"""Honest evaluation of FraudLens saved models on a held-out split of the real Kaggle dataset."""
import warnings

warnings.filterwarnings("ignore")

import joblib
import pandas as pd
import structlog
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger("evaluate_saved_models")

RANDOM_STATE = 42
TEST_SIZE = 0.2
FEATURES = [f"V{i}" for i in range(1, 29)] + ["Time", "Amount"]

df = pd.read_csv("data/raw/creditcard.csv")
logger.info("dataset_loaded", rows=len(df), fraud_rate=f"{100 * df['Class'].mean():.4f}%")

X = df[FEATURES].copy()
y = df["Class"].copy()
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
)

# Scale Time/Amount on train only (no leakage), matching the pipeline's SCALE_FEATURES
scaler = StandardScaler()
X_train[["Time", "Amount"]] = scaler.fit_transform(X_train[["Time", "Amount"]])
X_test[["Time", "Amount"]] = scaler.transform(X_test[["Time", "Amount"]])
logger.info("test_set", rows=len(X_test), fraud=int(y_test.sum()))

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
        logger.warning("model_skipped", model=name, error=str(exc))
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
logger.info("evaluation_results", table=res.to_string(index=False))
res.to_csv("reports/model_evaluation.csv", index=False)
logger.info("evaluation_saved", path="reports/model_evaluation.csv")
