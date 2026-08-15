"""
Model Loader Module

Responsible for loading, validating, and providing access to trained
model artifacts (model + scaler + threshold). Pure I/O — no prediction logic.

This was extracted from the original FraudPredictor to respect the
Single Responsibility Principle.
"""

import hashlib
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from src.fraudlens.config import ALL_FEATURES, MODELS_DIR, SCALE_FEATURES

logger = logging.getLogger(__name__)


class ModelLoadError(Exception):
    """Raised when a model artifact cannot be loaded or verified."""


class ModelLoader:
    """
    Load, verify, and provide access to trained model artifacts.

    Responsibilities:
    - Load model from disk (with optional checksum verification)
    - Load scaler from disk
    - Load and parse threshold from file
    - Generate checksums for future verification
    """

    def __init__(
        self,
        model_path: Path | None = None,
        scaler_path: Path | None = None,
        threshold_path: Path | None = None,
        feature_names: list[str] | None = None,
        verify_checksum: bool = True,
    ) -> None:
        """
        Args:
            model_path: Path to the model pickle file
            scaler_path: Path to the scaler pickle file
            threshold_path: Path to the threshold text file
            feature_names: List of feature names
            verify_checksum: Whether to verify model file integrity
        """
        self.model_path = model_path or MODELS_DIR / "best_fraud_model.pkl"
        self.scaler_path = scaler_path or MODELS_DIR / "scaler.pkl"
        self.threshold_path = threshold_path or MODELS_DIR / "threshold.txt"
        self.feature_names = feature_names or ALL_FEATURES
        self.verify_checksum = verify_checksum

        self.model: object | None = None
        self.scaler: StandardScaler | None = None
        self.threshold: float = 0.5

    def load_model(self) -> object:
        """
        Load and verify the trained model from disk.

        Returns:
            The loaded model object

        Raises:
            ModelLoadError: If model file doesn't exist or checksum fails
        """
        if not self.model_path.exists():
            raise ModelLoadError(f"Model not found at: {self.model_path}")

        if self.verify_checksum:
            self._verify_checksum(self.model_path)

        self.model = joblib.load(str(self.model_path))
        logger.info("Model loaded from %s", self.model_path)
        return self.model

    def load_scaler(self) -> StandardScaler | None:
        """
        Load the fitted StandardScaler from disk.

        Returns:
            The scaler, or None if not found
        """
        if not self.scaler_path.exists():
            logger.warning("Scaler not found at: %s", self.scaler_path)
            self.scaler = None
            return None

        self.scaler = joblib.load(str(self.scaler_path))
        logger.info("Scaler loaded from %s", self.scaler_path)
        return self.scaler

    def load_threshold(self) -> float:
        """
        Load the optimal decision threshold from disk.

        Returns:
            The threshold value (default 0.5 if not found)
        """
        if not self.threshold_path.exists():
            logger.info("Threshold file not found, using default: 0.5")
            self.threshold = 0.5
            return self.threshold

        with open(self.threshold_path) as f:
            self.threshold = float(f.read().strip())
        logger.info("Threshold loaded: %.4f", self.threshold)
        return self.threshold

    def load_all(self) -> "ModelLoader":
        """
        Convenience method to load model + scaler + threshold.

        Returns:
            Self for chaining
        """
        self.load_model()
        self.load_scaler()
        self.load_threshold()
        return self

    def preprocess(self, X: "pd.DataFrame") -> "pd.DataFrame":
        """
        Apply scaling transformation to features (DataFrame path).

        Args:
            X: Input features as DataFrame

        Returns:
            Scaled features (or original if no scaler loaded)
        """

        if self.scaler is None:
            return X

        X_scaled = X.copy()
        available = [c for c in SCALE_FEATURES if c in X_scaled.columns]
        if available:
            X_scaled[available] = self.scaler.transform(X_scaled[available])
        return X_scaled

    def preprocess_numpy(self, X: np.ndarray) -> np.ndarray:
        """
        Apply scaling transformation to features (vectorized numpy path).

        ~10x faster than the DataFrame path for single predictions.

        Args:
            X: Input features as numpy array of shape (n_samples, n_features)

        Returns:
            Scaled features as numpy array (or original if no scaler loaded)
        """
        if self.scaler is None or len(SCALE_FEATURES) == 0:
            return X

        # SCALE_FEATURES are always the last features: V1-V28, Time, Amount
        # Time is at index 28, Amount is at index 29
        scale_indices = [
            self.feature_names.index(f)
            for f in SCALE_FEATURES
            if f in self.feature_names
        ]

        if not scale_indices:
            return X

        X_scaled = X.copy()
        X_scaled[:, scale_indices] = self.scaler.transform(X[:, scale_indices])
        return X_scaled

    def _verify_checksum(self, model_path: Path) -> None:
        """
        Verify model file integrity using SHA-256 checksum.

        If no .sha256 file exists, generates one for future verification.
        """
        sha_path = model_path.with_suffix(".pkl.sha256")
        if not sha_path.exists():
            file_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
            sha_path.write_text(file_hash)
            logger.info("Generated model checksum: %s", sha_path)
            return

        stored_hash = sha_path.read_text().strip()
        computed_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if stored_hash != computed_hash:
            raise ModelLoadError(
                f"Checksum MISMATCH for {model_path} — possible tampering!"
            )
        logger.info("Model checksum verified: %s", model_path)

    @staticmethod
    def has_predict_proba(model: object) -> bool:
        """Check if a model supports predict_proba."""
        return hasattr(model, "predict_proba") and callable(model.predict_proba)
