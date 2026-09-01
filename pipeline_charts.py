"""Chart generation for the model comparison pipeline."""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from pandas import DataFrame
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

matplotlib.use("Agg")
plt.rcParams["figure.figsize"] = (12, 6)


def plot_comprehensive_comparison(
    comparison: DataFrame,
    predictions: dict[str, np.ndarray],
    y_test: np.ndarray,
    charts_dir: str,
) -> None:
    """Generate the 6-panel comprehensive comparison chart."""
    _fig, axes = plt.subplots(2, 3, figsize=(20, 12))

    models_list = comparison["Model"].values
    pr_aucs = comparison["PR-AUC"].values.astype(float)
    net_benefits = comparison["Net Benefit ($)"].values.astype(float)
    precisions = comparison["Precision"].values.astype(float)
    recalls = comparison["Recall"].values.astype(float)
    f1_scores = comparison["F1"].values.astype(float)

    # Panel 1: PR Curves
    ax = axes[0, 0]
    for name, y_proba in predictions.items():
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
        ax.text(val + 0.005, bar.get_y() + bar.get_height() / 2, f"{val:.4f}", va="center", fontsize=9)
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
        ax.text(val + 100, bar.get_y() + bar.get_height() / 2, f"${val:,.0f}", va="center", fontsize=9)

    # Panel 5: Precision vs Recall Scatter
    ax = axes[1, 1]
    scatter = ax.scatter(recalls, precisions, s=200, c=pr_aucs, cmap="RdYlGn", edgecolors="black", zorder=5)
    for i, name in enumerate(models_list):
        ax.annotate(name, (recalls[i], precisions[i]), textcoords="offset points", xytext=(5, 5), fontsize=8)
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
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.01, f"{val:.4f}", ha="center", fontsize=9)

    plt.suptitle("FraudLens — Comprehensive Model Comparison", fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(f"{charts_dir}/comprehensive_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()
