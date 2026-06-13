# cd loan_decisions_component
# pip install joblib numpy pandas scipy scikit-learn shap dice-ml xgboost lightgbm dill pyarrow

"""
BNA Mortgage Eligibility -- Inference Pipeline (Local)
Place this file at the root of your cloned repo:
    loan_decisions_component/inference.py

Run:
    cd loan_decisions_component
    python3 inference.py

Requirements:
    pip install joblib numpy pandas scipy scikit-learn shap dice-ml xgboost lightgbm
"""

import os, joblib, warnings
import numpy as np
import pandas as pd
from scipy.stats import percentileofscore
warnings.filterwarnings('ignore')

from validators import validate_input, engineer_features, compute_rule_manually, AGE_MAX, decode_features
from feature_mapping import map_to_lc, map_to_ger

# ── PATHS: auto-resolved relative to this file ────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CKPT_BNA = os.path.join(BASE_DIR, 'artifacts', 'bna')
CKPT_LC  = os.path.join(BASE_DIR, 'artifacts', 'lendingclub')
CKPT_GER = os.path.join(BASE_DIR, 'artifacts', 'germancredit')
AGG_DIR  = os.path.join(BASE_DIR, 'artifacts', 'aggregator')



# ── LOAD ARTIFACTS ────────────────────────────────────────────────────────────
def load_artifacts():
    import shap
    from sklearn.isotonic import IsotonicRegression
    print('Loading artifacts...')
    
    for path in [CKPT_BNA, CKPT_LC, CKPT_GER, AGG_DIR]:
        if not os.path.exists(path):
            raise FileNotFoundError(f'Missing: {path}')

    arts = {}

    # Load raw RF model and calibrator separately -- bypass CalibWrap
    calibrators = joblib.load(f'{CKPT_BNA}/calibrators.joblib')
    # calibrators is (iso_lgb, iso_xgb, iso_rf) -- we need iso_rf
    iso_rf = calibrators[2]
    rf_raw = joblib.load(f'{CKPT_BNA}/model_rf_tuned.joblib')
    rf_raw.n_jobs = 1   # fix Windows hang

    # Rebuild CalibWrap locally
    class CalibWrap:
        def __init__(self, model, iso):
            self.model = model
            self.iso   = iso
        def predict_proba(self, X):
            raw = self.model.predict_proba(X)[:,1]
            cal = self.iso.transform(raw)
            import numpy as np
            return np.column_stack([1-cal, cal])

    arts['bna_model']      = CalibWrap(rf_raw, iso_rf)
    arts['bna_val_probas'] = np.load(f'{CKPT_BNA}/val_probas_for_ranking.npy')
    arts['bna_features']   = joblib.load(f'{CKPT_BNA}/features.joblib')
    arts['bna_display']    = joblib.load(f'{CKPT_BNA}/feature_meta.joblib')['display_names']
    arts['bna_dice_data']  = pd.read_parquet(f'{CKPT_BNA}/dice_reference_data.parquet')
    arts['bna_explainer']  = joblib.load(f'{CKPT_BNA}/shap_explainer.joblib')
    print('  [OK] BNA')

    arts['lc_val_probas']  = np.load(f'{CKPT_LC}/val_probas_for_ranking.npy')
    arts['ger_val_probas'] = np.load(f'{CKPT_GER}/val_probas_for_ranking.npy')
    arts['lc_auc']         = joblib.load(f'{CKPT_LC}/aggregator_meta.joblib')['val_auc']
    arts['ger_auc']        = joblib.load(f'{CKPT_GER}/aggregator_meta.joblib')['val_auc']
    arts['lc_features']    = joblib.load(f'{CKPT_LC}/features.joblib')
    arts['ger_features']   = joblib.load(f'{CKPT_GER}/features.joblib')
    arts['lc_medians']     = joblib.load(f'{CKPT_LC}/train_medians.joblib')
    arts['ger_medians']    = joblib.load(f'{CKPT_GER}/train_medians.joblib')

    lc_cals  = joblib.load(f'{CKPT_LC}/calibrators.joblib')
    ger_cals = joblib.load(f'{CKPT_GER}/calibrators.joblib')
    lc_iso   = lc_cals[1]    # iso_xgb
    lc_raw   = joblib.load(f'{CKPT_LC}/model_xgb_tuned.joblib')
    ger_iso  = ger_cals[2]   # iso_rf
    ger_raw  = joblib.load(f'{CKPT_GER}/model_rf_tuned.joblib')
    ger_raw.n_jobs = 1

    class LCCalibWrap:
        def __init__(self, m, iso): self.model = m; self.iso = iso
        def predict_proba(self, X):
            raw = self.model.predict_proba(X)[:,1]
            cal = self.iso.transform(raw)
            return np.column_stack([1-cal, cal])

    class GERCalibWrap:
        def __init__(self, m, iso): self.model = m; self.iso = iso
        def predict_proba(self, X):
            raw = self.model.predict_proba(X)[:,1]
            cal = self.iso.transform(raw)
            return np.column_stack([1-cal, cal])

    arts['lc_model']  = LCCalibWrap(lc_raw, lc_iso)
    arts['ger_model'] = GERCalibWrap(ger_raw, ger_iso)
    print('  [OK] LC and GER')

    cfg = joblib.load(f'{AGG_DIR}/aggregator_config.joblib')
    arts['bna_thr']      = cfg['bna_thr']
    arts['escalate_thr'] = cfg.get('escalate_thr', 0.55)
    arts['lc_neutral']   = float(np.median(arts['lc_val_probas']))
    arts['ger_neutral']  = float(np.median(arts['ger_val_probas']))
    print('  [OK] Aggregator config')
    print(f'       LC neutral={arts["lc_neutral"]:.4f}  GER neutral={arts["ger_neutral"]:.4f}')
    # print()
    return arts


# ── STAGE 1 ───────────────────────────────────────────────────────────────────
def stage1(X_feat, arts):
    model = arts['bna_model']
    # Fix for Windows: RF hangs with parallel jobs -- force single thread
    if hasattr(model, 'model') and hasattr(model.model, 'n_jobs'):
        model.model.n_jobs = 1
    prob     = float(model.predict_proba(X_feat)[:,1][0])
    thr      = arts['bna_thr']
    eligible = prob < thr
    return {
        'eligibility': 'ELIGIBLE' if eligible else 'NOT ELIGIBLE',
        'eligible':    eligible,
        'bna_prob':    round(prob, 4),
        'bna_thr':     round(thr, 3),
        'bna_margin':  round(thr - prob, 4),
    }


# ── STAGE 2 ───────────────────────────────────────────────────────────────────
def stage2(X_bna, arts):
    X_lc  = map_to_lc(X_bna, arts['lc_medians'])
    X_ger = map_to_ger(X_bna, arts['ger_medians'])

    for col in arts['lc_features']:
        if col not in X_lc.columns: X_lc[col] = 0.0
    for col in arts['ger_features']:
        if col not in X_ger.columns: X_ger[col] = 0.0

    X_lc  = X_lc[arts['lc_features']].astype(float)
    X_ger = X_ger[arts['ger_features']].astype(float)

    lc_prob  = float(arts['lc_model'].predict_proba(X_lc)[:,1][0])
    ger_prob = float(arts['ger_model'].predict_proba(X_ger)[:,1][0])

    lc_rank  = percentileofscore(arts['lc_val_probas'], lc_prob,  kind='rank') / 100
    ger_rank = percentileofscore(arts['ger_val_probas'], ger_prob, kind='rank') / 100

    total  = arts['lc_auc'] + arts['ger_auc']
    w_lc   = arts['lc_auc'] / total
    w_ger  = arts['ger_auc'] / total
    score  = w_lc * lc_rank + w_ger * ger_rank
    thr    = arts['escalate_thr']

    lc_zone  = 'ESCALATE' if lc_rank > thr else 'REVIEW'
    ger_zone = 'ESCALATE' if ger_rank > thr else 'REVIEW'
    disagree = (lc_zone == 'ESCALATE' and ger_zone == 'REVIEW') or \
               (lc_zone == 'REVIEW'   and ger_zone == 'ESCALATE')
    final    = 'ESCALATE' if (disagree or score > thr) else 'REVIEW'

    return {
        'risk_zone':    final,
        'risk_score':   round(score, 4),
        'lc_prob':      round(lc_prob, 4),
        'ger_prob':     round(ger_prob, 4),
        'lc_rank':      round(lc_rank, 4),
        'ger_rank':     round(ger_rank, 4),
        'lc_zone':      lc_zone,
        'ger_zone':     ger_zone,
        'disagreement': disagree,
        'escalate_thr': thr,
        'weights':      {'w_lc': round(w_lc, 4), 'w_ger': round(w_ger, 4)},
        'note':         'LC and GER scores via BNA feature mapping',
    }


# ── SHAP ──────────────────────────────────────────────────────────────────────
def explain_shap(X_feat, arts, top_n=10):
    sv = arts['bna_explainer'].shap_values(X_feat, check_additivity=False, approximate=True)
    if isinstance(sv, list): sv = sv[1]
    if sv.ndim == 3:         sv = sv[:, :, 1]
    sv_s    = sv[0]
    feats   = arts['bna_features']
    display = arts['bna_display']
    idx     = np.argsort(np.abs(sv_s))[::-1][:top_n]
    return {
        'shap_sum': round(float(sv_s.sum()), 4),
        'contributions': [
            {
                'feature':      feats[i],
                'display_name': display.get(feats[i], feats[i]),
                'value_raw':    float(X_feat.iloc[0][feats[i]]),
                'value_display': decode_features({feats[i]: float(X_feat.iloc[0][feats[i]])}).get(feats[i], str(float(X_feat.iloc[0][feats[i]]))),
                'shap':         round(float(sv_s[i]), 4),
                'direction':    ('toward rejection' if sv_s[i] > 0
                                 else 'toward acceptance'),
            }
            for i in idx
        ],
    }


# ── DICE ──────────────────────────────────────────────────────────────────────
def explain_dice(X_feat, arts, n_cf=3):
    try:
        import dice_ml
    except ImportError:
        return {'error': 'dice-ml not installed -- run: pip install dice-ml'}

    try:
        features  = arts['bna_features']
        dice_ref  = arts['bna_dice_data'].copy()
        y_col     = 'y' if 'y' in dice_ref.columns else dice_ref.columns[-1]
        X_dice    = dice_ref.drop(columns=[y_col])
        for col in features:
            if col not in X_dice.columns:
                X_dice[col] = 0.0
        X_dice    = X_dice[features].astype('float64')
        dice_data = X_dice.copy()
        dice_data[y_col] = arts['bna_dice_data'][y_col].values.astype('float64')
        for col in features:
            dice_data[col] = dice_data[col].astype(float)

        query      = X_feat[features].copy()
        for col in features:
            query[col] = query[col].astype(float)

        immutable  = ['AGE', 'sexe_encoded']
        continuous = [f for f in features
                      if f in ['AGE', 'montant_credit', 'TAUX INTERET',
                               'DUREE DU CREDIT', 'revenu_estime',
                               'montant_par_mois']]

        class ModelWrap:
            def __init__(self, m): self.m = m
            def predict_proba(self, X):
                if not isinstance(X, pd.DataFrame):
                    X = pd.DataFrame(X, columns=features)
                Xa = X[features].copy()
                for col in features:
                    Xa[col] = Xa[col].astype(float)
                result = self.m.predict_proba(Xa)
                return np.array(result)


        # print(dice_data.dtypes)
        # print(dice_data.head(2))

        d   = dice_ml.Data(dataframe=dice_data, continuous_features=continuous,
                           outcome_name=y_col)
        exp = dice_ml.Dice(d, dice_ml.Model(model=ModelWrap(arts['bna_model']),
                                            backend='sklearn'), method='genetic')
        cf  = exp.generate_counterfactuals(
            query, total_CFs=n_cf, desired_class=0,
            features_to_vary=[f for f in features if f not in immutable],
            verbose=False)

        cf_df    = cf.cf_examples_list[0].final_cfs_df
        orig     = query.iloc[0]
        changes  = {}
        for col in features:
            ov = round(float(orig[col]), 4)
            for _, row in cf_df.iterrows():
                cv = round(float(row[col]), 4)
                if abs(ov - cv) > 0.001:
                    if col not in changes:
                        # Translate derived features back to actionable terms
                        if col == 'montant_par_mois':
                            dur = float(X_feat.iloc[0]['DUREE DU CREDIT'])
                            implied_amount = cv * dur
                            action = f'Reduce monthly portion to {cv:,.0f} DZD --> implies loan ≈ {implied_amount:,.0f} DZD'
                        elif col == 'montant_credit':
                            action = f'Reduce loan amount to {cv:,.0f} DZD'
                        elif col == 'DUREE DU CREDIT':
                            action = f'Extend duration to {int(cv)} months ({int(cv)//12} years)'
                        elif col == 'revenu_estime':
                            action = f'Income bracket change --> {cv:,.0f} DZD/month'
                        else:
                            action = f'{arts["bna_display"].get(col, col)}: {ov} --> {cv}'

                        pct = abs(cv - ov) / abs(ov) if abs(ov) > 1e-9 else None
                        changes[col] = {
                            'feature':      col,
                            'display_name': arts['bna_display'].get(col, col),
                            'original':     ov,
                            'suggestions':  [],
                            'action':       action,
                            'pct_change':   pct,
                        }
                    changes[col]['suggestions'].append(cv)

        return {'changes': list(changes.values()), 'n_cf': n_cf}

    except Exception as e:
        return {'error': str(e)}


# ── FULL PIPELINE ─────────────────────────────────────────────────────────────
def predict_applicant(raw, arts):
    print('  validating...')
    valid, errors = validate_input(raw)
    if not valid:
        print('Input validation failed:')
        for e in errors: print(f'  - {e}')
        return None

    print('  engineering features...')
    X = engineer_features(raw)
    # print(f'  X shape: {X.shape}')

    print('  rule check...')
    rule = compute_rule_manually(raw)
    # print(f'  rule: {rule}')

    print('  stage 1...')
    s1 = stage1(X, arts)
    # print(f'  s1: {s1}')

    print('  stage 2...')
    s2 = stage2(X, arts)
    # print(f'  s2: {s2}')

    print('  shap...')
    shap_exp = explain_shap(X, arts)
    print(f'  shap done')

    dice_exp = explain_dice(X, arts) if not s1['eligible'] else None
    decision = aggregate_decision(s1, s2)
    return {
        'stage1':     s1,
        'stage2':     s2,
        'rule_check': rule,
        'shap':       shap_exp,
        'dice':       dice_exp,
        'decision':   decision,
        'features':   X.iloc[0].to_dict(),
    }


def aggregate_decision(s1, s2):
    """Combine Stage 1 (eligibility gate) and Stage 2 (behavioral risk) into a
    single authoritative decision.

    Logic:
      - not eligible (Stage 1)            -> DECLINE
      - eligible + ESCALATE risk zone     -> ESCALATE  (refer for manual review)
      - eligible + REVIEW   risk zone     -> APPROVE    (proceed, standard review)
    """
    if not s1['eligible']:
        return {
            'decision': 'DECLINE',
            'label':    'DECLINE',
            'reason':   'Does not meet BNA eligibility criteria.',
            'stage':    'Stage 1',
        }
    if s2['risk_zone'] == 'ESCALATE':
        return {
            'decision': 'ESCALATE',
            'label':    'ESCALATE',
            'reason':   'Eligible, but flagged as HIGH behavioral risk (or model disagreement). Needs EXTRA senior/manual attention before any decision -- not the usual standard review.',
            'stage':    'Stage 2',
        }
    return {
        'decision': 'APPROVE',
        'label':    'APPROVE FOR REVIEW',
        'reason':   'Eligible and low behavioral risk; proceed with standard documentation.',
        'stage':    'Stage 1+2',
    }


# ── REPORT FORMATTERS ─────────────────────────────────────────────────────────
# def print_employee_report(result):
#     s1   = result['stage1']
#     s2   = result['stage2']
#     rule = result['rule_check']
#     shap = result['shap']

#     print('\n' + '='*65)
#     print('EMPLOYEE VIEW -- FULL ASSESSMENT REPORT')
#     print('='*65)

#     print('\nSTAGE 1 -- BNA ELIGIBILITY')
#     print(f'  Result:      {s1["eligibility"]}')
#     print(f'  BNA prob:    {s1["bna_prob"]:.4f}  '
#           f'(threshold={s1["bna_thr"]:.3f}  margin={s1["bna_margin"]:+.4f})')
#     print(f'\n  Rule check:')
#     print(f'    Monthly installment : {rule["mensualite"]:>12,.0f} DZD/month')
#     print(f'    Repayment ceiling   : {rule["capacite"]:>12,.0f} DZD/month  '
#           f'(quotite={rule["quotite"]:.0%})')
#     print(f'    Capacity rule       : {"[OK]" if rule["capacity_ok"] else "[FAIL]"}')
#     print(f'    Age at end of loan  : {rule["age_at_end"]:.1f} years  (max={AGE_MAX})')
#     print(f'    Age rule            : {"[OK]" if rule["age_ok"] else "[FAIL]"}')
#     if rule['failing_rule']:
#         print(f'    >> Failing: {rule["failing_rule"].upper()} rule')

#     print(f'\nSTAGE 2 -- BEHAVIORAL RISK  [LC + GER via feature mapping]')
#     print(f'  Risk zone:   {s2["risk_zone"]}')
#     print(f'  Risk score:  {s2["risk_score"]:.4f}  (threshold={s2["escalate_thr"]})')
#     print(f'  LC  (w={s2["weights"]["w_lc"]:.3f}): prob={s2["lc_prob"]:.4f}  rank={s2["lc_rank"]:.4f}  zone={s2["lc_zone"]}')
#     print(f'  GER (w={s2["weights"]["w_ger"]:.3f}): prob={s2["ger_prob"]:.4f}  rank={s2["ger_rank"]:.4f}  zone={s2["ger_zone"]}')
#     print(f'  Disagreement: {s2["disagreement"]}')
#     print(f'  Note: {s2["note"]}')

#     print(f'\nSHAP -- Top 5 drivers:')
#     for c in shap['contributions'][:5]:
#         bar  = '█' * min(int(abs(c['shap']) * 40), 30)
#         print(f'  {c["display_name"]:<35} {c["shap"]:+.4f}  {bar}')

#     print(f'\nRECOMMENDATION:')
#     dec = result.get('decision') or aggregate_decision(s1, s2)
#     print(f'  {dec["label"]} -- {dec["reason"]}')
#     if dec['decision'] == 'DECLINE':
#         dice = result.get('dice')
#         if dice and 'changes' in dice and dice['changes']:
#             # Only show counterfactuals on features the bank or client can act on.
#             # Immutable / inappropriate attributes (age, dependents, sex) are never shown.
#             EMP_EXCLUDE = {'AGE', 'AGE_BAND', 'age_band', 'sexe_encoded',
#                            'nb_personnes_charge', 'family_dependents'}
#             shown = [ch for ch in dice['changes']
#                      if ch.get('feature', ch.get('display_name')) not in EMP_EXCLUDE]
#             if shown:
#                 print(f'\n  COUNTERFACTUAL SUGGESTIONS:')
#                 for ch in shown:
#                     if 'action' in ch:
#                         print(f'    --> {ch["action"]}')
#                     else:
#                         sugg = ch['suggestions'][0] if ch['suggestions'] else '?'
#                         print(f'    --> {ch["display_name"]}: {ch["original"]} --> {sugg}')
#         elif dice and 'error' in dice:
#             print(f'  DiCE error: {dice["error"]}')
#     print('='*65)


# def print_client_report(result):
#     s1   = result['stage1']
#     rule = result['rule_check']

#     print('\n' + '='*65)
#     print('CLIENT VIEW -- APPLICATION SUMMARY')
#     print('='*65)

#     print(f'\nELIGIBILITY: [{s1["eligibility"]}]')
#     if s1['eligible']:
#         if s1['bna_margin'] > 0.10:
#             print('  Your application meets BNA mortgage eligibility criteria')
#             print('  with comfortable margin.')
#         else:
#             print('  Your application meets BNA mortgage eligibility criteria.')
#             print('  Note: your repayment capacity is close to the eligibility limit.')
#     else:
#         print('  Your application does not meet BNA mortgage eligibility criteria.')
#         if rule['failing_rule'] == 'capacity':
#             excess = rule['mensualite'] - rule['capacite']
#             print(f'  Your monthly installment exceeds your repayment ceiling')
#             print(f'  by approximately {excess:,.0f} DZD/month.')
#         elif rule['failing_rule'] == 'age':
#             print(f'  Your age at end of credit term ({rule["age_at_end"]:.1f} years)')
#             print(f'  exceeds the maximum of {AGE_MAX} years.')

#     print(f'\nNEXT STEPS:')
#     if s1['eligible']:
#         print('  1. Prepare standard income and employment documentation.')
#         print('  2. Application proceeds through standard loan officer review.')
#         print('='*65)
#         return

#     steps = _client_steps_from_dice(result.get('dice'), rule, result)
#     for i, step in enumerate(steps, 1):
#         print(f'  {i}. {step}')
#     print('  ' + '-'*40)
#     print('  These suggestions are indicative. Contact your BNA branch')
#     print('  for a detailed eligibility consultation.')
#     print('='*65)


# def _round_dzd(v, mode='nearest'):
#     """Round a DZD figure to a realistic increment for client-facing advice.
#     Coarser steps for large loan amounts, finer for small monthly figures.
#     mode='down' floors to the increment (used for installment ceilings so the
#     advice never suggests a higher payment than the counterfactual)."""
#     import math
#     v = float(v)
#     if v >= 1_000_000:
#         step = 100_000
#     elif v >= 100_000:
#         step = 10_000
#     else:
#         step = 1_000
#     if mode == 'down':
#         return math.floor(v / step) * step
#     return round(v / step) * step


# def _client_steps_from_dice(dice, rule, result, max_steps=3, max_reduction=0.40):
#     """Build client-friendly next steps from this applicant's counterfactuals.

#     - Only client-actionable, plain-language features are surfaced.
#     - Institution-side (interest rate), immutable (age, dependents, sex) and
#       raw encoded features are never shown.
#     - Income is intentionally excluded from client advice.
#     - Suggestions implying an unrealistic change (> max_reduction) are skipped.
#     - Loan amount / monthly portion are collapsed into one idea.
#     - Capped at max_steps; falls back to rule-based guidance if nothing usable.
#     """
#     CLIENT_ACTIONABLE = {'montant_credit', 'DUREE DU CREDIT', 'montant_par_mois'}

#     X = result['features']  # dict of the applicant's engineered features
#     steps, seen = [], set()

#     if dice and dice.get('changes'):
#         for ch in dice['changes']:
#             col = ch.get('feature', ch.get('display_name'))
#             if col not in CLIENT_ACTIONABLE:
#                 continue
#             sugg = ch['suggestions'][0] if ch.get('suggestions') else None
#             if sugg is None:
#                 continue
#             # Realism: skip suggestions that demand an extreme change
#             pct = ch.get('pct_change')
#             if pct is not None and pct > max_reduction:
#                 continue

#             key = 'loan_size' if col in ('montant_credit', 'montant_par_mois') else col
#             if key in seen:
#                 continue
#             seen.add(key)

#             if col == 'montant_credit':
#                 amt = _round_dzd(sugg)
#                 steps.append(
#                     f'Consider reducing your requested loan amount to about '
#                     f'{amt:,.0f} DZD.')
#             elif col == 'montant_par_mois':
#                 dur = float(X['DUREE DU CREDIT'])
#                 monthly = _round_dzd(sugg, mode='down')
#                 implied = _round_dzd(monthly * dur)
#                 steps.append(
#                     f'Consider lowering your monthly installment to about '
#                     f'{monthly:,.0f} DZD, which corresponds to a loan '
#                     f'of roughly {implied:,.0f} DZD.')
#             elif col == 'DUREE DU CREDIT':
#                 yrs = int(sugg) // 12
#                 steps.append(
#                     f'Consider adjusting your loan duration to about '
#                     f'{int(sugg)} months ({yrs} years).')

#             if len(steps) >= max_steps:
#                 break

#     if not steps:  # fallback: no usable client-facing counterfactual
#         if rule['failing_rule'] == 'age':
#             # Age-rule declines can only be helped by shortening the term.
#             steps.append('Request a simulation with a shorter loan duration, '
#                          'so the loan ends before the maximum age limit.')
#         elif rule['failing_rule'] == 'capacity':
#             steps.append('Request a simulation with a reduced loan amount; '
#                          'a 15-20% reduction may bring the installment within limits.')
#         else:
#             steps.append('Request a simulation with a reduced loan amount '
#                          'or a shorter loan duration.')

#     return steps[:max_steps]


# # ── EXAMPLES ──────────────────────────────────────────────────────────────────
# EXAMPLE_ELIGIBLE = {
#     'AGE': 42, 'SEXE': 'M',
#     'SITUATION_FAMILLE': 'MARIE(E)', 'PROFESSION': 'EMPLOYE',
#     'REVENU': 'SUPERIEUR A 6 FOIS LE SNMG',
#     'TYPE_CREDIT': 'CREDIT IMMOBILIER NON BONIFIE / NON EPARGNANT',
#     'MONTANT_CREDIT': 5_000_000, 'DUREE_CREDIT': 240, 'TAUX_INTERET': 5.75,
# }

# EXAMPLE_NOT_ELIGIBLE = {
#     'AGE': 52, 'SEXE': 'M',
#     'SITUATION_FAMILLE': 'MARIE(E)', 'PROFESSION': 'EMPLOYE',
#     'REVENU': 'INFERIEUR A 6 FOIS LE SNMG',
#     'TYPE_CREDIT': 'CREDIT IMMOBILIER NON BONIFIE / NON EPARGNANT',
#     'MONTANT_CREDIT': 8_500_000, 'DUREE_CREDIT': 240, 'TAUX_INTERET': 5.75,
# }


# if __name__ == '__main__':
#     arts = load_artifacts()

#     print(type(arts['bna_model']))
#     print(type(arts['bna_model'].model))

#     print('#'*65)
#     print('# EXAMPLE 1 -- ELIGIBLE APPLICANT')
#     print('#'*65)
#     try:
#         print('Running predict_applicant...')
#         r1 = predict_applicant(EXAMPLE_ELIGIBLE, arts)
#         # print(f'Result: {r1}')
#         if r1:
#             print_employee_report(r1)
#             print_client_report(r1)
#     except Exception as e:
#         import traceback
#         traceback.print_exc()

#     print('\n' + '#'*65)
#     print('# EXAMPLE 2 -- NOT ELIGIBLE APPLICANT')
#     print('#'*65)
#     r2 = predict_applicant(EXAMPLE_NOT_ELIGIBLE, arts)
#     print_employee_report(r2)
#     print_client_report(r2)