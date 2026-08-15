"""
FraudLens — Anomaly Detection Tests

Tests for IsolationForestDetector only.
AutoencoderDetector was removed per ADR-0001.
"""

import numpy as np
import pandas as pd
import pytest

from src.fraudlens.models.anomaly import IsolationForestDetector


@pytest.fixture
def normal_data():
    """Create a small dataset of normal (legitimate) transactions."""
    np.random.seed(42)
    n = 100
    X = pd.DataFrame({f"V{i}": np.random.randn(n) for i in range(1, 29)})
    X["Time"] = np.random.uniform(0, 172800, n)
    X["Amount"] = np.random.exponential(100, n)
    return X


@pytest.fixture
def labeled_data(normal_data):
    """Create a dataset with labels (mostly normal, a few fraud)."""
    np.random.seed(42)
    n = len(normal_data)
    y = pd.Series(np.random.choice([0, 1], n, p=[0.95, 0.05]))
    return normal_data, y


class TestIsolationForestDetector:
    """Tests for IsolationForestDetector."""

    def test_init_defaults(self):
        """Test default initialization parameters."""
        detector = IsolationForestDetector()
        assert detector.contamination == 0.01
        assert detector.n_estimators == 200
        assert detector.random_state == 42
        assert detector.model is None

    def test_init_custom(self):
        """Test custom initialization."""
        detector = IsolationForestDetector(
            contamination=0.05, n_estimators=100, random_state=123
        )
        assert detector.contamination == 0.05
        assert detector.n_estimators == 100
        assert detector.random_state == 123

    def test_fit_with_labels(self, labeled_data):
        """Test fit with labels trains on legitimate only."""
        X, y = labeled_data
        detector = IsolationForestDetector()
        detector.fit(X, y)

        assert detector.model is not None
        assert hasattr(detector.model, "predict")

    def test_fit_without_labels(self, normal_data):
        """Test fit without labels trains on all data."""
        detector = IsolationForestDetector()
        detector.fit(normal_data)

        assert detector.model is not None

    def test_predict_returns_minus_one_or_one(self, labeled_data):
        """Test predict returns -1 (anomaly) or 1 (normal)."""
        X, y = labeled_data
        detector = IsolationForestDetector()
        detector.fit(X, y)
        predictions = detector.predict(X)

        assert len(predictions) == len(X)
        assert set(predictions).issubset({-1, 1})

    def test_predict_not_fitted(self, normal_data):
        """Test predict raises ValueError when not fitted."""
        detector = IsolationForestDetector()
        with pytest.raises(ValueError, match="Model not fitted"):
            detector.predict(normal_data)

    def test_score_returns_float_array(self, labeled_data):
        """Test score returns array of floats."""
        X, y = labeled_data
        detector = IsolationForestDetector()
        detector.fit(X, y)
        scores = detector.score(X)

        assert isinstance(scores, np.ndarray)
        assert len(scores) == len(X)
        assert np.issubdtype(scores.dtype, np.floating)

    def test_score_not_fitted(self, normal_data):
        """Test score raises ValueError when not fitted."""
        detector = IsolationForestDetector()
        with pytest.raises(ValueError, match="Model not fitted"):
            detector.score(normal_data)

    def test_predict_proba_as_fraud_range(self, labeled_data):
        """Test predict_proba_as_fraud returns values in [0, 1]."""
        X, y = labeled_data
        detector = IsolationForestDetector()
        detector.fit(X, y)
        probas = detector.predict_proba_as_fraud(X)

        assert len(probas) == len(X)
        assert probas.min() >= 0.0
        assert probas.max() <= 1.0

    def test_predict_proba_as_fraud_not_fitted(self, normal_data):
        """Test predict_proba_as_fraud raises when not fitted."""
        detector = IsolationForestDetector()
        with pytest.raises(ValueError, match="Model not fitted"):
            detector.predict_proba_as_fraud(normal_data)

    def test_fit_with_y_none(self, normal_data):
        """Test fit() with only X argument."""
        detector = IsolationForestDetector()
        detector.fit(normal_data)
        assert detector.model is not None
