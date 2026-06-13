# # validators.py
# import unicodedata
# import pandas as pd

# SNMG    = 24_000
# DIFFERE = 6
# AGE_MAX = 75
# SIX_SNMG = 6 * SNMG          # 144,000 -> income-bracket threshold

# REVENU_MAP = {
#     'INFERIEUR A 6 FOIS LE SNMG': 3 * SNMG,
#     'SUPERIEUR A 6 FOIS LE SNMG': 9 * SNMG,
# }
# PROFESSION_STABILITY = {
#     'EMPLOYE': 3, 'RETRAITE': 3, 'PROFESSION LIBERALE': 3,
#     'COMMERCANT': 2, 'ARTISAN': 1, 'AGRICULTEUR': 1, 'ETUDIANT': 0,
# }
# DEPENDENTS_TIER = {            # legacy fallback (when only family status is given)
#     'MARIE(E)': 2, 'DIVORCE(E)': 1, 'VEUF(VE)': 1, 'CELIBATAIRE': 0,
# }
# FEATURE_ORDER = [
#     'AGE', 'montant_credit', 'TAUX INTERET', 'DUREE DU CREDIT',
#     'revenu_estime', 'is_epargnant', 'is_bonifie', 'sexe_encoded',
#     'stabilite_profession', 'dependents_tier',
#     'montant_par_mois', 'revenu_tier', 'age_band', 'is_long_loan'
# ]

# VALID_VALUES = {
#     'SEXE':       ['M', 'F'],
#     'PROFESSION': list(PROFESSION_STABILITY.keys()),
# }


# # ── helpers ─────────────────────────────────────────────────────────────────
# def _strip_accents(s):
#     return ''.join(c for c in unicodedata.normalize('NFD', str(s))
#                    if unicodedata.category(c) != 'Mn')

# def _credit_flags_from_text(type_credit):
#     """Robustly read subsidy / LPP / savings flags from a credit-type label.
#     Handles accents and the 'NON BONIFIE' case correctly."""
#     t = _strip_accents(type_credit).upper()
#     is_lpp     = 'LPP' in t
#     is_non_bon = ('NON BONIFIE' in t) or ('NON-BONIFIE' in t)
#     is_bonifie = (not is_non_bon) and ('BONIFIE' in t)      # LPP is also subsidized
#     is_eparg   = ('EPARGNANT' in t) and ('NON EPARGNANT' not in t)
#     return is_bonifie, is_lpp, is_eparg

# def _flags(raw):
#     """Return (is_bonifie, is_lpp, is_epargnant).
#     Explicit booleans (IS_BONIFIE / IS_LPP / EPARGNANT) take priority over text."""
#     tb, tl, te = _credit_flags_from_text(raw.get('TYPE_CREDIT', ''))
#     is_bonifie = bool(raw['IS_BONIFIE']) if 'IS_BONIFIE' in raw else tb
#     is_lpp     = bool(raw['IS_LPP'])     if 'IS_LPP'     in raw else tl
#     if 'EPARGNANT' in raw:
#         is_eparg = bool(raw['EPARGNANT'])
#     elif 'IS_EPARGNANT' in raw:
#         is_eparg = bool(raw['IS_EPARGNANT'])
#     else:
#         is_eparg = te
#     return is_bonifie, is_lpp, is_eparg

# def _income(raw):
#     """Actual monthly income (DZD). Falls back to the legacy REVENU bracket."""
#     if raw.get('INCOME') not in (None, ''):
#         return float(raw['INCOME'])
#     return float(REVENU_MAP.get(raw.get('REVENU'), 3 * SNMG))

# def income_bracket(income):
#     return ('SUPERIEUR A 6 FOIS LE SNMG' if income >= SIX_SNMG
#             else 'INFERIEUR A 6 FOIS LE SNMG')

# def derive_rate(is_bonifie, is_lpp, income):
#     """Interest rate from credit type and income bracket.
#     LPP is fixed at 3%. Other subsidized loans: 1% (< 6xSNMG) or 3.25% (>=).
#     Non-subsidized: 6.25%."""
#     if is_lpp:
#         return 3.0
#     if is_bonifie:
#         return 1.0 if income < SIX_SNMG else 3.25
#     return 6.25


# # ── validation ──────────────────────────────────────────────────────────────
# def validate_input(raw):
#     """Validate raw applicant dict. Returns (is_valid, errors list)."""
#     errors = []
#     required = ['AGE', 'SEXE', 'PROFESSION', 'TYPE_CREDIT',
#                 'MONTANT_CREDIT', 'DUREE_CREDIT']
#     for field in required:
#         if field not in raw or raw[field] is None or str(raw[field]).strip() == '':
#             errors.append(f'Missing required field: {field}')

#     # income: accept a number (INCOME) or the legacy bracket (REVENU)
#     if (raw.get('INCOME') in (None, '')) and (raw.get('REVENU') in (None, '')):
#         errors.append('Missing income: provide INCOME (DZD) or REVENU bracket')
#     # dependents: accept a count (DEPENDENTS) or the legacy family status
#     if (raw.get('DEPENDENTS') in (None, '')) and (raw.get('SITUATION_FAMILLE') in (None, '')):
#         errors.append('Missing dependents: provide DEPENDENTS count or SITUATION_FAMILLE')

#     if errors:
#         return False, errors

#     if not (18 <= int(raw['AGE']) <= 70):
#         errors.append('AGE must be between 18 and 70')
#     if float(raw['MONTANT_CREDIT']) <= 0:
#         errors.append('MONTANT_CREDIT must be positive')
#     if int(raw['DUREE_CREDIT']) <= DIFFERE:
#         errors.append(f'DUREE_CREDIT must be greater than {DIFFERE} months')
#     if raw.get('INCOME') not in (None, '') and float(raw['INCOME']) <= 0:
#         errors.append('INCOME must be positive')
#     if raw.get('DEPENDENTS') not in (None, '') and int(float(raw['DEPENDENTS'])) < 0:
#         errors.append('DEPENDENTS must be zero or greater')
#     for field, valid in VALID_VALUES.items():
#         if raw.get(field) not in valid:
#             errors.append(f'{field} must be one of: {valid}')

#     return len(errors) == 0, errors


# # ── feature engineering ───────────────────────────────────────────────────────
# def engineer_features(raw):
#     """Transform a validated raw dict into the model-ready DataFrame.
#     Interest rate is derived (not taken as input). The model's revenu_estime
#     stays bucketed to match the training domain; the actual income is used only
#     by the business rule (see compute_rule_manually)."""
#     f = {}
#     income = _income(raw)
#     is_bonifie, is_lpp, is_eparg = _flags(raw)

#     f['AGE']             = float(raw['AGE'])
#     f['DUREE DU CREDIT'] = float(raw['DUREE_CREDIT'])
#     f['montant_credit']  = float(raw['MONTANT_CREDIT'])
#     f['TAUX INTERET']    = derive_rate(is_bonifie, is_lpp, income)
#     f['revenu_estime']   = float(REVENU_MAP[income_bracket(income)])   # bucketed for the model
#     f['sexe_encoded']    = int(raw['SEXE'] == 'M')
#     f['stabilite_profession'] = int(PROFESSION_STABILITY.get(raw['PROFESSION'], 1))

#     if raw.get('DEPENDENTS') not in (None, ''):
#         f['dependents_tier'] = min(int(float(raw['DEPENDENTS'])), 2)   # actual count -> tier
#     else:
#         f['dependents_tier'] = int(DEPENDENTS_TIER.get(raw.get('SITUATION_FAMILLE'), 0))

#     f['is_bonifie']   = int(is_bonifie)
#     f['is_epargnant'] = int(is_eparg)
#     f['montant_par_mois'] = f['montant_credit'] / f['DUREE DU CREDIT']
#     f['revenu_tier']      = int(f['revenu_estime'] > 3 * SNMG)
#     age = f['AGE']
#     f['age_band']     = (0 if age < 30 else 1 if age < 40 else
#                          2 if age < 50 else 3 if age < 60 else 4)
#     f['is_long_loan'] = int(f['DUREE DU CREDIT'] > 240)
#     return pd.DataFrame([{k: f[k] for k in FEATURE_ORDER}])


# # ── eligibility rule ──────────────────────────────────────────────────────────
# def compute_rule_manually(raw):
#     """Compute BNA eligibility rules directly as a cross-check.
#     Repayment capacity uses the ACTUAL income; the income bracket relative to
#     6xSNMG is reported as a flag. Interest rate is derived from the credit type."""
#     income   = _income(raw)
#     is_bonifie, is_lpp, is_eparg = _flags(raw)
#     taux     = derive_rate(is_bonifie, is_lpp, income)
#     quotite  = 0.45 if is_eparg else 0.40
#     capacite = income * quotite                       # actual income (item 2)

#     n = float(raw['DUREE_CREDIT']) - DIFFERE
#     r = taux / 100 / 12
#     mensualite = (float(raw['MONTANT_CREDIT']) * r / (1 - (1 + r) ** (-n))) if r > 0 \
#                  else float(raw['MONTANT_CREDIT']) / n
#     age_end = float(raw['AGE']) + float(raw['DUREE_CREDIT']) / 12
#     cap_ok  = mensualite <= capacite
#     age_ok  = age_end <= AGE_MAX
#     return {
#         'mensualite':    round(mensualite, 2),
#         'capacite':      round(capacite, 2),
#         'quotite':       quotite,
#         'taux':          taux,
#         'income':        round(income, 2),
#         'income_bracket': income_bracket(income),
#         'above_6snmg':   income >= SIX_SNMG,
#         'age_at_end':    round(age_end, 1),
#         'capacity_ok':   cap_ok,
#         'age_ok':        age_ok,
#         'eligible':      cap_ok and age_ok,
#         'failing_rule':  (None if (cap_ok and age_ok)
#                           else 'capacity' if not cap_ok else 'age'),
#     }


# # ── human-readable decode ─────────────────────────────────────────────────────
# def decode_features(feat_dict):
#     """Convert model feature values back to human-readable English labels."""
#     decoded = {}
#     for k, v in feat_dict.items():
#         if k == 'sexe_encoded':
#             decoded['Sex'] = 'Male' if v == 1 else 'Female'
#         elif k == 'is_epargnant':
#             decoded['Savings plan'] = 'Yes' if v == 1 else 'No'
#         elif k == 'is_bonifie':
#             decoded['Bonified rate'] = 'Yes' if v == 1 else 'No'
#         elif k == 'revenu_tier':
#             decoded['Income tier'] = '> 6x SNMG' if v == 1 else '< 6x SNMG'
#         elif k == 'is_long_loan':
#             decoded['Long loan'] = 'Yes (>20 yrs)' if v == 1 else 'No'
#         elif k == 'age_band':
#             bands = {0: '<30', 1: '30-40', 2: '40-50', 3: '50-60', 4: '>60'}
#             decoded['Age band'] = bands.get(int(v), str(v))
#         elif k == 'stabilite_profession':
#             stabs = {0: 'Student', 1: 'Artisan/Farmer',
#                      2: 'Merchant', 3: 'Employee/Retired'}
#             decoded['Job stability'] = stabs.get(int(v), str(v))
#         elif k == 'dependents_tier':
#             deps = {0: 'None', 1: 'One', 2: 'Two or more'}
#             decoded['Dependents'] = deps.get(int(v), str(v))
#         elif k == 'montant_par_mois':
#             decoded['Monthly portion'] = f'{v:,.0f} DZD/month'
#         elif k == 'revenu_estime':
#             decoded['Estimated income'] = f'{v:,.0f} DZD/month'
#         elif k == 'montant_credit':
#             decoded['Loan amount'] = f'{v:,.0f} DZD'
#         elif k == 'AGE':
#             decoded['Age'] = f'{int(v)} years'
#         elif k == 'TAUX INTERET':
#             decoded['Interest rate'] = f'{v:.2f}%'
#         elif k == 'DUREE DU CREDIT':
#             decoded['Duration'] = f'{int(v)} months ({int(v)//12} years)'
#     return decoded

# validators.py
import unicodedata
import pandas as pd

SNMG    = 24_000
DIFFERE = 6
AGE_MAX = 75
SIX_SNMG = 6 * SNMG          # 144,000 -> income-bracket threshold

REVENU_MAP = {
    'INFERIEUR A 6 FOIS LE SNMG': 3 * SNMG,
    'SUPERIEUR A 6 FOIS LE SNMG': 9 * SNMG,
}
PROFESSION_STABILITY = {
    'EMPLOYE': 3, 'RETRAITE': 3, 'PROFESSION LIBERALE': 3,
    'COMMERCANT': 2, 'ARTISAN': 1, 'AGRICULTEUR': 1, 'ETUDIANT': 0,
}
DEPENDENTS_TIER = {            # legacy fallback (when only family status is given)
    'MARIE(E)': 2, 'DIVORCE(E)': 1, 'VEUF(VE)': 1, 'CELIBATAIRE': 0,
}
FEATURE_ORDER = [
    'AGE', 'montant_credit', 'TAUX INTERET', 'DUREE DU CREDIT',
    'revenu_estime', 'is_epargnant', 'is_bonifie', 'sexe_encoded',
    'stabilite_profession', 'dependents_tier',
    'montant_par_mois', 'revenu_tier', 'age_band', 'is_long_loan'
]

VALID_VALUES = {
    'SEXE':       ['M', 'F'],
    'PROFESSION': list(PROFESSION_STABILITY.keys()),
}


# ── helpers ─────────────────────────────────────────────────────────────────
def _strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s))
                   if unicodedata.category(c) != 'Mn')

def _credit_flags_from_text(type_credit):
    """Robustly read subsidy / LPP / savings flags from a credit-type label.
    Handles accents and the 'NON BONIFIE' case correctly."""
    t = _strip_accents(type_credit).upper()
    is_lpp     = 'LPP' in t
    is_non_bon = ('NON BONIFIE' in t) or ('NON-BONIFIE' in t)
    is_bonifie = (not is_non_bon) and ('BONIFIE' in t)      # LPP is also subsidized
    is_eparg   = ('EPARGNANT' in t) and ('NON EPARGNANT' not in t)
    return is_bonifie, is_lpp, is_eparg

def _flags(raw):
    """Return (is_bonifie, is_lpp, is_epargnant).
    Explicit booleans (IS_BONIFIE / IS_LPP / EPARGNANT) take priority over text."""
    tb, tl, te = _credit_flags_from_text(raw.get('TYPE_CREDIT', ''))
    is_bonifie = bool(raw['IS_BONIFIE']) if 'IS_BONIFIE' in raw else tb
    is_lpp     = bool(raw['IS_LPP'])     if 'IS_LPP'     in raw else tl
    if 'EPARGNANT' in raw:
        is_eparg = bool(raw['EPARGNANT'])
    elif 'IS_EPARGNANT' in raw:
        is_eparg = bool(raw['IS_EPARGNANT'])
    else:
        is_eparg = te
    return is_bonifie, is_lpp, is_eparg

def _income(raw):
    """Actual monthly income (DZD). Falls back to the legacy REVENU bracket."""
    if raw.get('INCOME') not in (None, ''):
        return float(raw['INCOME'])
    return float(REVENU_MAP.get(raw.get('REVENU'), 3 * SNMG))

def income_bracket(income):
    return ('SUPERIEUR A 6 FOIS LE SNMG' if income >= SIX_SNMG
            else 'INFERIEUR A 6 FOIS LE SNMG')

def derive_rate(is_bonifie, is_lpp, income):
    """Interest rate from credit type and income bracket.
    LPP is fixed at 3%. Other subsidized loans: 1% (< 6xSNMG) or 3.25% (>=).
    Non-subsidized: 6.25%."""
    if is_lpp:
        return 3.0
    if is_bonifie:
        return 1.0 if income < SIX_SNMG else 3.25
    return 6.25


# ── validation ──────────────────────────────────────────────────────────────
def validate_input(raw):
    """Validate raw applicant dict. Returns (is_valid, errors list)."""
    errors = []
    required = ['AGE', 'SEXE', 'PROFESSION', 'TYPE_CREDIT',
                'MONTANT_CREDIT', 'DUREE_CREDIT']
    for field in required:
        if field not in raw or raw[field] is None or str(raw[field]).strip() == '':
            errors.append(f'Missing required field: {field}')

    # income: accept a number (INCOME) or the legacy bracket (REVENU)
    if (raw.get('INCOME') in (None, '')) and (raw.get('REVENU') in (None, '')):
        errors.append('Missing income: provide INCOME (DZD) or REVENU bracket')
    # dependents: accept a count (DEPENDENTS) or the legacy family status
    if (raw.get('DEPENDENTS') in (None, '')) and (raw.get('SITUATION_FAMILLE') in (None, '')):
        errors.append('Missing dependents: provide DEPENDENTS count or SITUATION_FAMILLE')

    if errors:
        return False, errors

    if not (18 <= int(raw['AGE']) <= 70):
        errors.append('AGE must be between 18 and 70')
    if float(raw['MONTANT_CREDIT']) <= 0:
        errors.append('MONTANT_CREDIT must be positive')
    if int(raw['DUREE_CREDIT']) <= DIFFERE:
        errors.append(f'DUREE_CREDIT must be greater than {DIFFERE} months')
    if raw.get('INCOME') not in (None, '') and float(raw['INCOME']) <= 0:
        errors.append('INCOME must be positive')
    if raw.get('DEPENDENTS') not in (None, '') and int(float(raw['DEPENDENTS'])) < 0:
        errors.append('DEPENDENTS must be zero or greater')
    for field, valid in VALID_VALUES.items():
        if raw.get(field) not in valid:
            errors.append(f'{field} must be one of: {valid}')

    return len(errors) == 0, errors


# ── feature engineering ───────────────────────────────────────────────────────
def engineer_features(raw):
    """Transform a validated raw dict into the model-ready DataFrame.
    Interest rate is derived (not taken as input). The model's revenu_estime
    stays bucketed to match the training domain; the actual income is used only
    by the business rule (see compute_rule_manually)."""
    f = {}
    income = _income(raw)
    is_bonifie, is_lpp, is_eparg = _flags(raw)

    f['AGE']             = float(raw['AGE'])
    f['DUREE DU CREDIT'] = float(raw['DUREE_CREDIT'])
    f['montant_credit']  = float(raw['MONTANT_CREDIT'])
    f['TAUX INTERET']    = derive_rate(is_bonifie, is_lpp, income)
    f['revenu_estime']   = float(REVENU_MAP[income_bracket(income)])   # bucketed for the model
    f['sexe_encoded']    = int(raw['SEXE'] == 'M')
    f['stabilite_profession'] = int(PROFESSION_STABILITY.get(raw['PROFESSION'], 1))

    if raw.get('DEPENDENTS') not in (None, ''):
        f['dependents_tier'] = min(int(float(raw['DEPENDENTS'])), 2)   # actual count -> tier
    else:
        f['dependents_tier'] = int(DEPENDENTS_TIER.get(raw.get('SITUATION_FAMILLE'), 0))

    f['is_bonifie']   = int(is_bonifie)
    f['is_epargnant'] = int(is_eparg)
    f['montant_par_mois'] = f['montant_credit'] / f['DUREE DU CREDIT']
    f['revenu_tier']      = int(f['revenu_estime'] > 3 * SNMG)
    age = f['AGE']
    f['age_band']     = (0 if age < 30 else 1 if age < 40 else
                         2 if age < 50 else 3 if age < 60 else 4)
    f['is_long_loan'] = int(f['DUREE DU CREDIT'] > 240)
    return pd.DataFrame([{k: f[k] for k in FEATURE_ORDER}])


# ── eligibility rule ──────────────────────────────────────────────────────────
def compute_rule_manually(raw):
    """Compute BNA eligibility rules directly as a cross-check.
    Repayment capacity uses the ACTUAL income; the income bracket relative to
    6xSNMG is reported as a flag. Interest rate is derived from the credit type."""
    income   = _income(raw)
    is_bonifie, is_lpp, is_eparg = _flags(raw)
    taux     = derive_rate(is_bonifie, is_lpp, income)
    quotite  = 0.45 if is_eparg else 0.40
    capacite = income * quotite                       # actual income (item 2)

    n = float(raw['DUREE_CREDIT']) - DIFFERE
    r = taux / 100 / 12
    mensualite = (float(raw['MONTANT_CREDIT']) * r / (1 - (1 + r) ** (-n))) if r > 0 \
                 else float(raw['MONTANT_CREDIT']) / n
    age_end = float(raw['AGE']) + float(raw['DUREE_CREDIT']) / 12
    cap_ok  = mensualite <= capacite
    age_ok  = age_end <= AGE_MAX
    return {
        'mensualite':    round(mensualite, 2),
        'capacite':      round(capacite, 2),
        'quotite':       quotite,
        'taux':          taux,
        'income':        round(income, 2),
        'income_bracket': income_bracket(income),
        'above_6snmg':   income >= SIX_SNMG,
        'age_at_end':    round(age_end, 1),
        'capacity_ok':   cap_ok,
        'age_ok':        age_ok,
        'eligible':      cap_ok and age_ok,
        'failing_rule':  (None if (cap_ok and age_ok)
                          else 'capacity' if not cap_ok else 'age'),
    }


# ── human-readable decode ─────────────────────────────────────────────────────
def decode_features(feat_dict):
    """Convert model feature values back to human-readable English labels."""
    decoded = {}
    for k, v in feat_dict.items():
        if k == 'sexe_encoded':
            decoded['Sex'] = 'Male' if v == 1 else 'Female'
        elif k == 'is_epargnant':
            decoded['Savings plan'] = 'Yes' if v == 1 else 'No'
        elif k == 'is_bonifie':
            decoded['Bonified rate'] = 'Yes' if v == 1 else 'No'
        elif k == 'revenu_tier':
            decoded['Income tier'] = '> 6x SNMG' if v == 1 else '< 6x SNMG'
        elif k == 'is_long_loan':
            decoded['Long loan'] = 'Yes (>20 yrs)' if v == 1 else 'No'
        elif k == 'age_band':
            bands = {0: '<30', 1: '30-40', 2: '40-50', 3: '50-60', 4: '>60'}
            decoded['Age band'] = bands.get(int(v), str(v))
        elif k == 'stabilite_profession':
            stabs = {0: 'Student', 1: 'Artisan/Farmer',
                     2: 'Merchant', 3: 'Employee/Retired'}
            decoded['Job stability'] = stabs.get(int(v), str(v))
        elif k == 'dependents_tier':
            deps = {0: 'None', 1: 'One', 2: 'Two or more'}
            decoded['Dependents'] = deps.get(int(v), str(v))
        elif k == 'montant_par_mois':
            decoded['Monthly portion'] = f'{v:,.0f} DZD/month'
        elif k == 'revenu_estime':
            decoded['Estimated income'] = f'{v:,.0f} DZD/month'
        elif k == 'montant_credit':
            decoded['Loan amount'] = f'{v:,.0f} DZD'
        elif k == 'AGE':
            decoded['Age'] = f'{int(v)} years'
        elif k == 'TAUX INTERET':
            decoded['Interest rate'] = f'{v:.2f}%'
        elif k == 'DUREE DU CREDIT':
            decoded['Duration'] = f'{int(v)} months ({int(v)//12} years)'
    return decoded