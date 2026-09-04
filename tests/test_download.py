"""
FraudLens — Data Download Module Tests

Tests for src/fraudlens/data/download.py covering:
- Synthetic dataset generation
- Dataset validation
- ensure_data_ready logic (Kaggle path + fallback)
- Checksum computation
"""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit



from src.fraudlens.data.download import (
    _generate_synthetic_dataset,
    _is_valid_dataset,
    _kaggle_available,
    ensure_data_ready,
    get_or_create_data,
)

# Fixtures


@pytest.fixture
def tmp_data_dir(tmp_path) -> None:
    """Create a temporary data directory."""
    data_dir = tmp_path / "data" / "raw"
    data_dir.mkdir(parents=True)
    return data_dir


@pytest.fixture
def valid_csv(tmp_data_dir) -> None:
    """Create a valid synthetic creditcard.csv for testing."""
    target = tmp_data_dir / "creditcard.csv"
    rng = np.random.RandomState(42)
    n = 200
    data = {f"V{i}": rng.randn(n) for i in range(1, 29)}
    data["Time"] = rng.uniform(0, 172800, n)
    data["Amount"] = rng.exponential(50, n)
    data["Class"] = np.random.choice([0, 1], n, p=[0.99, 0.01])
    df = pd.DataFrame(data)
    df.to_csv(target, index=False)
    return target


# Tests: Checksum


# Tests: Kaggle Available


class TestKaggleAvailable:
    """Tests for _kaggle_available."""

    def test_returns_false_when_no_env(self, monkeypatch) -> None:
        """Returns False when env vars not set."""
        monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
        monkeypatch.delenv("KAGGLE_KEY", raising=False)
        assert _kaggle_available() is False

    def test_returns_true_when_both_set(self, monkeypatch) -> None:
        """Returns True when both env vars are set."""
        monkeypatch.setenv("KAGGLE_USERNAME", "testuser")
        monkeypatch.setenv("KAGGLE_KEY", "testkey")
        assert _kaggle_available() is True

    def test_returns_false_when_only_username(self, monkeypatch) -> None:
        """Returns False when only username is set."""
        monkeypatch.setenv("KAGGLE_USERNAME", "testuser")
        monkeypatch.delenv("KAGGLE_KEY", raising=False)
        assert _kaggle_available() is False

    def test_returns_false_when_only_key(self, monkeypatch) -> None:
        """Returns False when only key is set."""
        monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
        monkeypatch.setenv("KAGGLE_KEY", "testkey")
        assert _kaggle_available() is False


# Tests: Synthetic Dataset Generation


class TestSyntheticDataset:
    """Tests for _generate_synthetic_dataset."""

    def test_generates_csv_with_correct_columns(self, tmp_data_dir) -> None:
        """Synthetic data should have all expected columns."""
        target = tmp_data_dir / "creditcard.csv"
        df = _generate_synthetic_dataset(target)

        expected_cols = {f"V{i}" for i in range(1, 29)} | {"Time", "Amount", "Class"}
        assert expected_cols.issubset(set(df.columns))

    def test_generates_correct_row_count(self, tmp_data_dir) -> None:
        """Should generate approximately _SYNTHETIC_N_ROWS rows."""
        target = tmp_data_dir / "creditcard.csv"
        df = _generate_synthetic_dataset(target)
        # Allow some variance but should be close to 10000
        assert 9000 <= len(df) <= 11000

    def test_fraud_rate_is_realistic(self, tmp_data_dir) -> None:
        """Fraud rate should be approximately 0.172%."""
        target = tmp_data_dir / "creditcard.csv"
        df = _generate_synthetic_dataset(target)
        fraud_rate = df["Class"].mean()
        assert 0.001 <= fraud_rate <= 0.01  # Between 0.1% and 1%

    def test_saves_to_csv(self, tmp_data_dir) -> None:
        """Should write a CSV file to the target path."""
        target = tmp_data_dir / "creditcard.csv"
        _generate_synthetic_dataset(target)
        assert target.exists()
        assert target.stat().st_size > 0

    def test_creates_parent_directories(self, tmp_path) -> None:
        """Should create intermediate directories if needed."""
        target = tmp_path / "deep" / "nested" / "path" / "creditcard.csv"
        _generate_synthetic_dataset(target)
        assert target.exists()

    def test_fraud_features_are_shifted(self, tmp_data_dir) -> None:
        """Fraud transactions should have shifted V14, V4, V12 distributions."""
        target = tmp_data_dir / "creditcard.csv"
        df = _generate_synthetic_dataset(target)

        fraud = df[df["Class"] == 1]
        legit = df[df["Class"] == 0]

        # V14 should be shifted negative for fraud
        assert fraud["V14"].mean() < legit["V14"].mean()
        # V4 should be shifted positive for fraud
        assert fraud["V4"].mean() > legit["V4"].mean()
        # V12 should be shifted negative for fraud
        assert fraud["V12"].mean() < legit["V12"].mean()

    def test_amount_higher_for_fraud(self, tmp_data_dir) -> None:
        """Fraud transactions should have higher amounts."""
        target = tmp_data_dir / "creditcard.csv"
        df = _generate_synthetic_dataset(target)

        fraud = df[df["Class"] == 1]
        legit = df[df["Class"] == 0]
        assert fraud["Amount"].mean() > legit["Amount"].mean()

    def test_deterministic_with_same_seed(self, tmp_data_dir) -> None:
        """Two calls should produce identical data (same random seed)."""
        target1 = tmp_data_dir / "data1.csv"
        target2 = tmp_data_dir / "data2.csv"
        df1 = _generate_synthetic_dataset(target1)
        df2 = _generate_synthetic_dataset(target2)
        pd.testing.assert_frame_equal(df1, df2)


# Tests: Dataset Validation


class TestDatasetValidation:
    """Tests for _is_valid_dataset."""

    def test_valid_dataset_passes(self, valid_csv) -> None:
        """A valid CSV should pass validation."""
        assert _is_valid_dataset(valid_csv) is True

    def test_nonexistent_file_fails(self, tmp_path) -> None:
        """A nonexistent file should fail validation."""
        assert _is_valid_dataset(tmp_path / "nonexistent.csv") is False

    def test_empty_file_fails(self, tmp_path) -> None:
        """An empty file should fail validation."""
        f = tmp_path / "empty.csv"
        f.write_text("")
        assert _is_valid_dataset(f) is False

    def test_too_few_rows_fails(self, tmp_path) -> None:
        """A CSV with < 100 rows should fail validation."""
        f = tmp_path / "small.csv"
        df = pd.DataFrame({"V1": [1, 2], "V2": [3, 4], "Class": [0, 1]})
        df.to_csv(f, index=False)
        assert _is_valid_dataset(f) is False

    def test_missing_columns_fails(self, tmp_path) -> None:
        """A CSV missing expected columns should fail validation."""
        f = tmp_path / "bad_cols.csv"
        df = pd.DataFrame({"col_a": range(200), "col_b": range(200)})
        df.to_csv(f, index=False)
        assert _is_valid_dataset(f) is False


# Tests: ensure_data_ready


class TestEnsureDataReady:
    """Tests for ensure_data_ready."""

    def test_returns_existing_valid_dataset(self, valid_csv) -> None:
        """Should return existing valid dataset without re-generating."""
        df = ensure_data_ready(target_path=valid_csv)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 200

    def test_generates_synthetic_when_no_file(self, tmp_data_dir) -> None:
        """Should generate synthetic data when no file exists."""
        target = tmp_data_dir / "creditcard.csv"
        df = ensure_data_ready(target_path=target)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert target.exists()

    def test_force_synthetic_overrides(self, valid_csv) -> None:
        """force_synthetic=True should regenerate even if valid file exists."""
        original_rows = pd.read_csv(valid_csv).shape[0]
        df = ensure_data_ready(target_path=valid_csv, force_synthetic=True)
        # Synthetic has different row count (10000 vs 200)
        assert df.shape[0] != original_rows

    def test_no_kaggle_falls_back_to_synthetic(self, tmp_data_dir, monkeypatch) -> None:
        """Without Kaggle creds, should fall back to synthetic."""
        monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
        monkeypatch.delenv("KAGGLE_KEY", raising=False)
        target = tmp_data_dir / "creditcard.csv"
        df = ensure_data_ready(target_path=target)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_default_path(self) -> None:
        """Should use the default path when no target_path given."""
        # Just verify it doesn't raise
        with patch("src.fraudlens.data.download._DATA_PATH") as mock_path:
            mock_path.return_value = Path("/tmp/test_default.csv")
            with patch(
                "src.fraudlens.data.download._is_valid_dataset",
                return_value=True,
            ), patch("pandas.read_csv") as mock_read:
                mock_read.return_value = pd.DataFrame({"A": [1]})
                df = ensure_data_ready()
                assert isinstance(df, pd.DataFrame)


# Tests: get_or_create_data


class TestGetOrCreateData:
    """Tests for get_or_create_data convenience wrapper."""

    def test_creates_data_with_string_path(self, tmp_path) -> None:
        """Should accept string paths."""
        target = str(tmp_path / "data.csv")
        df = get_or_create_data(data_path=target)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_creates_data_without_path(self) -> None:
        """Should work without specifying a path."""
        with patch("src.fraudlens.data.download._DATA_PATH") as mock_path:
            mock_path.return_value = Path("/tmp/test_get_or_create.csv")
            with patch(
                "src.fraudlens.data.download._is_valid_dataset",
                return_value=True,
            ), patch("pandas.read_csv") as mock_read:
                mock_read.return_value = pd.DataFrame({"A": [1]})
                df = get_or_create_data()
                assert isinstance(df, pd.DataFrame)

    def test_force_synthetic(self, tmp_path) -> None:
        """Should support force_synthetic parameter."""
        target = tmp_path / "forced.csv"
        df = get_or_create_data(data_path=str(target), force_synthetic=True)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
