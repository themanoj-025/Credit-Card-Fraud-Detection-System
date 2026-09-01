"""
Preprocessing Module

Handles train/test split (BEFORE resampling), scaling, and resampling strategies.
CRITICAL: All resampling is done ONLY on the training set to avoid data leakage.
"""

import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from imblearn.combine import SMOTETomek
from imblearn.over_sampling import ADASYN, SMOTE
from imblearn.under_sampling import RandomUnderSampler
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.fraudlens.config import (
    PCA_FEATURES,
    RANDOM_STATE,
    SCALE_FEATURES,
    TEST_SIZE,
)

logger = logging.getLogger(__name__)


class FraudPreprocessor:
    """
    Preprocessing pipeline for credit card fraud detection.

    Key design decisions:
    1. Train/test split FIRST, then resample ONLY training data
    2. StandardScaler fitted ONLY on training data, then applied to test
    3. Multiple resampling strategies for comparison
    """

    def __init__(
        self,
        test_size: float = TEST_SIZE,
        random_state: int = RANDOM_STATE,
        scale_features: bool = True,
    ) -> None:
        """
        Initialize the preprocessor.

        Args:
            test_size: Proportion of data for testing
            random_state: Random seed for reproducibility
            scale_features: Whether to scale Time/Amount features
        """
        self.test_size = test_size
        self.random_state = random_state
        self.scale_features = scale_features
        self.scaler = StandardScaler() if scale_features else None
        self._is_fitted = False

    def split_data(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """
        Split data into train and test sets BEFORE any resampling.

        Args:
            df: Full DataFrame with features and 'Class' column

        Returns:
            Tuple of (X_train, X_test, y_train, y_test)
        """
        feature_cols = PCA_FEATURES + SCALE_FEATURES
        X = df[feature_cols].copy()
        y = df["Class"].copy()

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=self.test_size,
            random_state=self.random_state,
            stratify=y,
        )

        logger.info(
            "Train set: %d samples (%d fraud)", len(X_train), int(y_train.sum())
        )
        logger.info("Test set: %d samples (%d fraud)", len(X_test), int(y_test.sum()))

        return X_train, X_test, y_train, y_test

    def fit_scale(self, X_train: pd.DataFrame) -> pd.DataFrame:
        """
        Fit scaler on training data and transform it.

        Args:
            X_train: Training features

        Returns:
            Scaled training features
        """
        if not self.scale_features:
            return X_train

        X_scaled = X_train.copy()
        X_scaled[SCALE_FEATURES] = self.scaler.fit_transform(X_train[SCALE_FEATURES])
        self._is_fitted = True

        logger.info("Scaler fitted on training data: %s", SCALE_FEATURES)
        return X_scaled

    def transform_scale(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transform features using the fitted scaler.

        Args:
            X: Features to transform

        Returns:
            Scaled features
        """
        if not self.scale_features or not self._is_fitted:
            return X

        X_scaled = X.copy()
        X_scaled[SCALE_FEATURES] = self.scaler.transform(X[SCALE_FEATURES])
        return X_scaled

    def full_preprocess(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Complete preprocessing pipeline: split, scale.

        Args:
            df: Full DataFrame

        Returns:
            Dictionary with preprocessed data splits
        """
        X_train, X_test, y_train, y_test = self.split_data(df)
        X_train_scaled = self.fit_scale(X_train)
        X_test_scaled = self.transform_scale(X_test)

        return {
            "X_train": X_train_scaled,
            "X_test": X_test_scaled,
            "y_train": y_train,
            "y_test": y_test,
        }

    def save_scaler(self, path: str = "models/scaler.pkl") -> None:
        """Save the fitted scaler to disk."""
        if self.scaler is None:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.scaler, path)
        logger.info("Scaler saved to %s", path)

    def load_scaler(self, path: str = "models/scaler.pkl") -> None:
        """Load a fitted scaler from disk."""
        self.scaler = joblib.load(path)
        self._is_fitted = True
        logger.info("Scaler loaded from %s", path)


class Resampler:
    """
    Resampling strategies for handling class imbalance.

    CRITICAL: Only fit_resample on training data, never on test data.
    """

    STRATEGIES: list[str] = [
        "none",
        "class_weight",
        "random_under",
        "smote",
        "adasyn",
        "smote_tomek",
    ]

    def __init__(self, random_state: int = RANDOM_STATE) -> None:
        self.random_state = random_state

    def resample(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        strategy: str = "smote",
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Apply a resampling strategy to training data.

        Args:
            X_train: Training features
            y_train: Training labels
            strategy: Resampling strategy name

        Returns:
            Tuple of resampled (X, y)

        Raises:
            ValueError: If strategy is not recognized
        """
        if strategy in ("none", "class_weight"):
            return X_train, y_train

        sampler_map = {
            "random_under": RandomUnderSampler(
                random_state=self.random_state, sampling_strategy=0.5
            ),
            "smote": SMOTE(random_state=self.random_state, sampling_strategy=0.5),
            "adasyn": ADASYN(random_state=self.random_state, sampling_strategy=0.5),
            "smote_tomek": SMOTETomek(
                random_state=self.random_state, sampling_strategy=0.5
            ),
        }

        if strategy not in sampler_map:
            raise ValueError(
                f"Unknown strategy '{strategy}'. Choose from: {self.STRATEGIES}"
            )

        sampler = sampler_map[strategy]
        logger.info("Applying %s resampling...", strategy)
        n_before = len(y_train)
        fraud_before = int(y_train.sum())

        X_res, y_res = sampler.fit_resample(X_train, y_train)

        logger.info(
            "  Before: %d samples (%d fraud) → After: %d samples (%d fraud)",
            n_before,
            fraud_before,
            len(y_res),
            int(y_res.sum()),
        )

        return X_res, y_res

    def compare_strategies(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        strategies: list[str] | None = None,
    ) -> dict[str, tuple[pd.DataFrame, pd.Series]]:
        """
        Apply multiple resampling strategies for comparison.

        Args:
            X_train: Training features
            y_train: Training labels
            strategies: List of strategy names

        Returns:
            Dictionary mapping strategy name to (X, y) tuple
        """
        if strategies is None:
            strategies = ["none", "random_under", "smote", "adasyn", "smote_tomek"]

        return {strat: self.resample(X_train, y_train, strat) for strat in strategies}


def get_class_weights(y: pd.Series) -> dict[int, float]:
    """
    Compute class weights for imbalanced classification.

    Args:
        y: Target labels

    Returns:
        Dictionary of {class: weight}
    """
    n = len(y)
    n_classes = y.nunique()
    class_counts = y.value_counts().to_dict()

    weights = {cls: n / (n_classes * count) for cls, count in class_counts.items()}
    logger.info("Class weights: %s", weights)
    return weights
