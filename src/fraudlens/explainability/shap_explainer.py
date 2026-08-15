"""
SHAP Explainability Module

Pure SHAP explanation computation — no prediction logic.
Extracted from the original FraudPredictor to respect SRP.

Usage:
    explainer = ShapExplainer()
    explainer.init_explainer(model, feature_names)
    explanation = explainer.explain(X_processed, transaction)
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
import shap

from src.fraudlens.common.enums import ShapImpact
from src.fraudlens.config import MAX_SHAP_FEATURES, N_SHAP_BACKGROUND_SAMPLES

logger = logging.getLogger(__name__)


class ShapExplanation:
    """Typed container for a SHAP explanation result."""

    def __init__(
        self,
        summary: str,
        top_features: list[dict[str, Any]],
    ) -> None:
        self.summary = summary
        self.top_features = top_features

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "top_features": self.top_features,
        }

    @staticmethod
    def from_raw(
        top_features: list[tuple[str, float]],
        raw_transaction: dict[str, Any],
        max_features: int = 10,
    ) -> "ShapExplanation":
        """Create a ShapExplanation from raw feature importance tuples."""
        top = top_features[:max_features]
        features = [
            {
                "feature": feat,
                "value": round(float(raw_transaction.get(feat, 0)), 4),
                "shap_value": round(float(val), 4),
                "impact": (
                    ShapImpact.INCREASES.value
                    if val > 0
                    else ShapImpact.DECREASES.value
                ),
            }
            for feat, val in top
        ]
        summary = _format_explanation_text(top)
        return ShapExplanation(summary=summary, top_features=features)


class ShapExplainer:
    """
    Compute SHAP explanations for fraud predictions.

    Pure computation — no model loading, no I/O.
    Handles TreeExplainer vs KernelExplainer dispatch.
    """

    def __init__(self, max_features: int = MAX_SHAP_FEATURES) -> None:
        """
        Args:
            max_features: Max features to include in explanation
        """
        self.max_features = max_features
        self.explainer = None
        self._initialized = False

    def init_explainer(
        self,
        model: object,
        feature_names: list[str],
        X_background: pd.DataFrame | None = None,
    ) -> None:
        """
        Initialize the appropriate SHAP explainer based on model type.

        Args:
            model: Trained ML model
            feature_names: Feature names for the model
            X_background: Optional background data for KernelExplainer
        """
        model_type = type(model).__name__

        if hasattr(model, "feature_importances_") or any(
            t in model_type for t in ["XGB", "LGBM", "Forest", "GradientBoosting"]
        ):
            logger.info("Using TreeExplainer for %s", model_type)
            self.explainer = shap.TreeExplainer(model)
        else:
            logger.info("Using KernelExplainer for %s", model_type)
            bg = (
                X_background
                if X_background is not None
                else pd.DataFrame(
                    np.zeros((100, len(feature_names))),
                    columns=feature_names,
                )
            )
            self.explainer = shap.KernelExplainer(
                model.predict_proba,
                shap.kmeans(bg, N_SHAP_BACKGROUND_SAMPLES),
            )

        self._initialized = True

    def explain(
        self,
        X_processed: pd.DataFrame,
        feature_names: list[str],
        raw_transaction: dict[str, Any],
    ) -> ShapExplanation:
        """
        Compute SHAP explanation for a transaction.

        Args:
            X_processed: Preprocessed feature vector
            feature_names: Feature names
            raw_transaction: Original raw transaction dict

        Returns:
            ShapExplanation with summary and top features

        Raises:
            RuntimeError: If explainer not initialized
        """
        if not self._initialized or self.explainer is None:
            raise RuntimeError(
                "Explainer not initialized. Call init_explainer() first."
            )

        shap_values = self.explainer.shap_values(X_processed)
        shap_vals = _extract_positive_class_values(shap_values, idx=0)

        feature_importance = list(zip(feature_names, shap_vals))
        feature_importance.sort(key=lambda x: abs(x[1]), reverse=True)

        return ShapExplanation.from_raw(
            feature_importance, raw_transaction, self.max_features
        )

    def global_importance(
        self,
        X_sample: pd.DataFrame,
        feature_names: list[str],
    ) -> pd.DataFrame:
        """
        Compute global feature importance using SHAP.

        Args:
            X_sample: Sample of data to compute SHAP values over
            feature_names: Feature names

        Returns:
            DataFrame with feature importances sorted by magnitude
        """
        if not self._initialized or self.explainer is None:
            raise RuntimeError(
                "Explainer not initialized. Call init_explainer() first."
            )

        shap_values = self.explainer.shap_values(X_sample)
        shap_vals = _extract_positive_class_global(shap_values)

        importance = pd.DataFrame(
            {
                "feature": feature_names,
                "mean_abs_shap": np.abs(shap_vals).mean(axis=0),
                "mean_shap": shap_vals.mean(axis=0),
            }
        ).sort_values("mean_abs_shap", ascending=False)

        return importance


# Internal helpers


def _extract_positive_class_values(shap_values, idx: int = 0):
    """Extract SHAP values for the positive (fraud) class."""
    if isinstance(shap_values, list):
        return shap_values[1][idx]
    elif hasattr(shap_values, "shape") and len(shap_values.shape) == 3:
        return shap_values[idx, :, 1]
    else:
        return shap_values[idx]


def _extract_positive_class_global(shap_values):
    """Extract global SHAP values for the positive class."""
    if isinstance(shap_values, list):
        return shap_values[1]
    elif hasattr(shap_values, "shape") and len(shap_values.shape) == 3:
        return shap_values[:, :, 1]
    else:
        return shap_values


def _format_explanation_text(top_features: list[tuple[str, float]]) -> str:
    """Format top features into a human-readable explanation string."""
    increases = [(f, v) for f, v in top_features if v > 0]
    decreases = [(f, v) for f, v in top_features if v < 0]

    parts = []
    if increases:
        feats = ", ".join(f for f, _ in increases[:3])
        parts.append(f"Flagged mainly due to: {feats}")
    if decreases:
        feats = ", ".join(f for f, _ in decreases[:3])
        parts.append(f"Mitigated by: {feats}")

    return " | ".join(parts) if parts else "No strong individual feature drivers"
