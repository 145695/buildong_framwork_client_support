import pandas as pd, joblib, os

# Run this once locally from the repo root
lc_train  = pd.read_parquet('artifacts/lc/checkpoints/X_train.parquet')
ger_train = pd.read_parquet('artifacts/german/checkpoints/01_train.parquet')

joblib.dump(lc_train.median().to_dict(),  'artifacts/lc/checkpoints/train_medians.joblib')
joblib.dump(ger_train.median().to_dict(), 'artifacts/german/checkpoints/train_medians.joblib')

print('LC medians:',  len(lc_train.columns), 'features')
print('GER medians:', len(ger_train.columns), 'features')