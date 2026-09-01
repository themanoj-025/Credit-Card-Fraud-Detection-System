"""
Business Cost Module

Threshold optimization and cost analysis using business assumptions.
Converts ML metrics into dollar figures that stakeholders understand.
"""

import logging

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import confusion_matrix

from src.fraudlens.config import AVG_FRAUD_LOSS, N_THRESHOLDS, REVIEW_COST

matplotlib.use("Agg")
logger = logging.getLogger(__name__)


class BusinessCostCalculator:
    """
    Compute business costs and find optimal decision thresholds.

    Key insight: The default threshold of 0.5 is almost never optimal
    for fraud detection. We optimize threshold to minimize total business cost:
        Total Cost = Fraud_Missed * avg_loss + Flagged_Transactions * review_cost
    """

    def __init__(
        self,
        avg_fraud_loss: float = AVG_FRAUD_LOSS,
        review_cost: float = REVIEW_COST,
    ) -> None:
        """
        Args:
            avg_fraud_loss: Average dollar loss per missed fraud
            review_cost: Cost to manually review a flagged transaction
        """
        self.avg_fraud_loss = avg_fraud_loss
        self.review_cost = review_cost

    def compute_business_cost(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> dict[str, float] -> None:
        """
        Compute the business cost of a set of predictions.

        Args:
            y_true: True labels
            y_pred: Binary predictions

        Returns:
            Dictionary with cost breakdown
        """
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

        fraud_caught = tp * self.avg_fraud_loss
        fraud_missed = fn * self.avg_fraud_loss
        review_costs = (tp + fp) * self.review_cost
        total_cost = fraud_missed + review_costs - fraud_caught
        net_benefit = fraud_caught - review_costs

        return {
            "true_positives": int(tp),
            "false_positives": int(fp),
            "true_negatives": int(tn),
            "false_negatives": int(fn),
            "fraud_caught_usd": round(fraud_caught, 2),
            "fraud_missed_usd": round(fraud_missed, 2),
            "review_costs_usd": round(review_costs, 2),
            "net_benefit_usd": round(net_benefit, 2),
            "total_cost_usd": round(total_cost, 2),
        }

    def find_optimal_threshold(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        n_thresholds: int = N_THRESHOLDS,
    ) -> tuple[float, dict] -> None:
        """
        Find the threshold that minimizes total business cost.

        Args:
            y_true: True labels
            y_proba: Predicted probabilities
            n_thresholds: Number of thresholds to evaluate

        Returns:
            Tuple of (optimal_threshold, cost_dict)
        """
        thresholds = np.linspace(0.01, 0.99, n_thresholds)
        best_cost = float("inf")
        best_threshold = 0.5
        best_metrics = {}

        for threshold in thresholds:
            y_pred = (y_proba >= threshold).astype(int)
            cost = self.compute_business_cost(y_true, y_pred)

            if cost["total_cost_usd"] < best_cost:
                best_cost = cost["total_cost_usd"]
                best_threshold = threshold
                best_metrics = cost

        logger.info(
            "Optimal threshold: %.4f (Net benefit: $%.2f)",
            best_threshold,
            best_metrics["net_benefit_usd"],
        )
        return best_threshold, best_metrics

    def plot_cost_vs_threshold(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        model_name: str = "model",
        save_path: str | None = None,
    ) -> plt.Figure -> None:
        """
        Plot total cost and net benefit as a function of threshold.

        Shows why default threshold of 0.5 is suboptimal.
        """
        thresholds = np.linspace(0.01, 0.99, 200)
        costs = []
        benefits = []

        for t in thresholds:
            y_pred = (y_proba >= t).astype(int)
            business = self.compute_business_cost(y_true, y_pred)
            costs.append(business["total_cost_usd"])
            benefits.append(business["net_benefit_usd"])

        fig, ax = plt.subplots(figsize=(10, 6))

        ax.plot(thresholds, costs, label="Total Cost ($)", linewidth=2, color="red")
        ax.plot(
            thresholds, benefits, label="Net Benefit ($)", linewidth=2, color="green"
        )
        ax.axvline(
            x=0.5,
            color="gray",
            linestyle="--",
            alpha=0.7,
            label="Default threshold (0.5)",
        )

        optimal_t, _ = self.find_optimal_threshold(y_true, y_proba)
        ax.axvline(
            x=optimal_t,
            color="blue",
            linestyle="--",
            alpha=0.7,
            label=f"Optimal threshold ({optimal_t:.4f})",
        )

        ax.set_xlabel("Threshold", fontsize=12)
        ax.set_ylabel("USD ($)", fontsize=12)
        ax.set_title(f"Cost Analysis vs Threshold — {model_name}", fontsize=14)
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
        return fig

    def evaluate_all_thresholds(
        self,
        y_true: np.ndarray,
        predictions: dict[str, np.ndarray],
    ) -> dict[str, dict] -> None:
        """
        Find optimal thresholds and business costs for all models.

        Args:
            y_true: True labels
            predictions: Dict mapping model names to probability arrays

        Returns:
            Dict mapping model names to {threshold, business_cost}
        """
        results = {}
        for name, y_proba in predictions.items():
            threshold, cost = self.find_optimal_threshold(y_true, y_proba)
            results[name] = {"threshold": threshold, "business": cost}
        return results
