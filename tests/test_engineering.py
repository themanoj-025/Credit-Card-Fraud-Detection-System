"""
Tests for the Feature Engineering module.

Verifies engineered features produce expected columns/dtypes
and handle edge cases without raising.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fraudlens.features.engineering import FeatureEngineer

# Fixtures


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """A small representative dataset for testing."""
    np.random.seed(42)
    n = 100
    data = {f"V{i}": np.random.randn(n) for i in range(1, 29)}
    data["Time"] = np.random.uniform(0, 172800, n)
    data["Amount"] = np.random.exponential(100, n)
    return pd.DataFrame(data)


# Tests: Initialization


class TestFeatureEngineerInit:
    """Tests for FeatureEngineer initialization."""

    def test_default_initialization(self) -> None:
        """Test default constructor."""
        fe = FeatureEngineer()
        assert fe.create_interactions
        assert fe.create_bins

    def test_custom_initialization(self) -> None:
        """Test custom parameters."""
        fe = FeatureEngineer(create_interactions=False, create_bins=False)
        assert not fe.create_interactions
        assert not fe.create_bins


# Tests: Feature Transformation


class TestFeatureTransformation:
    """Tests for the transform method."""

    def test_transform_returns_dataframe(self, sample_df) -> None:
        """Test that transform returns a DataFrame."""
        fe = FeatureEngineer()
        result = fe.transform(sample_df)
        assert isinstance(result, pd.DataFrame)

    def test_transform_adds_columns(self, sample_df) -> None:
        """Test that transform adds more columns than the input had."""
        fe = FeatureEngineer()
        n_input = sample_df.shape[1]
        result = fe.transform(sample_df)
        assert result.shape[1] > n_input

    def test_transform_adds_amount_log(self, sample_df) -> None:
        """Test that Amount_log column is created."""
        fe = FeatureEngineer()
        result = fe.transform(sample_df)
        assert "Amount_log" in result.columns

    def test_transform_adds_hour(self, sample_df) -> None:
        """Test that Hour column is created."""
        fe = FeatureEngineer()
        result = fe.transform(sample_df)
        assert "Hour" in result.columns

    def test_transform_adds_pca_stats(self, sample_df) -> None:
        """Test that PCA aggregate statistics are created."""
        fe = FeatureEngineer()
        result = fe.transform(sample_df)
        assert "V_mean" in result.columns
        assert "V_std" in result.columns
        assert "V_min" in result.columns
        assert "V_max" in result.columns
        assert "V_skew" in result.columns

    def test_transform_adds_interactions(self, sample_df) -> None:
        """Test that interaction features are created."""
        fe = FeatureEngineer()
        result = fe.transform(sample_df)
        assert "V14_V4_interaction" in result.columns
        assert "V12_V10_interaction" in result.columns

    def test_transform_without_bins(self, sample_df) -> None:
        """Test transform with create_bins=False."""
        fe = FeatureEngineer(create_bins=False)
        result = fe.transform(sample_df)
        assert "Amount_log" not in result.columns
        assert "Hour" not in result.columns

    def test_transform_without_interactions(self, sample_df) -> None:
        """Test transform with create_interactions=False."""
        fe = FeatureEngineer(create_interactions=False)
        result = fe.transform(sample_df)
        assert "V14_V4_interaction" not in result.columns

    def test_transform_preserves_input_rows(self, sample_df) -> None:
        """Test that transform preserves the number of rows."""
        fe = FeatureEngineer()
        result = fe.transform(sample_df)
        assert len(result) == len(sample_df)


# Tests: Edge Cases


class TestEdgeCases:
    """Edge case tests for FeatureEngineer."""

    def test_single_row_input(self) -> None:
        """Test that transform handles a single-row DataFrame."""
        single = pd.DataFrame(
            {**{f"V{i}": [0.0] for i in range(1, 29)}, "Time": [0.0], "Amount": [50.0]}
        )
        fe = FeatureEngineer()
        result = fe.transform(single)
        assert len(result) == 1

    def test_negative_amount(self) -> None:
        """Test that negative Amount values are handled without error.
        Note: np.log1p(-amount) will be NaN for amount < -1 since log of negatives is undefined.
        """
        df = pd.DataFrame(
            {
                **{f"V{i}": [0.0, 0.0] for i in range(1, 29)},
                "Time": [0.0, 100.0],
                "Amount": [-50.0, 200.0],
            }
        )
        fe = FeatureEngineer()
        result = fe.transform(df)
        assert len(result) == 2
        # Amount_log may be NaN for negative values, but the transform should not crash
        assert "Amount_log" in result.columns
        # The second row should have a valid positive log
        assert result["Amount_log"].iloc[1] > 0

    def test_zero_amount(self) -> None:
        """Test that Amount of 0 is handled."""
        df = pd.DataFrame(
            {**{f"V{i}": [0.0] for i in range(1, 29)}, "Time": [0.0], "Amount": [0.0]}
        )
        fe = FeatureEngineer()
        result = fe.transform(df)
        assert result["Amount_log"].iloc[0] == 0.0


# Tests: Static Methods


class TestStaticMethods:
    """Tests for static helper methods."""

    def test_get_base_features(self) -> None:
        """Test that get_base_features returns correct feature list."""
        features = FeatureEngineer.get_base_features()
        assert len(features) == 30
        assert "V1" in features
        assert "V28" in features
        assert "Time" in features
        assert "Amount" in features

    def test_get_pca_features(self) -> None:
        """Test that get_pca_features returns correct feature list."""
        features = FeatureEngineer.get_pca_features()
        assert len(features) == 28
        assert "V1" in features
        assert "V28" in features
        assert "Time" not in features
