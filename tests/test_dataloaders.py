"""
FraudLens — DataLoader Tests

Covers DataLoader class: load, get_basic_stats, get_column_info,
get_class_distribution, sample_transaction, and the convenience load_data function.
"""

import numpy as np
import pandas as pd
import pytest

from src.fraudlens.data.loaders import DataLoader, load_data


@pytest.fixture
def sample_csv_data() -> pd.DataFrame:
    """Create a small in-memory dataset mimicking the Kaggle fraud CSV."""
    np.random.seed(42)
    n = 200
    data = {f"V{i}": np.random.randn(n) for i in range(1, 29)}
    data["Time"] = np.random.uniform(0, 172800, n)
    data["Amount"] = np.random.exponential(100, n)
    data["Class"] = np.random.choice([0, 1], n, p=[0.97, 0.03])
    return pd.DataFrame(data)


class TestDataLoaderInit:
    """Test DataLoader initialization."""

    def test_default_init(self):
        """Test default initialization uses config values."""
        loader = DataLoader()
        assert loader.data_path is not None
        assert loader.avg_fraud_loss == 150.0
        assert loader.review_cost == 5.0
        assert loader.df is None

    def test_custom_init(self):
        """Test custom initialization values."""
        loader = DataLoader(
            data_path="/custom/path.csv",
            avg_fraud_loss=200.0,
            review_cost=10.0,
        )
        assert "custom" in str(loader.data_path)
        assert "path.csv" in str(loader.data_path)
        assert loader.avg_fraud_loss == 200.0
        assert loader.review_cost == 10.0

    def test_init_partial_custom(self):
        """Test with only data_path provided."""
        loader = DataLoader(data_path="/data/creditcard.csv")
        assert loader.avg_fraud_loss == 150.0  # default
        assert loader.review_cost == 5.0  # default


class TestDataLoaderLoad:
    """Test the load method."""

    def test_load_success(self, sample_csv_data, tmp_path):
        """Test successful loading of CSV file."""
        csv_path = tmp_path / "creditcard.csv"
        sample_csv_data.to_csv(csv_path, index=False)

        loader = DataLoader(data_path=str(csv_path))
        df = loader.load()

        assert df is not None
        assert len(df) == 200
        assert "Class" in df.columns
        assert loader.df is not None

    def test_load_file_not_found(self):
        """Test FileNotFoundError when file doesn't exist."""
        loader = DataLoader(data_path="/nonexistent/path.csv")
        with pytest.raises(FileNotFoundError, match="Dataset not found"):
            loader.load()

    def test_load_updates_internal_df(self, sample_csv_data, tmp_path):
        """Test that load() sets self.df."""
        csv_path = tmp_path / "test.csv"
        sample_csv_data.to_csv(csv_path, index=False)

        loader = DataLoader(data_path=str(csv_path))
        assert loader.df is None
        loader.load()
        assert loader.df is not None


class TestDataLoaderStats:
    """Test get_basic_stats and related methods."""

    def test_get_basic_stats_not_loaded(self):
        """Test ValueError when calling stats before loading."""
        loader = DataLoader()
        with pytest.raises(ValueError, match="Dataset not loaded"):
            loader.get_basic_stats()

    def test_get_basic_stats_shape(self, sample_csv_data, tmp_path):
        """Test basic stats contains all expected keys."""
        csv_path = tmp_path / "data.csv"
        sample_csv_data.to_csv(csv_path, index=False)

        loader = DataLoader(data_path=str(csv_path))
        loader.load()
        stats = loader.get_basic_stats()

        assert "n_samples" in stats
        assert "n_features" in stats
        assert "n_fraud" in stats
        assert "n_legitimate" in stats
        assert "fraud_rate_pct" in stats
        assert "imbalance_ratio" in stats
        assert "amount_mean" in stats
        assert "amount_max" in stats
        assert "time_range" in stats
        assert stats["n_samples"] == 200
        assert (
            stats["n_features"] == 30
        )  # V1-V28 + Time + Amount = 30 features, minus Class in shape[1]-1

    def test_get_column_info(self, sample_csv_data, tmp_path):
        """Test column info returns expected DataFrame."""
        csv_path = tmp_path / "data.csv"
        sample_csv_data.to_csv(csv_path, index=False)

        loader = DataLoader(data_path=str(csv_path))
        loader.load()
        info = loader.get_column_info()

        assert isinstance(info, pd.DataFrame)
        assert "dtype" in info.columns
        assert "non_null" in info.columns
        assert "n_unique" in info.columns
        assert len(info) == len(sample_csv_data.columns)

    def test_get_column_info_not_loaded(self):
        """Test ValueError when calling column info before loading."""
        loader = DataLoader()
        with pytest.raises(ValueError, match="Dataset not loaded"):
            loader.get_column_info()

    def test_get_class_distribution(self, sample_csv_data, tmp_path):
        """Test class distribution returns expected keys."""
        csv_path = tmp_path / "data.csv"
        sample_csv_data.to_csv(csv_path, index=False)

        loader = DataLoader(data_path=str(csv_path))
        loader.load()
        dist = loader.get_class_distribution()

        assert "n_fraud" in dist
        assert "n_legitimate" in dist
        assert "fraud_rate" in dist
        assert "baseline_loss" in dist
        assert "avg_fraud_loss" in dist
        assert dist["n_fraud"] + dist["n_legitimate"] == 200

    def test_get_class_distribution_not_loaded(self):
        """Test ValueError when calling class distribution before loading."""
        loader = DataLoader()
        with pytest.raises(ValueError, match="Dataset not loaded"):
            loader.get_class_distribution()

    def test_sample_transaction(self, sample_csv_data, tmp_path):
        """Test sample transaction returns a fraud dict without 'Class'."""
        csv_path = tmp_path / "data.csv"
        sample_csv_data.to_csv(csv_path, index=False)

        loader = DataLoader(data_path=str(csv_path))
        loader.load()
        tx = loader.sample_transaction()

        assert isinstance(tx, dict)
        assert "Class" not in tx  # Class column excluded
        assert "Amount" in tx
        assert "Time" in tx

    def test_sample_transaction_not_loaded(self):
        """Test ValueError when sample_transaction called before loading."""
        loader = DataLoader()
        with pytest.raises(ValueError, match="Dataset not loaded"):
            loader.sample_transaction()


class TestLoadDataFunction:
    """Test the convenience load_data function."""

    def test_load_data(self, sample_csv_data, tmp_path):
        """Test load_data returns DataFrame and stats dict."""
        csv_path = tmp_path / "data.csv"
        sample_csv_data.to_csv(csv_path, index=False)

        df, stats = load_data(str(csv_path))

        assert isinstance(df, pd.DataFrame)
        assert isinstance(stats, dict)
        assert len(df) == 200
        assert stats["n_samples"] == 200

    def test_load_data_file_not_found(self):
        """Test load_data propagates FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_data("/nonexistent/path.csv")


class TestDataLoaderEdgeCases:
    """Test edge cases for DataLoader."""

    def test_empty_dataframe(self, tmp_path):
        """Test handling of empty CSV."""
        empty_df = pd.DataFrame(
            columns=[f"V{i}" for i in range(1, 29)] + ["Time", "Amount", "Class"]
        )
        csv_path = tmp_path / "empty.csv"
        empty_df.to_csv(csv_path, index=False)

        loader = DataLoader(data_path=str(csv_path))
        loader.load()

        stats = loader.get_basic_stats()
        assert stats["n_samples"] == 0
        assert stats["n_fraud"] == 0
        assert stats["n_legitimate"] == 0

    def test_all_legitimate(self, tmp_path):
        """Test dataset with no fraud samples."""
        df = pd.DataFrame({f"V{i}": [0.0, 0.1] for i in range(1, 29)})
        df["Time"] = [0.0, 100.0]
        df["Amount"] = [50.0, 100.0]
        df["Class"] = [0, 0]
        csv_path = tmp_path / "nofraud.csv"
        df.to_csv(csv_path, index=False)

        loader = DataLoader(data_path=str(csv_path))
        loader.load()
        stats = loader.get_basic_stats()

        assert stats["n_fraud"] == 0
        assert stats["n_legitimate"] == 2
        assert stats["fraud_rate_pct"] == 0.0
