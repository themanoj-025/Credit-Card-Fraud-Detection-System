"""
FraudLens — Full Model Comparison Pipeline (Stage 4)

Trains ALL candidate models with k-fold CV, compares with comprehensive
charts, auto-selects the best, and saves artifacts for the API/dashboard.

Models:
  Supervised: Logistic Regression, Random Forest, Gradient Boosting,
              XGBoost, LightGBM, CatBoost
  Unsupervised: Isolation Forest (anomaly detection)

Output:
  - models/best_fraud_model.pkl       (selected supervised best)
  - models/anomaly_detector.pkl       (Isolation Forest, always saved)
  - models/threshold.txt              (optimal decision threshold)
  - reports/model_comparison_fraud.csv
  - data/processed/comprehensive_comparison.png
  - data/processed/pr_curves.png
  - data/processed/confusion_matrices.png
  - data/processed/cost_vs_threshold.png
"""

import json
import os
import sys
import time
import warnings
from typing import Any

import joblib
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import structlog

warnings.filterwarnings("ignore")
matplotlib.use("Agg")

logger = structlog.get_logger("run_pipeline")

from src.fraudlens.config import (
    AVG_FRAUD_LOSS,
    HPO_CV_FOLDS,
    HPO_ENABLED,
    HPO_MODELS,
    HPO_N_TRIALS,
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_TRACKING_URI,
    MODELS_DIR,
    PROCESSED_DATA_DIR,
    REPORTS_DIR,
    REVIEW_COST,
)

# MLflow Experiment Tracking
try:
    import mlflow

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
    HAS_MLFLOW = True
    logger.info("mlflow_tracking", uri=MLFLOW_TRACKING_URI)
except (ImportError, Exception) as e:
    HAS_MLFLOW = False
    logger.warning("mlflow_tracking_disabled", error=str(e))
from src.fraudlens.data.loaders import DataLoader
from src.fraudlens.data.preprocessing import FraudPreprocessor, Resampler
from src.fraudlens.evaluation.business_cost import BusinessCostCalculator
from src.fraudlens.evaluation.metrics import FraudEvaluator, print_evaluation_summary
from src.fraudlens.models.anomaly import IsolationForestDetector
from src.fraudlens.models.hpo import HyperparameterOptimizer
from src.fraudlens.models.model_selection import ModelSelector
from src.fraudlens.models.train import FraudTrainer

sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (12, 6)

os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

logger.info("=" * 70)
logger.info("  FRAUDLENS — Rigorous Model Comparison Pipeline")
logger.info("  Stage 4: 6 Supervised + 1 Unsupervised Model")
logger.info("=" * 70)

# STAGE 1: Data Loading
logger.info("[1/6] Data Loading")

loader = DataLoader()
try:
    df = loader.load()
except FileNotFoundError as e:
    logger.error("data_not_found", error=str(e), download_url="https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud", place_at="data/raw/creditcard.csv")
    sys.exit(1)

stats = loader.get_basic_stats()
for k, v in stats.items():
    logger.info("data_stats", metric=k, value=v)

# STAGE 2: Preprocessing
logger.info("[2/6] Preprocessing (No Data Leakage)")

preprocessor = FraudPreprocessor(test_size=0.2, random_state=42)
data = preprocessor.full_preprocess(df)
X_train, X_test = data["X_train"], data["X_test"]
y_train, y_test = data["y_train"], data["y_test"]

logger.info("train_split", samples=X_train.shape[0], fraud=int(y_train.sum()), fraud_rate=f"{y_train.mean() * 100:.4f}%")
logger.info("test_split", samples=X_test.shape[0], fraud=int(y_test.sum()), fraud_rate=f"{y_test.mean() * 100:.4f}%")

preprocessor.save_scaler(str(MODELS_DIR / "scaler.pkl"))

# STAGE 3: Resampling Comparison
logger.info("[3/6] Resampling Strategy Comparison")

resampler = Resampler(random_state=42)
strategies = ["none", "random_under", "smote", "adasyn", "smote_tomek"]
resampled = resampler.compare_strategies(X_train, y_train, strategies)

for strat, (X_r, y_r) in resampled.items():
    logger.info("resampling_strategy", strategy=strat, samples=len(X_r), fraud=int(y_r.sum()), fraud_rate=f"{y_r.mean() * 100:.2f}%")

# STAGE 3.5: Hyperparameter Optimization (Optuna) — optional
logger.info("[3.5/6] Hyperparameter Optimization (Optuna)")

custom_configs = {}
if HPO_ENABLED:
    hpo = HyperparameterOptimizer(n_trials=HPO_N_TRIALS, cv_folds=HPO_CV_FOLDS)
    if "xgboost" in HPO_MODELS:
        logger.info("tuning_xgboost")
        xgb_params = hpo.tune_xgboost(X_train, y_train)
        custom_configs["xgboost"] = {"params": xgb_params}
    if "lightgbm" in HPO_MODELS:
        logger.info("tuning_lightgbm")
        lgb_params = hpo.tune_lightgbm(X_train, y_train)
        custom_configs["lightgbm"] = {"params": lgb_params}
else:
    logger.info("hpo_disabled")

# STAGE 4: Train All Models (6 Supervised + 2 Unsupervised)
logger.info("[4/6] Training All Models")

t_start = time.time()

# 4a. Supervised models (with optional HPO-tuned params)
trainer = FraudTrainer(custom_configs=custom_configs if custom_configs else None)
models = trainer.train_all(X_train, y_train)

# 4b. Cross-validate supervised models
logger.info("running_5fold_cv")
cv_results = trainer.cross_validate(X_train, y_train)
for name, result in cv_results.items():
    logger.info("cv_result", model=name, pr_auc=round(result['mean_score'], 4), std=round(result['std_score'], 4))

# 4c. Isolation Forest (unsupervised, trained on legit only)
iso_detector = IsolationForestDetector(contamination=0.005, n_estimators=200)
iso_detector.fit(X_train, y_train)
iso_trained = iso_detector.model
logger.info("isolation_forest_trained")

t_train = time.time() - t_start
logger.info("training_completed", elapsed_s=round(t_train, 1), models_trained=len(models) + 1)

# Save all model artifacts
trainer.save_all_models(str(MODELS_DIR))
joblib.dump(iso_trained, MODELS_DIR / "anomaly_detector.pkl")


# STAGE 5: Evaluation & Comparison
logger.info("[5/6] Evaluation & Comparison")

evaluator = FraudEvaluator(avg_fraud_loss=AVG_FRAUD_LOSS, review_cost=REVIEW_COST)
cost_calc = BusinessCostCalculator(
    avg_fraud_loss=AVG_FRAUD_LOSS, review_cost=REVIEW_COST
)

predictions: dict[str, np.ndarray] = {}
thresholds: dict[str, float] = {}
business_costs: dict[str, dict] = {}

# Evaluate supervised models
for name, model in models.items():
    y_proba = model.predict_proba(X_test)[:, 1]
    predictions[name] = y_proba
    threshold, biz_cost = cost_calc.find_optimal_threshold(y_test, y_proba)
    thresholds[name] = threshold
    business_costs[name] = biz_cost
    result = evaluator.evaluate_model(
        y_test, y_proba, threshold=threshold, model_name=name, business_cost=biz_cost
    )
    logger.info("model_evaluated", model=name, summary=print_evaluation_summary(result))

# Evaluate Isolation Forest
iso_probas = iso_detector.predict_proba_as_fraud(X_test)
predictions["Isolation Forest"] = iso_probas
th_if, biz_if = cost_calc.find_optimal_threshold(y_test, iso_probas)
thresholds["Isolation Forest"] = th_if
business_costs["Isolation Forest"] = biz_if
result_if = evaluator.evaluate_model(
    y_test,
    iso_probas,
    threshold=th_if,
    model_name="Isolation Forest",
    business_cost=biz_if,
)
logger.info("isolation_forest_evaluated", summary=print_evaluation_summary(result_if))

# Build comparison table
comparison = evaluator.compare_models(y_test, predictions, thresholds, business_costs)

logger.info("final_model_comparison", table=comparison.to_string(index=False))

# Save comparison CSV to both locations
comparison.to_csv(REPORTS_DIR / "model_comparison_fraud.csv", index=False)
comparison.to_csv(PROCESSED_DATA_DIR / "model_comparison.csv", index=False)
logger.info("comparison_saved", reports=str(REPORTS_DIR / "model_comparison_fraud.csv"), processed=str(PROCESSED_DATA_DIR / "model_comparison.csv"))

# STAGE 6: Auto-Select Best Model
logger.info("[6/6] Auto-Select Best Model + Generate Charts")

selector = ModelSelector(metric="PR-AUC")
all_trained: dict[str, Any] = {**models, "Isolation Forest": iso_trained}

selection = selector.select(comparison, all_trained)
selector.save_best_model(str(MODELS_DIR / "best_fraud_model.pkl"))

logger.info("model_selection", summary=selector.get_selection_summary())

# Save optimal threshold
best_threshold = thresholds.get(selection["best_model_name"], 0.5)
with open(MODELS_DIR / "threshold.txt", "w") as f:
    f.write(str(best_threshold))

# STAGE 7: Generate Comprehensive Charts
logger.info("generating_charts")

from pipeline_charts import plot_comprehensive_comparison

charts_dir = PROCESSED_DATA_DIR

# Individual charts
evaluator.plot_precision_recall_curve(y_test, predictions, save_path=str(charts_dir / "pr_curves.png"))
cost_calc.plot_cost_vs_threshold(y_test, predictions[selection["best_model_name"]], model_name=selection["best_model_name"], save_path=str(charts_dir / "cost_vs_threshold.png"))
evaluator.plot_confusion_matrices(y_test, predictions, top_n=3, save_path=str(charts_dir / "confusion_matrices.png"))

# Multi-panel comparison chart
logger.info("comprehensive_comparison_chart")
plot_comprehensive_comparison(comparison, predictions, y_test, str(charts_dir))

# FINAL SUMMARY
logger.info("=" * 70)
logger.info("  PIPELINE COMPLETE — Summary")
logger.info("=" * 70)
logger.info("best_model", name=selection['best_model_name'], pr_auc=round(selection['metric_value'], 4), threshold=round(best_threshold, 4))
cv_score = cv_results.get(selection['best_model_name'], {}).get('mean_score', 'N/A')
cv_std = cv_results.get(selection['best_model_name'], {}).get('std_score', 'N/A')
logger.info("cv_score", mean=cv_score, std=cv_std)
logger.info("selection_reasoning", reasoning=selection['reasoning'])

biz = business_costs.get(selection["best_model_name"], {})
if biz:
    logger.info("business_impact", fraud_caught_usd=biz.get('fraud_caught_usd', 0), fraud_missed_usd=biz.get('fraud_missed_usd', 0), review_costs_usd=biz.get('review_costs_usd', 0), net_benefit_usd=biz.get('net_benefit_usd', 0))

logger.info("saved_artifacts", best_model="models/best_fraud_model.pkl", anomaly_detector="models/anomaly_detector.pkl", threshold="models/threshold.txt", comparison_csv="reports/model_comparison_fraud.csv", charts="data/processed/*.png")
logger.info("=" * 70)

# Save summary JSON
final_results = {
    "best_model": selection["best_model_name"],
    "best_threshold": best_threshold,
    "cv_score": cv_results.get(selection["best_model_name"], {}).get("mean_score"),
    "cv_std": cv_results.get(selection["best_model_name"], {}).get("std_score"),
    "metrics": {
        "pr_auc": float(comparison.iloc[0]["PR-AUC"]),
        "f1": float(comparison.iloc[0]["F1"]),
        "precision": float(comparison.iloc[0]["Precision"]),
        "recall": float(comparison.iloc[0]["Recall"]),
    },
    "business": biz,
    "selection_reasoning": selection["reasoning"],
}
with open(REPORTS_DIR / "final_results.json", "w") as f:
    json.dump(final_results, f, indent=2, default=str)
