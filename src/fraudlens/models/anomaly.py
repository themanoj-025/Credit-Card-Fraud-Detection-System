"""
Anomaly Detection Module

Unsupervised anomaly detection models for fraud detection.
Provides an alternative signal to supervised models:
- "Known fraud pattern match" (supervised model)
- "Statistically unusual, possibly a new pattern" (anomaly detector)
"""

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from src.fraudlens.config import (
    IFOREST_CONTAMINATION,
    IFOREST_N_ESTIMATORS,
    RANDOM_STATE,
)

logger = logging.getLogger(__name__)


class IsolationForestDetector:
    """
    Unsupervised anomaly detection using Isolation Forest.

    Trained ONLY on legitimate transactions to learn "normal" patterns.
    Anomalies (high negative scores) are flagged as potential fraud,
    making this useful for catching *novel* fraud patterns the supervised
    model hasn't seen before.
    """

    def __init__(
        self,
        contamination: float = IFOREST_CONTAMINATION,
        n_estimators: int = IFOREST_N_ESTIMATORS,
        random_state: int = RANDOM_STATE,
    ) -> None:
        """
        Args:
            contamination: Expected proportion of anomalies in the data
            n_estimators: Number of isolation trees
            random_state: Random seed for reproducibility
        """
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model: IsolationForest | None = None

    def fit(
        self, X_train: pd.DataFrame, y_train: pd.Series | None = None
    ) -> "IsolationForestDetector" -> None:
        """
        Fit on legitimate transactions only.

        Args:
            X_train: Training features
            y_train: Training labels (used to filter legitimate only)
        """
        if y_train is not None:
            X_legit = X_train[y_train == 0]
            logger.info(
                "Training Isolation Forest on %d legitimate transactions (excluded %d fraud samples)",
                len(X_legit),
                int((y_train == 1).sum()),
            )
        else:
            X_legit = X_train
            logger.info("Training Isolation Forest on %d transactions", len(X_legit))

        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.model.fit(X_legit)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict anomalies.

        Returns:
            Array of -1 (anomaly) and 1 (normal)
        """
        if self.model is None:
            raise ValueError("Model not fitted. Call fit() first.")
        return self.model.predict(X)

    def score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get anomaly scores (lower = more anomalous).

        Returns:
            Array of anomaly scores
        """
        if self.model is None:
            raise ValueError("Model not fitted. Call fit() first.")
        return self.model.score_samples(X)

    def predict_proba_as_fraud(self, X: pd.DataFrame) -> np.ndarray:
        """
        Convert anomaly scores to fraud-like probabilities (0-1).

        Higher scores = more likely to be fraud/anomalous.

        Returns:
            Array of scores between 0 and 1
        """
        scores = self.score(X)
        min_score = scores.min()
        max_score = scores.max()
        probas = 1 - (scores - min_score) / (max_score - min_score + 1e-10)
        return probas
