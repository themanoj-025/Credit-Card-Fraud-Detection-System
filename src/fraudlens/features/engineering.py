"""
Feature Engineering Module

Creates additional features from the base dataset to improve model performance.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Create derived features for fraud detection.

    The base dataset already has PCA-transformed features (V1-V28),
    but we can derive additional features from Time and Amount.
    """

    def __init__(
        self, create_interactions: bool = True, create_bins: bool = True
    ) -> None:
        """
        Args:
            create_interactions: Create interaction features between top V features
            create_bins: Create binned versions of Amount and Time
        """
        self.create_interactions = create_interactions
        self.create_bins = create_bins
        self._feature_names: list[str] | None = None

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add engineered features to the dataframe.

        Args:
            df: DataFrame with base features

        Returns:
            DataFrame with additional engineered features
        """
        X = df.copy()
        pca_cols = [f"V{i}" for i in range(1, 29)]

        # Amount-based features
        if self.create_bins:
            X["Amount_log"] = np.log1p(X["Amount"])
            X["Amount_bin"] = (
                pd.cut(
                    X["Amount"],
                    bins=[0, 10, 50, 200, 1000, 30000],
                    labels=[0, 1, 2, 3, 4],
                )
                .astype(float)
                .fillna(0)
            )

        # Time-based features
        if self.create_bins:
            X["Hour"] = (X["Time"] / 3600) % 24
            X["Time_diff"] = X["Time"].diff().fillna(0).clip(lower=0)

        # Aggregated PCA statistics
        X["V_mean"] = X[pca_cols].mean(axis=1)
        X["V_std"] = X[pca_cols].std(axis=1)
        X["V_min"] = X[pca_cols].min(axis=1)
        X["V_max"] = X[pca_cols].max(axis=1)
        X["V_skew"] = X[pca_cols].skew(axis=1)

        # Number of extreme PCA values (> 2 std from mean)
        v_means = X[pca_cols].mean()
        v_stds = X[pca_cols].std()
        extreme_count = pd.DataFrame(
            np.abs(X[pca_cols].values - v_means.values) > 2 * v_stds.values,
            columns=pca_cols,
            index=X.index,
        ).sum(axis=1)
        X["V_extreme_count"] = extreme_count

        # Interaction features (top discriminative pairs)
        if self.create_interactions:
            X["V14_V4_interaction"] = X["V14"] * X["V4"]
            X["V12_V10_interaction"] = X["V12"] * X["V10"]
            X["V14_V12_interaction"] = X["V14"] * X["V12"]
            X["V17_V14_interaction"] = X["V17"] * X["V14"]

        self._feature_names = X.columns.tolist()
        logger.info("Feature engineering: %d → %d features", df.shape[1], X.shape[1])
        return X

    def get_feature_names(self) -> list[str] | None:
        """Get the list of feature names after transformation."""
        return self._feature_names

    @staticmethod
    def get_base_features() -> list[str]:
        """Get the original feature names (V1-V28 + Time + Amount)."""
        return [f"V{i}" for i in range(1, 29)] + ["Time", "Amount"]

    @staticmethod
    def get_pca_features() -> list[str]:
        """Get only the PCA feature names."""
        return [f"V{i}" for i in range(1, 29)]
