"""Honest evaluation of FraudLens saved models on a held-out split of the real Kaggle dataset."""
import warnings

warnings.filterwarnings("ignore")

import joblib
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

RANDOM_STATE = 42
TEST_SIZE = 0.2
FEATURES = [f"V{i}" for i in range(1, 29)] + ["Time", "Amount"]

df = pd.read_csv("data/raw/creditcard.csv")
print("dataset rows:", len(df), "| fraud rate: %.4f%%" % (100 * df["Class"].mean()))

X = df[FEATURES].copy()
y = df["Class"].copy()
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
)

# Scale Time/Amount on train only (no leakage), matching the pipeline's SCALE_FEATURES
scaler = StandardScaler()
X_train[["Time", "Amount"]] = scaler.fit_transform(X_train[["Time", "Amount"]])
X_test[["Time", "Amount"]] = scaler.transform(X_test[["Time", "Amount"]])
print("test set rows:", len(X_test), "| fraud in test:", int(y_test.sum()))

models = {
    "best_fraud_model": "models/best_fraud_model.pkl",
    "XGBoost": "models/xgboost.pkl",
    "LightGBM": "models/lightgbm.pkl",
    "Random Forest": "models/random_forest.pkl",
    "Logistic Regression": "models/logistic_regression.pkl",
    "Gradient Boosting": "models/gradient_boosting.pkl",
    "CatBoost": "models/catboost.pkl",
}

rows = []
for name, path in models.items():
    try:
        model = joblib.load(path)
        proba = model.predict_proba(X_test)[:, 1]
    except (FileNotFoundError, ValueError, OSError) as exc:  # missing dependency or artifact
        print(f"SKIP {name}: {exc}")
        continue
    pred = (proba >= 0.5).astype(int)
    rows.append({
        "Model": name,
        "Precision@0.5": round(precision_score(y_test, pred), 4),
        "Recall@0.5": round(recall_score(y_test, pred), 4),
        "F1@0.5": round(f1_score(y_test, pred), 4),
        "PR-AUC": round(average_precision_score(y_test, proba), 4),
        "ROC-AUC": round(roc_auc_score(y_test, proba), 4),
    })

res = pd.DataFrame(rows).sort_values("PR-AUC", ascending=False)
pd.set_option("display.width", 200)
print(res.to_string(index=False))
res.to_csv("reports/model_evaluation.csv", index=False)
print("saved -> reports/model_evaluation.csv")
