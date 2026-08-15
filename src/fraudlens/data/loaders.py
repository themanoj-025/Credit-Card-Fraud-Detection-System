"""
Data Loader Module

Handles loading the credit card fraud dataset and providing basic statistics.
"""

import logging
from pathlib import Path

import pandas as pd

from src.fraudlens.config import AVG_FRAUD_LOSS, DEFAULT_DATA_PATH, REVIEW_COST

logger = logging.getLogger(__name__)


class DataLoader:
    """Load and inspect the credit card fraud dataset."""

    def __init__(
        self,
        data_path: str | None = None,
        avg_fraud_loss: float | None = None,
        review_cost: float | None = None,
    ) -> None:
        """
        Initialize the data loader.

        Args:
            data_path: Path to the CSV dataset (default from config)
            avg_fraud_loss: Average dollar loss per fraudulent transaction
            review_cost: Cost to manually review a flagged transaction
        """
        self.data_path = Path(data_path) if data_path else DEFAULT_DATA_PATH
        self.avg_fraud_loss = avg_fraud_loss or AVG_FRAUD_LOSS
        self.review_cost = review_cost or REVIEW_COST
        self.df: pd.DataFrame | None = None

    def load(self) -> pd.DataFrame:
        """
        Load the dataset from CSV.

        Returns:
            DataFrame with the loaded data

        Raises:
            FileNotFoundError: If the data file doesn't exist
        """
        if not self.data_path.exists():
            raise FileNotFoundError(f"Dataset not found at: {self.data_path}")

        logger.info("Loading dataset from %s", self.data_path)
        self.df = pd.read_csv(self.data_path)
        logger.info(
            "Dataset loaded: %d rows, %d columns",
            self.df.shape[0],
            self.df.shape[1],
        )
        return self.df

    def get_basic_stats(self) -> dict:
        """
        Get basic statistics about the dataset.

        Returns:
            Dictionary with dataset statistics
        """
        if self.df is None:
            raise ValueError("Dataset not loaded. Call load() first.")

        df = self.df
        n_total = len(df)
        n_fraud = int(df["Class"].sum()) if n_total > 0 else 0
        n_legit = n_total - n_fraud
        fraud_rate = n_fraud / n_total * 100 if n_total > 0 else 0.0

        stats = {
            "n_samples": n_total,
            "n_features": df.shape[1] - 1,
            "n_fraud": n_fraud,
            "n_legitimate": n_legit,
            "fraud_rate_pct": round(fraud_rate, 4),
            "imbalance_ratio": round(n_legit / n_fraud, 1) if n_fraud > 0 else None,
            "amount_mean": round(float(df["Amount"].mean()), 2) if n_total > 0 else 0.0,
            "amount_max": round(float(df["Amount"].max()), 2) if n_total > 0 else 0.0,
            "time_range": (
                (int(df["Time"].min()), int(df["Time"].max()))
                if n_total > 0
                else (0, 0)
            ),
            "avg_fraud_loss": self.avg_fraud_loss,
            "review_cost": self.review_cost,
        }
        return stats

    def get_column_info(self) -> pd.DataFrame:
        """Get information about each column."""
        if self.df is None:
            raise ValueError("Dataset not loaded. Call load() first.")

        info = pd.DataFrame(
            {
                "dtype": self.df.dtypes,
                "non_null": self.df.count(),
                "null_pct": (self.df.isnull().sum() / len(self.df) * 100).round(2),
                "n_unique": self.df.nunique(),
            }
        )
        return info

    def get_class_distribution(self) -> dict:
        """
        Get the class distribution with business metrics.

        Returns:
            Dictionary with class distribution and business impact
        """
        if self.df is None:
            raise ValueError("Dataset not loaded. Call load() first.")

        n_total = len(self.df)
        n_fraud = int(self.df["Class"].sum())
        n_legit = n_total - n_fraud
        baseline_loss = n_fraud * self.avg_fraud_loss

        return {
            "n_fraud": n_fraud,
            "n_legitimate": n_legit,
            "fraud_rate": round(n_fraud / n_total * 100, 4) if n_total > 0 else 0.0,
            "baseline_loss": round(baseline_loss, 2),
            "avg_fraud_loss": self.avg_fraud_loss,
            "review_cost": self.review_cost,
        }

    def sample_transaction(self) -> dict:
        """
        Get a sample fraudulent transaction for API testing.

        Returns:
            Dictionary with sample transaction data
        """
        if self.df is None:
            raise ValueError("Dataset not loaded. Call load() first.")

        fraud_sample = self.df[self.df["Class"] == 1].iloc[0]
        return fraud_sample.drop("Class").to_dict()


def load_data(
    data_path: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Convenience function to load data and get stats.

    Args:
        data_path: Path to the CSV file

    Returns:
        Tuple of (DataFrame, stats_dict)
    """
    loader = DataLoader(data_path)
    df = loader.load()
    stats = loader.get_basic_stats()
    return df, stats
