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

warnings.filterwarnings("ignore")
matplotlib.use("Agg")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    print(f"  MLflow tracking: enabled (URI={MLFLOW_TRACKING_URI})")
except (ImportError, Exception) as e:
    HAS_MLFLOW = False
    print(f"  MLflow tracking: disabled ({e})")
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

print("=" * 70)
print("  FRAUDLENS — Rigorous Model Comparison Pipeline")
print("  Stage 4: 6 Supervised + 1 Unsupervised Model")
print("=" * 70)

# STAGE 1: Data Loading
print("\n" + "-" * 70)
print("  [1/6] Data Loading")
print("-" * 70)

loader = DataLoader()
try:
    df = loader.load()
except FileNotFoundError as e:
    print(f"\n  ❌ {e}")
    print("  Download from: https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud")
    print("  Place at: data/raw/creditcard.csv")
    sys.exit(1)

stats = loader.get_basic_stats()
for k, v in stats.items():
    print(f"    {k}: {v}")

# STAGE 2: Preprocessing
print("\n" + "-" * 70)
print("  [2/6] Preprocessing (No Data Leakage)")
print("-" * 70)

preprocessor = FraudPreprocessor(test_size=0.2, random_state=42)
data = preprocessor.full_preprocess(df)
X_train, X_test = data["X_train"], data["X_test"]
y_train, y_test = data["y_train"], data["y_test"]

print(
    f"    Train: {X_train.shape[0]} samples ({y_train.sum()} fraud, {y_train.mean() * 100:.4f}%)"
)
print(
    f"    Test:  {X_test.shape[0]} samples ({y_test.sum()} fraud, {y_test.mean() * 100:.4f}%)"
)

preprocessor.save_scaler(str(MODELS_DIR / "scaler.pkl"))

# STAGE 3: Resampling Comparison
print("\n" + "-" * 70)
print("  [3/6] Resampling Strategy Comparison")
print("-" * 70)

resampler = Resampler(random_state=42)
strategies = ["none", "random_under", "smote", "adasyn", "smote_tomek"]
resampled = resampler.compare_strategies(X_train, y_train, strategies)

for strat, (X_r, y_r) in resampled.items():
    print(
        f"    {strat:<20}: {len(X_r):>8} samples, {int(y_r.sum()):>5} fraud ({y_r.mean() * 100:.2f}%)"
    )

# STAGE 3.5: Hyperparameter Optimization (Optuna) — optional
print("\n" + "-" * 70)
print("  [3.5/6] Hyperparameter Optimization (Optuna)")
print("-" * 70)

custom_configs = {}
if HPO_ENABLED:
    hpo = HyperparameterOptimizer(n_trials=HPO_N_TRIALS, cv_folds=HPO_CV_FOLDS)
    if "xgboost" in HPO_MODELS:
        print("  Tuning XGBoost hyperparameters...")
        xgb_params = hpo.tune_xgboost(X_train, y_train)
        custom_configs["xgboost"] = {"params": xgb_params}
    if "lightgbm" in HPO_MODELS:
        print("  Tuning LightGBM hyperparameters...")
        lgb_params = hpo.tune_lightgbm(X_train, y_train)
        custom_configs["lightgbm"] = {"params": lgb_params}
else:
    print("  HPO disabled (set HPO_ENABLED=True to enable)")

# STAGE 4: Train All Models (6 Supervised + 2 Unsupervised)
print("\n" + "-" * 70)
print("  [4/6] Training All Models")
print("-" * 70)

t_start = time.time()

# 4a. Supervised models (with optional HPO-tuned params)
trainer = FraudTrainer(custom_configs=custom_configs if custom_configs else None)
models = trainer.train_all(X_train, y_train)

# 4b. Cross-validate supervised models
print("\n  Running 5-fold CV on supervised models...")
cv_results = trainer.cross_validate(X_train, y_train)
for name, result in cv_results.items():
    print(
        f"    {name:<22}: PR-AUC = {result['mean_score']:.4f} ± {result['std_score']:.4f}"
    )

# 4c. Isolation Forest (unsupervised, trained on legit only)
iso_detector = IsolationForestDetector(contamination=0.005, n_estimators=200)
iso_detector.fit(X_train, y_train)
iso_trained = iso_detector.model
print(f"    Isolation Forest{'':<9}: trained on legitimate transactions only")

t_train = time.time() - t_start
print(f"\n  Training completed in {t_train:.1f}s")
print(f"  Models trained: {len(models) + 1}")

# Save all model artifacts
trainer.save_all_models(str(MODELS_DIR))
joblib.dump(iso_trained, MODELS_DIR / "anomaly_detector.pkl")


# STAGE 5: Evaluation & Comparison
print("\n" + "-" * 70)
print("  [5/6] Evaluation & Comparison")
print("-" * 70)

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
    print(print_evaluation_summary(result))

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
print(print_evaluation_summary(result_if))

# Build comparison table
comparison = evaluator.compare_models(y_test, predictions, thresholds, business_costs)

print("\n=== FINAL MODEL COMPARISON (sorted by PR-AUC) ===")
print(comparison.to_string(index=False))

# Save comparison CSV to both locations
comparison.to_csv(REPORTS_DIR / "model_comparison_fraud.csv", index=False)
comparison.to_csv(PROCESSED_DATA_DIR / "model_comparison.csv", index=False)
print("\n  Comparison saved to:")
print("    reports/model_comparison_fraud.csv")
print("    data/processed/model_comparison.csv")

# STAGE 6: Auto-Select Best Model
print("\n" + "-" * 70)
print("  [6/6] Auto-Select Best Model + Generate Charts")
print("-" * 70)

selector = ModelSelector(metric="PR-AUC")
all_trained: dict[str, Any] = {**models, "Isolation Forest": iso_trained}

selection = selector.select(comparison, all_trained)
selector.save_best_model(str(MODELS_DIR / "best_fraud_model.pkl"))

print(f"\n  {selector.get_selection_summary()}")

# Save optimal threshold
best_threshold = thresholds.get(selection["best_model_name"], 0.5)
with open(MODELS_DIR / "threshold.txt", "w") as f:
    f.write(str(best_threshold))

# STAGE 7: Generate Comprehensive Charts
print("\n  Generating comparison charts...")

charts_dir = PROCESSED_DATA_DIR

# Chart 1: PR Curves Overlay
print("    PR Curves...")
evaluator.plot_precision_recall_curve(
    y_test,
    predictions,
    save_path=str(charts_dir / "pr_curves.png"),
)

# Chart 2: Cost vs Threshold
print("    Cost vs Threshold...")
best_name = selection["best_model_name"]
cost_calc.plot_cost_vs_threshold(
    y_test,
    predictions[best_name],
    model_name=best_name,
    save_path=str(charts_dir / "cost_vs_threshold.png"),
)

# Chart 3: Confusion Matrices (Top 3)
print("    Confusion Matrices...")
evaluator.plot_confusion_matrices(
    y_test,
    predictions,
    top_n=3,
    save_path=str(charts_dir / "confusion_matrices.png"),
)

# Chart 4: Multi-Panel Comparison
print("    Comprehensive comparison chart...")
fig, axes = plt.subplots(2, 3, figsize=(20, 12))

models_list = comparison["Model"].values
pr_aucs = comparison["PR-AUC"].values.astype(float)
net_benefits = comparison["Net Benefit ($)"].values.astype(float)
precisions = comparison["Precision"].values.astype(float)
recalls = comparison["Recall"].values.astype(float)
f1_scores = comparison["F1"].values.astype(float)

# Panel 1: PR Curves
ax = axes[0, 0]
for name, y_proba in predictions.items():
    from sklearn.metrics import average_precision_score, precision_recall_curve

    p, r, _ = precision_recall_curve(y_test, y_proba)
    ap = average_precision_score(y_test, y_proba)
    ax.plot(r, p, linewidth=2, label=f"{name} (AP={ap:.3f})")
ax.set_xlabel("Recall")
ax.set_ylabel("Precision")
ax.set_title("Precision-Recall Curves", fontsize=13, fontweight="bold")
ax.legend(fontsize=7, loc="lower left")
ax.grid(True, alpha=0.3)

# Panel 2: ROC Curves
ax = axes[0, 1]
from sklearn.metrics import roc_auc_score, roc_curve

for name, y_proba in predictions.items():
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    auc_score = roc_auc_score(y_test, y_proba)
    ax.plot(fpr, tpr, linewidth=2, label=f"{name} (AUC={auc_score:.3f})")
ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Random")
ax.set_xlabel("FPR")
ax.set_ylabel("TPR")
ax.set_title("ROC Curves", fontsize=13, fontweight="bold")
ax.legend(fontsize=7, loc="lower right")
ax.grid(True, alpha=0.3)

# Panel 3: PR-AUC Comparison
ax = axes[0, 2]
colors = plt.cm.RdYlGn(np.linspace(0.3, 0.9, len(models_list)))
bars = ax.barh(range(len(models_list)), pr_aucs, color=colors)
ax.set_yticks(range(len(models_list)))
ax.set_yticklabels(models_list, fontsize=10)
ax.set_xlabel("PR-AUC")
ax.set_title("PR-AUC (higher is better)", fontsize=13, fontweight="bold")
for bar, val in zip(bars, pr_aucs):
    ax.text(
        val + 0.005,
        bar.get_y() + bar.get_height() / 2,
        f"{val:.4f}",
        va="center",
        fontsize=9,
    )
ax.set_xlim(0, max(pr_aucs) * 1.15)

# Panel 4: Business Impact
ax = axes[1, 0]
colors_biz = ["#38ef7d" if nb > 0 else "#ff416c" for nb in net_benefits]
bars = ax.barh(range(len(models_list)), net_benefits, color=colors_biz)
ax.set_yticks(range(len(models_list)))
ax.set_yticklabels(models_list, fontsize=10)
ax.set_xlabel("Net Benefit ($)")
ax.set_title("Business Impact", fontsize=13, fontweight="bold")
for bar, val in zip(bars, net_benefits):
    ax.text(
        val + 100,
        bar.get_y() + bar.get_height() / 2,
        f"${val:,.0f}",
        va="center",
        fontsize=9,
    )

# Panel 5: Precision vs Recall Scatter
ax = axes[1, 1]
scatter = ax.scatter(
    recalls, precisions, s=200, c=pr_aucs, cmap="RdYlGn", edgecolors="black", zorder=5
)
for i, name in enumerate(models_list):
    ax.annotate(
        name,
        (recalls[i], precisions[i]),
        textcoords="offset points",
        xytext=(5, 5),
        fontsize=8,
    )
ax.set_xlabel("Recall")
ax.set_ylabel("Precision")
ax.set_title("Precision vs Recall", fontsize=13, fontweight="bold")
plt.colorbar(scatter, ax=ax, label="PR-AUC")
ax.grid(True, alpha=0.3)

# Panel 6: F1 Score
ax = axes[1, 2]
colors_f1 = plt.cm.viridis(np.linspace(0.3, 0.9, len(models_list)))
bars = ax.bar(range(len(models_list)), f1_scores, color=colors_f1)
ax.set_xticks(range(len(models_list)))
ax.set_xticklabels(models_list, rotation=45, ha="right", fontsize=9)
ax.set_ylabel("F1 Score")
ax.set_title("F1 Score", fontsize=13, fontweight="bold")
for bar, val in zip(bars, f1_scores):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        val + 0.01,
        f"{val:.4f}",
        ha="center",
        fontsize=9,
    )

plt.suptitle(
    "FraudLens — Comprehensive Model Comparison", fontsize=16, fontweight="bold", y=1.02
)
plt.tight_layout()
plt.savefig(
    str(charts_dir / "comprehensive_comparison.png"), dpi=150, bbox_inches="tight"
)
plt.close()

# FINAL SUMMARY
print("\n" + "=" * 70)
print("  PIPELINE COMPLETE — Summary")
print("=" * 70)
print(f"\n  Best Model:      {selection['best_model_name']}")
print(f"  PR-AUC:          {selection['metric_value']:.4f}")
print(f"  Threshold:       {best_threshold:.4f}")
print(
    f"  CV Score:        {cv_results.get(selection['best_model_name'], {}).get('mean_score', 'N/A')}"
)
print(f"  Selection:       {selection['reasoning']}")

biz = business_costs.get(selection["best_model_name"], {})
if biz:
    print("\n  Business Impact (Best Model):")
    print(f"    Fraud Caught:    ${biz.get('fraud_caught_usd', 0):,.2f}")
    print(f"    Fraud Missed:    ${biz.get('fraud_missed_usd', 0):,.2f}")
    print(f"    Review Costs:    ${biz.get('review_costs_usd', 0):,.2f}")
    print(f"    Net Benefit:     ${biz.get('net_benefit_usd', 0):,.2f}")

print("\n  Saved Artifacts:")
print("    Best model:       models/best_fraud_model.pkl")
print("    Anomaly detector: models/anomaly_detector.pkl")
print("    Threshold:        models/threshold.txt")
print("    Comparison CSV:   reports/model_comparison_fraud.csv")
print("    Charts:           data/processed/*.png")
print("=" * 70)

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
