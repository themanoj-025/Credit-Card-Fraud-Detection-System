"""
SHAP Explainability Module

Prediction pipeline with SHAP-based explanations.
Returns not just "fraud: 92%" but "flagged mainly due to V14, V4, V12"
— exactly what real fraud analysts need.
"""

import logging
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap

from src.fraudlens.config import (
    ALL_FEATURES,
    MAX_SHAP_FEATURES,
    MODELS_DIR,
    N_SHAP_BACKGROUND_SAMPLES,
    SCALE_FEATURES,
)

logger = logging.getLogger(__name__)


class FraudPredictor:
    """
    Prediction pipeline with SHAP explanations.

    Provides per-transaction interpretability so fraud analysts
    can understand *why* a transaction was flagged.
    """

    def __init__(
        self,
        model=None,
        scaler=None,
        feature_names: list[str] | None = None,
        threshold: float = 0.5,
        max_shap_features: int = MAX_SHAP_FEATURES,
    ) -> None:
        """
        Args:
            model: Trained model with predict_proba
            scaler: Fitted StandardScaler
            feature_names: List of feature names (default from config)
            threshold: Classification threshold
            max_shap_features: Max features to include in SHAP explanation
        """
        self.model = model
        self.scaler = scaler
        self.feature_names = feature_names or ALL_FEATURES
        self.threshold = threshold
        self.max_shap_features = max_shap_features
        self.explainer = None
        self._shap_initialized = False

    def load_model(self, model_path: str) -> "FraudPredictor":
        """Load a model from disk."""
        self.model = joblib.load(model_path)
        logger.info("Model loaded from %s", model_path)
        return self

    def load_scaler(self, scaler_path: str) -> "FraudPredictor":
        """Load a scaler from disk."""
        self.scaler = joblib.load(scaler_path)
        logger.info("Scaler loaded from %s", scaler_path)
        return self

    def load_from_config(self) -> "FraudPredictor":
        """Load model and scaler from default paths defined in config."""
        model_path = MODELS_DIR / "best_fraud_model.pkl"
        scaler_path = MODELS_DIR / "scaler.pkl"
        self.load_model(str(model_path))
        self.load_scaler(str(scaler_path))
        return self

    def _init_shap_explainer(self, X_background: pd.DataFrame | None = None) -> None:
        """Initialize the SHAP explainer based on model type."""
        if self._shap_initialized or self.model is None:
            return

        model_type = type(self.model).__name__

        if hasattr(self.model, "feature_importances_") or any(
            t in model_type for t in ["XGB", "LGBM", "Forest", "GradientBoosting"]
        ):
            logger.info("Using TreeExplainer for %s", model_type)
            self.explainer = shap.TreeExplainer(self.model)
        else:
            logger.info("Using KernelExplainer for %s", model_type)
            bg = shap.kmeans(
                (
                    X_background
                    if X_background is not None
                    else pd.DataFrame(
                        np.zeros((100, len(self.feature_names))),
                        columns=self.feature_names,
                    )
                ),
                N_SHAP_BACKGROUND_SAMPLES,
            )
            self.explainer = shap.KernelExplainer(self.model.predict_proba, bg)

        self._shap_initialized = True

    def preprocess(self, X: pd.DataFrame) -> pd.DataFrame:
        """Preprocess input features (scale if scaler available)."""
        if self.scaler is not None:
            X_scaled = X.copy()
            available = [c for c in SCALE_FEATURES if c in X_scaled.columns]
            if available:
                X_scaled[available] = self.scaler.transform(X_scaled[available])
            return X_scaled
        return X

    def predict_single(
        self,
        transaction: dict[str, Any],
        return_shap: bool = True,
        X_background: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        """
        Predict fraud for a single transaction with explanation.

        Args:
            transaction: Dictionary of feature values
            return_shap: Whether to compute SHAP explanations
            X_background: Background data for SHAP

        Returns:
            Dictionary with prediction, probability, and explanation
        """
        X = pd.DataFrame([transaction])[self.feature_names]
        X_processed = self.preprocess(X)

        fraud_proba = float(self.model.predict_proba(X_processed)[0][1])
        is_fraud = fraud_proba >= self.threshold
        decision = "FRAUD" if is_fraud else "LEGITIMATE"

        result = {
            "fraud_probability": round(fraud_proba, 4),
            "decision": decision,
            "threshold_used": self.threshold,
            "is_fraud": bool(is_fraud),
        }

        if return_shap:
            result["explanation"] = self._compute_shap_explanation(
                X_processed, transaction
            )

        return result

    @staticmethod
    def _extract_shap_values(shap_values, idx: int = 0) -> Any:
        """Extract SHAP values for the positive class, handling different SHAP output shapes."""
        # Newer SHAP (TreeExplainer) returns shape (n_samples, n_features, n_classes) for multi-class
        # Older SHAP returns list of arrays [neg_class_vals, pos_class_vals]
        if isinstance(shap_values, list):
            # List format: [negative_class_values, positive_class_values]
            return shap_values[1][idx]
        elif hasattr(shap_values, "shape") and len(shap_values.shape) == 3:
            # 3D format: (n_samples, n_features, n_classes) — take positive class (index 1)
            return shap_values[idx, :, 1]
        else:
            # 2D format: (n_samples, n_features) — single class
            return shap_values[idx]

    def _compute_shap_explanation(
        self,
        X_processed: pd.DataFrame,
        raw_transaction: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute SHAP explanation for a single transaction."""
        self._init_shap_explainer()

        shap_values = self.explainer.shap_values(X_processed)

        shap_vals = self._extract_shap_values(shap_values, idx=0)

        feature_importance = list(zip(self.feature_names, shap_vals))
        feature_importance.sort(key=lambda x: abs(x[1]), reverse=True)

        top_features = feature_importance[: self.max_shap_features]

        explanation = [
            {
                "feature": feat,
                "value": round(float(raw_transaction.get(feat, 0)), 4),
                "shap_value": round(float(val), 4),
                "impact": "increases" if val > 0 else "decreases",
            }
            for feat, val in top_features
        ]

        return {
            "summary": self._format_explanation(top_features),
            "top_features": explanation,
        }

    def predict_batch(
        self,
        X: pd.DataFrame,
        threshold: float | None = None,
    ) -> pd.DataFrame:
        """
        Predict fraud for a batch of transactions (no SHAP).

        Returns:
            DataFrame with original data + fraud_probability + prediction
        """
        t = threshold or self.threshold
        X_processed = self.preprocess(X)
        probas = self.model.predict_proba(X_processed)[:, 1]

        result = X.copy()
        result["fraud_probability"] = probas
        result["prediction"] = (probas >= t).astype(int)
        result["decision"] = result["prediction"].map({0: "LEGITIMATE", 1: "FRAUD"})
        return result

    def _format_explanation(self, top_features: list[tuple[str, float]]) -> str:
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

    def _extract_global_shap_values(self, shap_values) -> Any:
        """Extract global SHAP values, handling different output shapes."""
        if isinstance(shap_values, list):
            return shap_values[1]
        elif hasattr(shap_values, "shape") and len(shap_values.shape) == 3:
            # (n_samples, n_features, n_classes) → (n_samples, n_features) for positive class
            return shap_values[:, :, 1]
        else:
            return shap_values

    def get_global_feature_importance(self, X_sample: pd.DataFrame) -> pd.DataFrame:
        """
        Compute global feature importance using SHAP.

        Args:
            X_sample: Sample of data to compute SHAP values over

        Returns:
            DataFrame with feature importances sorted by magnitude
        """
        self._init_shap_explainer(X_sample)
        X_processed = self.preprocess(X_sample)

        shap_values = self.explainer.shap_values(X_processed)
        shap_vals = self._extract_global_shap_values(shap_values)

        importance = pd.DataFrame(
            {
                "feature": self.feature_names,
                "mean_abs_shap": np.abs(shap_vals).mean(axis=0),
                "mean_shap": shap_vals.mean(axis=0),
            }
        ).sort_values("mean_abs_shap", ascending=False)

        return importance
