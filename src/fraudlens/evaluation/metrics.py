"""
Evaluation Metrics Module

Comprehensive evaluation with business-relevant metrics:
- Precision-Recall AUC (primary metric for imbalanced data)
- F1, Precision, Recall
- Confusion matrix
- PR curve plotting
"""

import logging
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)

from src.fraudlens.config import AVG_FRAUD_LOSS, REVIEW_COST

matplotlib.use("Agg")
logger = logging.getLogger(__name__)


class FraudEvaluator:
    """
    Evaluate fraud detection models with business-relevant metrics.

    Key design decisions:
    - PR-AUC is the primary metric (not ROC-AUC which is misleading on imbalanced data)
    - Threshold is optimized using a business cost function, not default 0.5
    - Confusion matrix is shown in both counts and dollar values
    """

    def __init__(
        self,
        avg_fraud_loss: float = AVG_FRAUD_LOSS,
        review_cost: float = REVIEW_COST,
    ) -> None:
        """
        Args:
            avg_fraud_loss: Average dollar loss per missed fraud (false negative)
            review_cost: Cost to manually review a flagged transaction (false positive)
        """
        self.avg_fraud_loss = avg_fraud_loss
        self.review_cost = review_cost

    def compute_metrics(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        threshold: float = 0.5,
    ) -> dict[str, Any]:
        """
        Compute standard ML metrics.

        Args:
            y_true: True labels
            y_proba: Predicted probabilities
            threshold: Decision threshold

        Returns:
            Dictionary with all standard metrics
        """
        y_pred = (y_proba >= threshold).astype(int)

        return {
            "pr_auc": round(average_precision_score(y_true, y_proba), 4),
            "roc_auc": round(roc_auc_score(y_true, y_proba), 4),
            "f1": round(f1_score(y_true, y_pred), 4),
            "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
            "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
            "threshold": round(threshold, 4),
            "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        }

    def evaluate_model(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        threshold: float | None = None,
        model_name: str = "model",
        business_cost: dict | None = None,
    ) -> dict[str, Any]:
        """
        Comprehensive model evaluation.

        Args:
            y_true: True labels
            y_proba: Predicted probabilities
            threshold: Decision threshold
            model_name: Name for logging
            business_cost: Pre-computed business cost (optional)

        Returns:
            Dictionary with all evaluation metrics
        """
        metrics = self.compute_metrics(y_true, y_proba, threshold or 0.5)

        results = {
            "model_name": model_name,
            **metrics,
            "business": business_cost or {},
        }

        logger.info("Evaluation: %s", model_name)
        logger.info(
            "  PR-AUC: %.4f | F1: %.4f | Precision: %.4f | Recall: %.4f",
            metrics["pr_auc"],
            metrics["f1"],
            metrics["precision"],
            metrics["recall"],
        )
        return results

    def compare_models(
        self,
        y_true: np.ndarray,
        predictions: dict[str, np.ndarray],
        thresholds: dict[str, float] | None = None,
        business_costs: dict[str, dict] | None = None,
    ) -> pd.DataFrame:
        """
        Compare multiple models side by side.

        Args:
            y_true: True labels
            predictions: Dict mapping model names to probability arrays
            thresholds: Dict mapping model names to optimal thresholds
            business_costs: Dict mapping model names to business cost results

        Returns:
            DataFrame with comparison metrics
        """
        rows = []
        for model_name, y_proba in predictions.items():
            t = (thresholds or {}).get(model_name, 0.5)
            metrics = self.compute_metrics(y_true, y_proba, t)
            biz = (business_costs or {}).get(model_name, {})

            rows.append(
                {
                    "Model": model_name,
                    "Threshold": metrics["threshold"],
                    "PR-AUC": metrics["pr_auc"],
                    "ROC-AUC": metrics["roc_auc"],
                    "F1": metrics["f1"],
                    "Precision": metrics["precision"],
                    "Recall": metrics["recall"],
                    "Net Benefit ($)": biz.get("net_benefit_usd", 0),
                    "Fraud Caught ($)": biz.get("fraud_caught_usd", 0),
                    "Missed Fraud ($)": biz.get("fraud_missed_usd", 0),
                }
            )

        comparison_df = pd.DataFrame(rows).sort_values("PR-AUC", ascending=False)
        logger.info("Model comparison:\n%s", comparison_df.to_string(index=False))
        return comparison_df

    def plot_precision_recall_curve(
        self,
        y_true: np.ndarray,
        predictions: dict[str, np.ndarray],
        save_path: str | None = None,
    ) -> plt.Figure:
        """
        Plot precision-recall curves for multiple models.

        Args:
            y_true: True labels
            predictions: Dict mapping model names to probability arrays
            save_path: Optional path to save the figure

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        for model_name, y_proba in predictions.items():
            precisions, recalls, _ = precision_recall_curve(y_true, y_proba)
            pr_auc = average_precision_score(y_true, y_proba)
            ax.plot(
                recalls,
                precisions,
                label=f"{model_name} (PR-AUC={pr_auc:.4f})",
                linewidth=2,
            )

        ax.set_xlabel("Recall", fontsize=12)
        ax.set_ylabel("Precision", fontsize=12)
        ax.set_title("Precision-Recall Curves", fontsize=14, fontweight="bold")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)

        baseline = y_true.sum() / len(y_true)
        ax.axhline(
            y=baseline,
            color="gray",
            linestyle="--",
            alpha=0.5,
            label=f"Random baseline ({baseline:.4f})",
        )

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            logger.info("PR curve saved to %s", save_path)
        return fig

    def plot_confusion_matrices(
        self,
        y_true: np.ndarray,
        predictions: dict[str, np.ndarray],
        top_n: int = 3,
        save_path: str | None = None,
    ) -> plt.Figure:
        """
        Plot confusion matrices for top N models.

        Args:
            y_true: True labels
            predictions: Dict mapping model names to probability arrays
            top_n: Number of top models to plot
            save_path: Optional path to save the figure
        """
        # Sort models by PR-AUC
        sorted_models = sorted(
            predictions.keys(),
            key=lambda m: average_precision_score(y_true, predictions[m]),
            reverse=True,
        )[:top_n]

        n = len(sorted_models)
        fig, axes = plt.subplots(1, n, figsize=(6 * n, 5))
        if n == 1:
            axes = [axes]

        for idx, model_name in enumerate(sorted_models):
            ax = axes[idx]
            y_pred = (predictions[model_name] >= 0.5).astype(int)
            cm = confusion_matrix(y_true, y_pred)

            sns.heatmap(
                cm,
                annot=True,
                fmt="d",
                cmap="Blues",
                ax=ax,
                xticklabels=["Legit", "Fraud"],
                yticklabels=["Legit", "Fraud"],
            )
            ax.set_title(f"{model_name}", fontsize=12, fontweight="bold")
            ax.set_xlabel("Predicted")
            ax.set_ylabel("Actual")

        plt.suptitle("Confusion Matrices", fontsize=14, fontweight="bold")
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
        return fig


def print_evaluation_summary(results: dict[str, Any]) -> str:
    """
    Format evaluation results as a readable string.
    """
    lines = [
        f"\n{'=' * 60}",
        f"  EVALUATION: {results['model_name']}",
        f"{'=' * 60}",
        f"  Threshold:       {results['threshold']:.4f}",
        f"  PR-AUC:          {results['pr_auc']:.4f}  <-- PRIMARY METRIC",
        f"  ROC-AUC:         {results['roc_auc']:.4f}",
        f"  F1 Score:        {results['f1']:.4f}",
        f"  Precision:       {results['precision']:.4f}",
        f"  Recall:          {results['recall']:.4f}",
        f"{'-' * 60}",
        "  BUSINESS IMPACT:",
        f"  Fraud Caught:    ${results['business']['fraud_caught_usd']:>10,.2f}",
        f"  Fraud Missed:    ${results['business']['fraud_missed_usd']:>10,.2f}",
        f"  Review Costs:    ${results['business']['review_costs_usd']:>10,.2f}",
        "  --------------------------------------------",
        f"  Net Benefit:     ${results['business']['net_benefit_usd']:>10,.2f}",
        f"{'=' * 60}",
    ]
    return "\n".join(lines)
