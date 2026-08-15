"""
FraudLens — Automated Data Download

Provides two paths for obtaining the credit card fraud dataset:
1. Kaggle API download (requires KAGGLE_USERNAME + KAGGLE_KEY)
2. Synthetic fallback dataset (zero credentials needed)

The synthetic dataset matches the real schema (31 columns, same feature
names, similar statistics) so the demo works without any external
dependencies.

Usage:
    from src.fraudlens.data.download import ensure_data_ready
    df = ensure_data_ready()  # auto-downloads or generates synthetic
"""

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Target path
_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "raw"
    / "creditcard.csv"
)

# Synthetic dataset parameters (mimics real creditcard.csv statistics)
_SYNTHETIC_N_ROWS = 10000
_SYNTHETIC_FRAUD_RATE = 0.00172  # 0.172% fraud (matches real dataset)
_SYNTHETIC_N_FEATURES = 28  # V1-V28


def _kaggle_available() -> bool:
    """Check if Kaggle credentials are configured."""
    return bool(os.environ.get("KAGGLE_USERNAME")) and bool(
        os.environ.get("KAGGLE_KEY")
    )


def _download_from_kaggle(target_path: Path) -> bool:
    """
    Download creditcard.csv from Kaggle.

    Args:
        target_path: Where to save the downloaded file

    Returns:
        True if download succeeded, False otherwise
    """
    if not _kaggle_available():
        logger.info(
            "Kaggle credentials not found. Set KAGGLE_USERNAME and KAGGLE_KEY. "
            "See: https://github.com/Kaggle/kaggle-api#api-credentials. "
            "Falling back to synthetic dataset."
        )
        return False

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi()
        api.authenticate()

        logger.info("Downloading creditcardfraud dataset from Kaggle...")
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Download the dataset
        api.dataset_download_files(
            dataset="mlg-ulb/creditcardfraud",
            path=str(target_path.parent),
            force=False,
            quiet=True,
        )

        # Kaggle downloads as a zip — extract if needed
        zip_path = target_path.parent / "creditcardfraud.zip"
        if zip_path.exists():
            import zipfile

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(target_path.parent)
            zip_path.unlink()

        if target_path.exists():
            logger.info("Downloaded creditcard.csv to %s", target_path)
            return True

        logger.warning("Kaggle download completed but creditcard.csv not found")
        return False

    except ImportError:
        logger.warning("kaggle package not installed. Install with: pip install kaggle")
        return False
    except Exception as e:
        logger.warning("Kaggle download failed: %s", e)
        return False


def _generate_synthetic_dataset(target_path: Path) -> pd.DataFrame:
    """
    Generate a synthetic dataset matching the creditcard.csv schema.

    The synthetic data has:
    - Same column names (V1-V28, Time, Amount, Class)
    - Similar statistical properties (PCA features ~ N(0,1), Amount ~ Exponential)
    - Realistic class imbalance (~1.7% fraud)
    - Fraud transactions have shifted distributions (matching real patterns)

    Args:
        target_path: Where to save the generated CSV

    Returns:
        The generated DataFrame
    """
    rng = np.random.RandomState(42)

    n_total = _SYNTHETIC_N_ROWS
    n_fraud = int(n_total * _SYNTHETIC_FRAUD_RATE)
    n_total - n_fraud

    # Generate legitimate transactions
    features = {}
    for i in range(1, _SYNTHETIC_N_FEATURES + 1):
        features[f"V{i}"] = rng.randn(n_total)

    # Time: uniform over 2 days (172800 seconds)
    features["Time"] = rng.uniform(0, 172800, n_total)

    # Amount: exponential distribution (realistic for credit cards)
    features["Amount"] = rng.exponential(50, n_total)

    # Class labels
    classes = np.zeros(n_total, dtype=int)
    fraud_indices = rng.choice(n_total, n_fraud, replace=False)
    classes[fraud_indices] = 1

    # Shift fraud transactions to have characteristic patterns
    # Real fraud typically has extreme V14, V4, V12 values
    fraud_shifts = {
        "V14": -2.5,  # Strong negative shift
        "V4": 1.8,  # Positive shift
        "V12": -2.0,  # Negative shift
        "V10": 1.2,  # Positive shift
        "V17": -1.5,  # Negative shift
    }
    for feat, shift in fraud_shifts.items():
        features[feat][fraud_indices] += shift

    # Higher amounts for fraud
    features["Amount"][fraud_indices] *= 3

    features["Class"] = classes

    df = pd.DataFrame(features)

    # Save
    target_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target_path, index=False)

    logger.info(
        "Generated synthetic dataset: %d rows, %d fraud (%.2f%%)",
        n_total,
        n_fraud,
        n_fraud / n_total * 100,
    )

    return df


def _is_valid_dataset(path: Path) -> bool:
    """
    Check if an existing dataset file is valid.

    Validates:
    - File exists and is non-empty
    - Has expected columns (V1-V28, Time, Amount, Class)
    - Has reasonable row count (> 100)
    """
    if not path.exists() or path.stat().st_size == 0:
        return False

    try:
        # Read just the header + first few rows for speed
        df = pd.read_csv(path, nrows=5)
        expected_cols = {f"V{i}" for i in range(1, 29)} | {"Time", "Amount", "Class"}
        actual_cols = set(df.columns)

        if not expected_cols.issubset(actual_cols):
            logger.warning(
                "Dataset missing expected columns. Expected subset of %s, got %s",
                expected_cols,
                actual_cols,
            )
            return False

        # Check total row count
        total_rows = sum(1 for _ in open(path)) - 1  # subtract header
        if total_rows < 100:
            logger.warning("Dataset too small: %d rows", total_rows)
            return False

        return True

    except Exception as e:
        logger.warning("Dataset validation failed: %s", e)
        return False


def ensure_data_ready(
    target_path: Path | None = None,
    force_synthetic: bool = False,
    force_download: bool = False,
) -> pd.DataFrame:
    """
    Ensure the credit card fraud dataset is available.

    Priority:
    1. If target_path exists and is valid, return it
    2. If force_download or Kaggle creds available, try Kaggle
    3. Fall back to synthetic dataset (always works, zero credentials)

    Args:
        target_path: Path to creditcard.csv (default: data/raw/creditcard.csv)
        force_synthetic: Skip download, always generate synthetic
        force_download: Always try Kaggle, even if file exists

    Returns:
        DataFrame with the dataset
    """
    if target_path is None:
        target_path = _DATA_PATH

    # Check existing file (unless forced to re-download)
    if not force_download and not force_synthetic and _is_valid_dataset(target_path):
        logger.info("Using existing dataset at %s", target_path)
        return pd.read_csv(target_path)

    # Try Kaggle download
    if not force_synthetic and _kaggle_available():
        logger.info("Attempting Kaggle download...")
        if _download_from_kaggle(target_path):
            if _is_valid_dataset(target_path):
                return pd.read_csv(target_path)
            logger.warning("Downloaded file failed validation")

    # Fall back to synthetic
    logger.info(
        "No real dataset available — generating synthetic fallback "
        "(works with zero credentials)"
    )
    return _generate_synthetic_dataset(target_path)


def get_or_create_data(
    data_path: str | None = None,
    force_synthetic: bool = False,
) -> pd.DataFrame:
    """
    Convenience wrapper for DataLoader integration.

    Args:
        data_path: Path to CSV file
        force_synthetic: Force synthetic data generation

    Returns:
        DataFrame with the dataset
    """
    path = Path(data_path) if data_path else _DATA_PATH
    return ensure_data_ready(target_path=path, force_synthetic=force_synthetic)
