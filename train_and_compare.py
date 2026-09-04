"""
FraudLens — Enhanced Training & Comparison Pipeline

Trains all ML algorithms, compares with detailed interactive-style charts,
auto-selects the best model, and saves artifacts for the API/dashboard.
"""

import json
import os
import sys
import time
import warnings

import joblib
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

warnings.filterwarnings("ignore")
matplotlib.use("Agg")

from src.fraudlens.config import (
    AVG_FRAUD_LOSS,
    MODELS_DIR,
    PROCESSED_DATA_DIR,
    REVIEW_COST,
)
from src.fraudlens.data.loaders import DataLoader
from src.fraudlens.data.preprocessing import FraudPreprocessor
from src.fraudlens.evaluation.business_cost import BusinessCostCalculator
from src.fraudlens.evaluation.metrics import FraudEvaluator
from src.fraudlens.models.anomaly import IsolationForestDetector
from src.fraudlens.models.model_selection import ModelSelector
from src.fraudlens.models.train import FraudTrainer

sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (12, 6)

os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

print("=" * 70)
print("  FRAUDLENS — Comprehensive ML Training & Comparison")
print("=" * 70)

# STAGE 1: Load and preprocess
print("\n[1/6] Loading and preprocessing data...")
df, stats = DataLoader().load(), None
loader = DataLoader()
df = loader.load()

preprocessor = FraudPreprocessor(test_size=0.2, random_state=42)
data = preprocessor.full_preprocess(df)
X_train, X_test = data["X_train"], data["X_test"]
y_train, y_test = data["y_train"], data["y_test"]

print(f"  Train: {len(X_train)} samples, Test: {len(X_test)} samples")
print(f"  Fraud in train: {y_train.sum()} ({y_train.mean() * 100:.4f}%)")

# STAGE 2: Train all models
print("\n[2/6] Training all ML models...")
trainer = FraudTrainer()
t_start = time.time()
models = trainer.train_all(X_train, y_train)

iso_detector = IsolationForestDetector(contamination=0.005, n_estimators=200)
iso_detector.fit(X_train, y_train)
t_total = time.time() - t_start

print(f"  Training completed in {t_total:.1f}s")
for name in models:
    print(f"    - {name}")
print("    - isolation_forest (unsupervised)")

# Save models
trainer.save_all_models(str(MODELS_DIR))
preprocessor.save_scaler(str(MODELS_DIR / "scaler.pkl"))
joblib.dump(iso_detector.model, MODELS_DIR / "anomaly_detector.pkl")

# STAGE 3: Evaluate
print("\n[3/6] Evaluating all models...")
evaluator = FraudEvaluator(avg_fraud_loss=AVG_FRAUD_LOSS, review_cost=REVIEW_COST)
cost_calc = BusinessCostCalculator(
    avg_fraud_loss=AVG_FRAUD_LOSS, review_cost=REVIEW_COST
)

predictions, thresholds, business_costs, timing = {}, {}, {}, {}

for name, model in models.items():
    t0 = time.time()
    y_proba = model.predict_proba(X_test)[:, 1]
    timing[name] = time.time() - t0
    predictions[name] = y_proba
    threshold, biz = cost_calc.find_optimal_threshold(y_test, y_proba)
    thresholds[name] = threshold
    business_costs[name] = biz

t0 = time.time()
iso_probas = iso_detector.predict_proba_as_fraud(X_test)
timing["isolation_forest"] = time.time() - t0
predictions["Isolation Forest"] = iso_probas
th_if, biz_if = cost_calc.find_optimal_threshold(y_test, iso_probas)
thresholds["Isolation Forest"] = th_if
business_costs["Isolation Forest"] = biz_if

comparison = evaluator.compare_models(y_test, predictions, thresholds, business_costs)
print("\n=== MODEL COMPARISON ===")
print(comparison.to_string(index=False))

# STAGE 4: Auto-Select Best Model
print("\n[4/6] Auto-selecting best model...")
all_models = {**models, "Isolation Forest": iso_detector.model}
selector = ModelSelector(metric="PR-AUC")
selection = selector.select(comparison, all_models)
selector.save_best_model(str(MODELS_DIR / "best_fraud_model.pkl"))
print(
    f"  Best: {selection['best_model_name']} (PR-AUC={selection['metric_value']:.4f})"
)

best_threshold = thresholds.get(selection["best_model_name"], 0.5)
with open(MODELS_DIR / "threshold.txt", "w") as f:
    f.write(str(best_threshold))

# STAGE 5: Generate Charts
print("\n[5/6] Generating comparison charts...")

fig, axes = plt.subplots(2, 3, figsize=(20, 12))
models_list = comparison["Model"].values
pr_aucs = comparison["PR-AUC"].values
net_benefits = comparison["Net Benefit ($)"].values
precisions = comparison["Precision"].values
recalls = comparison["Recall"].values
f1_scores = comparison["F1"].values

# Chart 1: PR Curves
ax = axes[0, 0]
for name, y_proba in predictions.items():
    from sklearn.metrics import average_precision_score, precision_recall_curve

    p, r, _ = precision_recall_curve(y_test, y_proba)
    ap = average_precision_score(y_test, y_proba)
    ax.plot(r, p, linewidth=2, label=f"{name} (AP={ap:.3f})")
ax.set_xlabel("Recall")
ax.set_ylabel("Precision")
ax.set_title("Precision-Recall Curves", fontsize=13, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# Chart 2: ROC Curves
ax = axes[0, 1]
from sklearn.metrics import roc_auc_score, roc_curve

for name, y_proba in predictions.items():
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    auc = roc_auc_score(y_test, y_proba)
    ax.plot(fpr, tpr, linewidth=2, label=f"{name} (AUC={auc:.3f})")
ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Random")
ax.set_xlabel("FPR")
ax.set_ylabel("TPR")
ax.set_title("ROC Curves", fontsize=13, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# Chart 3: PR-AUC Comparison
ax = axes[0, 2]
colors = plt.cm.RdYlGn(np.linspace(0.3, 0.9, len(models_list)))
bars = ax.barh(models_list, pr_aucs, color=colors)
ax.set_xlabel("PR-AUC")
ax.set_title("PR-AUC Comparison", fontsize=13, fontweight="bold")
for bar, val in zip(bars, pr_aucs):
    ax.text(
        val + 0.005,
        bar.get_y() + bar.get_height() / 2,
        f"{val:.4f}",
        va="center",
        fontsize=10,
    )
ax.set_xlim(0, max(pr_aucs) * 1.15)

# Chart 4: Business Impact
ax = axes[1, 0]
colors_biz = ["#38ef7d" if nb > 0 else "#ff416c" for nb in net_benefits]
bars = ax.barh(models_list, net_benefits, color=colors_biz)
ax.set_xlabel("Net Benefit ($)")
ax.set_title("Business Impact", fontsize=13, fontweight="bold")
for bar, val in zip(bars, net_benefits):
    ax.text(
        val + 100,
        bar.get_y() + bar.get_height() / 2,
        f"${val:,.0f}",
        va="center",
        fontsize=10,
    )

# Chart 5: Precision vs Recall
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
        fontsize=9,
    )
ax.set_xlabel("Recall")
ax.set_ylabel("Precision")
ax.set_title("Precision vs Recall", fontsize=13, fontweight="bold")
plt.colorbar(scatter, ax=ax, label="PR-AUC")
ax.grid(True, alpha=0.3)

# Chart 6: F1 Score
ax = axes[1, 2]
colors_f1 = plt.cm.viridis(np.linspace(0.3, 0.9, len(models_list)))
bars = ax.bar(range(len(models_list)), f1_scores, color=colors_f1)
ax.set_xticks(range(len(models_list)))
ax.set_xticklabels(models_list, rotation=45, ha="right")
ax.set_ylabel("F1 Score")
ax.set_title("F1 Score Comparison", fontsize=13, fontweight="bold")
for bar, val in zip(bars, f1_scores):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        val + 0.01,
        f"{val:.4f}",
        ha="center",
        fontsize=10,
    )

plt.suptitle("FraudLens — Model Comparison", fontsize=16, fontweight="bold", y=1.02)
plt.tight_layout()
plt.savefig(
    str(PROCESSED_DATA_DIR / "comprehensive_comparison.png"),
    dpi=150,
    bbox_inches="tight",
)
plt.close()
print("  [OK] Comprehensive comparison chart saved")

# STAGE 6: Summary
print("\n[6/6] Final Summary")
print("=" * 70)
print("  TRAINING COMPLETE")
print("=" * 70)
print(f"\n  Models Trained: {len(models) + 1}")
print(f"  Best Model:     {selection['best_model_name']}")
print(f"  PR-AUC:         {selection['metric_value']:.4f}")
print(f"  Threshold:      {best_threshold:.4f}")
biz = business_costs.get(selection["best_model_name"], {})
if biz:
    print("\n  Business Impact:")
    print(f"    Fraud Caught:  ${biz.get('fraud_caught_usd', 0):,.2f}")
    print(f"    Fraud Missed:  ${biz.get('fraud_missed_usd', 0):,.2f}")
    print(f"    Review Costs:  ${biz.get('review_costs_usd', 0):,.2f}")
    print(f"    Net Benefit:   ${biz.get('net_benefit_usd', 0):,.2f}")
print(f"\n  Charts saved to: {PROCESSED_DATA_DIR}")
print(f"  Models saved to: {MODELS_DIR}")
print("=" * 70)

# Save final results
final_results = {
    "best_model": selection["best_model_name"],
    "best_threshold": best_threshold,
    "metrics": {
        k: float(v)
        for k, v in comparison.iloc[0].items()
        if isinstance(v, (int, float))
    },
    "business": biz,
}
with open(PROCESSED_DATA_DIR / "final_results.json", "w") as f:
    json.dump(final_results, f, indent=2, default=str)
