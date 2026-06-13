"""
feature_mapping.py
Maps BNA applicant features to LC and GER feature spaces.
Both mappings fill all features with training medians, then
overwrite the ones that have meaningful BNA equivalents.

Place this file at the root of your cloned repo alongside inference.py.
"""

import os
import joblib
import numpy as np
import pandas as pd

# ── BNA to LC feature mapping ─────────────────────────────────────────────────
# Maps BNA engineered feature names to LC feature names
# Only features with a genuine conceptual equivalent are mapped.
# Everything else uses the LC training median.

BNA_TO_LC = {
    'montant_credit':  'loan_amnt',        # loan amount
    'TAUX INTERET':    'int_rate',          # interest rate
    'revenu_estime':   'annual_inc',        # annual income (BNA is monthly -- x12 below)
    'montant_par_mois':'installment',       # monthly payment approximation
    'AGE':             None,               # no LC equivalent
    'DUREE DU CREDIT': None,               # handled via is_long_term below
}

# BNA to German Credit feature mapping
BNA_TO_GER = {
    'montant_credit':  'credit_amount',    # loan amount
    'DUREE DU CREDIT': 'duration',         # loan duration in months
    'AGE':             'age',              # applicant age
    'stabilite_profession': None,          # handled via employment tier below
}


def map_to_lc(bna_features_df, lc_medians):
    """
    Build LC feature vector from BNA features + LC training medians.

    Parameters
    ----------
    bna_features_df : pd.DataFrame (1 row, 14 BNA features)
    lc_medians      : dict loaded from lc/checkpoints/train_medians.joblib

    Returns
    -------
    pd.DataFrame (1 row, all LC features)
    """
    row = bna_features_df.iloc[0]

    # Start with training medians for all LC features
    lc_row = {k: float(v) for k, v in lc_medians.items()}

    # Overwrite with BNA equivalents
    lc_row['loan_amnt']   = float(row['montant_credit'])
    lc_row['int_rate']    = float(row['TAUX INTERET'])
    lc_row['annual_inc']  = float(row['revenu_estime']) * 12   # monthly -> annual
    lc_row['installment'] = float(row['montant_par_mois'])
    lc_row['log_income']  = float(np.log1p(lc_row['annual_inc']))

    # Derived LC features from BNA data
    lc_row['loan_to_income']         = lc_row['loan_amnt'] / max(lc_row['annual_inc'], 1)
    lc_row['installment_to_income']  = lc_row['installment'] * 12 / max(lc_row['annual_inc'], 1)
    lc_row['is_long_term']           = int(row['DUREE DU CREDIT'] > 360)  # >30 years = 60-month equivalent

    # Job stability -> employment length approximation
    stab = int(row['stabilite_profession'])
    emp_map = {0: 0.5, 1: 2.0, 2: 5.0, 3: 9.0}
    lc_row['emp_length_num']     = emp_map.get(stab, 5.0)
    lc_row['emp_length_unknown'] = 0.0

    # rejection_propensity -- fill with 0 (neutral)
    if 'rejection_propensity' in lc_row:
        lc_row['rejection_propensity'] = 0.0

    return pd.DataFrame([lc_row])


def map_to_ger(bna_features_df, ger_medians):
    """
    Build GER feature vector from BNA features + GER training medians.

    Parameters
    ----------
    bna_features_df : pd.DataFrame (1 row, 14 BNA features)
    ger_medians     : dict loaded from german/checkpoints/train_medians.joblib

    Returns
    -------
    pd.DataFrame (1 row, all GER features)
    """
    row = bna_features_df.iloc[0]

    # Start with training medians for all GER features
    ger_row = {k: float(v) for k, v in ger_medians.items()}

    # Overwrite with BNA equivalents
    ger_row['credit_amount'] = float(row['montant_credit'])
    ger_row['duration']      = float(row['DUREE DU CREDIT'])
    ger_row['age']           = float(row['AGE'])

    # Derived GER features from BNA data
    ger_row['log_credit']       = float(np.log1p(ger_row['credit_amount']))
    ger_row['credit_per_month'] = ger_row['credit_amount'] / max(ger_row['duration'], 1)

    # Job stability -> employment tier
    stab = int(row['stabilite_profession'])
    ger_row['employment'] = float(stab)  # 0-3 maps reasonably to GER employment ordinal

    # Family situation -> dependents
    dep = int(row['dependents_tier'])
    ger_row['personal_status_encoded'] = float(dep)

    return pd.DataFrame([ger_row])
