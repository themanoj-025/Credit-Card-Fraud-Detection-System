"""
Model Selection Module

Auto-selects the best model from a comparison table using a documented,
overridable rule. Saves the selected model and logs the winner + reasoning.
"""

import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.fraudlens.config import (
    MLFLOW_EXPERIMENT_NAME,
    MODEL_SELECTION_METRIC,
    MODELS_DIR,
    SELECTION_RULE_DESCRIPTION,
)

logger = logging.getLogger(__name__)

# MLflow setup
try:
    import mlflow

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


class ModelSelector:
    """
    Auto-select the best model using a documented, overridable rule.

    Default behavior: select model with highest PR-AUC score.
    """

    def __init__(
        self,
        metric: str = MODEL_SELECTION_METRIC,
        higher_is_better: bool = True,
    ) -> None:
        """
        Args:
            metric: Column name in comparison DataFrame to optimize
            higher_is_better: Whether higher metric values are better
        """
        self.metric = metric
        self.higher_is_better = higher_is_better
        self.selection_result: dict[str, Any] | None = None

    def select(
        self,
        comparison_df: pd.DataFrame,
        trained_models: dict[str, Any],
    ) -> dict[str, Any] -> None:
        """
        Select the best model from a comparison table.

        Args:
            comparison_df: DataFrame with model comparison metrics
            trained_models: Dict of {model_name: trained_model_object}

        Returns:
            Dictionary with selection results:
            - best_model_name: str
            - best_model: trained model object
            - metric_used: str
            - metric_value: float
            - reasoning: str
            - ranking: DataFrame of all models sorted by metric

        Raises:
            ValueError: If metric column not found in comparison table
        """
        if self.metric not in comparison_df.columns:
            raise ValueError(
                f"Metric '{self.metric}' not found in comparison table. "
                f"Available: {list(comparison_df.columns)}"
            )

        # Sort by metric
        sorted_df = comparison_df.sort_values(
            by=self.metric, ascending=not self.higher_is_better
        ).reset_index(drop=True)

        best_name = sorted_df.iloc[0]["Model"]
        best_value = sorted_df.iloc[0][self.metric]

        # Get reasoning
        reason_parts = [
            SELECTION_RULE_DESCRIPTION,
            (f"Among {len(sorted_df)} models, '{best_name}' achieved the "
            f"highest {self.metric} ({best_value:.4f})."),
        ]

        # Add runner-up context
        if len(sorted_df) > 1:
            second_value = sorted_df.iloc[1][self.metric]
            delta = best_value - second_value
            if self.higher_is_better:
                reason_parts.append(
                    f"This is {delta:.4f} higher than the runner-up "
                    f"('{sorted_df.iloc[1]['Model']}', {second_value:.4f})."
                )
            else:
                reason_parts.append(
                    f"This is {abs(delta):.4f} lower than the runner-up "
                    f"('{sorted_df.iloc[1]['Model']}', {second_value:.4f})."
                )

        reasoning = " ".join(reason_parts)

        # Get the model object
        best_model = trained_models.get(best_name)
        if best_model is None:
            raise KeyError(
                f"Best model '{best_name}' not found in trained_models dict."
            )

        self.selection_result = {
            "best_model_name": best_name,
            "best_model": best_model,
            "metric_used": self.metric,
            "metric_value": float(best_value),
            "reasoning": reasoning,
            "ranking": sorted_df,
        }

        logger.info(
            "Selected best model: %s (%s=%.4f)", best_name, self.metric, best_value
        )
        logger.info("Reasoning: %s", reasoning)

        # Tag the winning model's MLflow run
        self._tag_winning_model_mlflow(best_name, best_value, reasoning)

        return self.selection_result

    def save_best_model(self, path: str | None = None) -> str:
        """
        Save the selected best model to disk.

        Args:
            path: Save path (default: models/best_fraud_model.pkl)

        Returns:
            Path where model was saved
        """
        if self.selection_result is None:
            raise ValueError("No selection result. Call select() first.")

        if path is None:
            path = str(MODELS_DIR / "best_fraud_model.pkl")

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.selection_result["best_model"], path)
        logger.info("Best model saved to %s", path)
        return path

    def _tag_winning_model_mlflow(
        self, best_name: str, best_value: float, reasoning: str
    ) -> None:
        """Tag the winning model's MLflow run for easy identification in the UI."""
        if not MLFLOW_AVAILABLE:
            return
        try:
            mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
            # Find the MLflow run by custom 'run_name' tag (set in train.py during training)
            experiment = mlflow.get_experiment_by_name(MLFLOW_EXPERIMENT_NAME)
            if experiment:
                runs = mlflow.search_runs(
                    experiment_ids=[experiment.experiment_id],
                    filter_string=f"tags.run_name = '{best_name}'",
                )
                if not runs.empty:
                    run_id = runs.iloc[0]["run_id"]
                    with mlflow.start_run(run_id=run_id):
                        mlflow.set_tag("selected", "true")
                        mlflow.set_tag("selection_metric", self.metric)
                        mlflow.set_tag("selection_value", str(round(best_value, 4)))
                        mlflow.set_tag("selection_reasoning", reasoning[:200])
                    logger.info("  MLflow run '%s' tagged as selected:true", best_name)
        except (RuntimeError, ValueError) as e:
            logger.warning("  MLflow tagging failed for winning model: %s", e)

    def get_selection_summary(self) -> str:
        """Get a human-readable summary of the selection."""
        if self.selection_result is None:
            return "No model selected yet."

        r = self.selection_result
        return (
            f"Best Model: {r['best_model_name']}\n"
            f"Selection Metric: {r['metric_used']}\n"
            f"Metric Value: {r['metric_value']:.4f}\n"
            f"Reasoning: {r['reasoning']}"
        )
