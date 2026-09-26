"""
FraudLens — Shared Test Fixtures

Provides reusable fixtures for integration tests, API tests,
and mock external services (Anthropic, etc.).
"""

from collections.abc import Generator
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app() -> Any:
    """Get the FastAPI application."""
    from api.main import app

    return app


@pytest.fixture(scope="function")
def client(app) -> Generator:
    """Get a FastAPI TestClient per test function."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_transaction() -> dict[str, float]:
    """A valid transaction with all required features."""
    tx = {f"V{i}": round(float(np.random.randn()), 4) for i in range(1, 29)}
    tx["Time"] = 100000.0
    tx["Amount"] = 150.0
    return tx


@pytest.fixture
def sample_batch(sample_transaction) -> dict[str, list]:
    """A valid batch of transactions."""
    return {"transactions": [sample_transaction, sample_transaction]}


@pytest.fixture
def fraud_transaction() -> dict[str, float]:
    """A transaction engineered to look like fraud."""
    tx = {f"V{i}": round(float(np.random.randn()), 4) for i in range(1, 29)}
    tx["V14"] = round(float(np.random.uniform(-8, -3)), 4)
    tx["V4"] = round(float(np.random.uniform(3, 8)), 4)
    tx["Time"] = 100000.0
    tx["Amount"] = 2980.50
    return tx


@pytest.fixture
def small_training_data() -> tuple:
    """A small labeled dataset for training tests."""
    np.random.seed(42)
    n = 500
    data = {f"V{i}": np.random.randn(n) for i in range(1, 29)}
    data["Time"] = np.random.uniform(0, 172800, n)
    data["Amount"] = np.random.exponential(100, n)
    df = pd.DataFrame(data)
    y = pd.Series(np.random.choice([0, 1], n, p=[0.98, 0.02]))
    return df, y


@pytest.fixture
def trained_model(small_training_data) -> Any:
    """A small trained model for integration tests."""
    from src.fraudlens.models.train import FraudTrainer

    X, y = small_training_data
    trainer = FraudTrainer(models_to_train=["logistic_regression"])
    model = trainer.train_model("logistic_regression", X, y)
    return model, trainer


# Anthropic API Mock


@pytest.fixture(autouse=True)
def mock_anthropic(monkeypatch) -> Any:
    """
    Mock the Anthropic API client so tests never make real API calls.

    This fixture is auto-used — all tests automatically get the mock.
    To test with a real client, override this fixture in your test module.
    """
    import anthropic

    class MockMessage:
        class MockContent:
            text = "Mock narrative response for testing."

        content = [MockContent()]
        stop_reason = "end_turn"

    class MockMessages:
        def create(self, *args, **kwargs) -> Any:
            return MockMessage()

    class MockAnthropic:
        def __init__(self, *args, **kwargs):
            self.messages = MockMessages()

    monkeypatch.setattr(anthropic, "Anthropic", MockAnthropic)
    return MockAnthropic


# Feature Engineering Fixture


@pytest.fixture
def engineered_transaction() -> dict[str, float]:
    """A transaction with all base features (before engineering)."""
    tx = {f"V{i}": round(float(np.random.randn()), 4) for i in range(1, 29)}
    tx["Time"] = 50000.0
    tx["Amount"] = 250.0
    return tx


@pytest.fixture
def trained_engineer(small_training_data) -> Any:
    """A fitted FeatureEngineer for inference parity tests."""
    from src.fraudlens.features.engineering import FeatureEngineer

    X, _ = small_training_data
    engineer = FeatureEngineer(create_interactions=True, create_bins=True)
    X_eng = engineer.transform(X)
    return engineer, X_eng.shape[1]


@pytest.fixture
def recent_critical_drift_events() -> list:
    """Simulated drift events: 3 CRITICAL, 1 WARNING, timestamps in window."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    return [
        {
            "feature_name": "V14",
            "drift_score": 0.89,
            "alert_type": "CRITICAL",
            "created_at": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "feature_name": "V4",
            "drift_score": 0.76,
            "alert_type": "CRITICAL",
            "created_at": (now - timedelta(hours=2)).isoformat(),
        },
        {
            "feature_name": "V12",
            "drift_score": 0.92,
            "alert_type": "CRITICAL",
            "created_at": (now - timedelta(hours=3)).isoformat(),
        },
        {
            "feature_name": "Amount",
            "drift_score": 0.45,
            "alert_type": "WARNING",
            "created_at": (now - timedelta(hours=4)).isoformat(),
        },
    ]


@pytest.fixture
def trigger():
    """A RetrainingTrigger with low thresholds for easy testing."""
    from src.fraudlens.retraining.retrain_models import RetrainingTrigger

    return RetrainingTrigger(
        feedback_threshold=5,
        drift_critical_threshold=2,
        drift_window_days=7,
    )


@pytest.fixture
def sample_shap_explanation() -> list:
    """A list of SHAP feature contributions."""
    return [
        {"feature": "V14", "value": -5.23, "shap_value": 0.34, "impact": "increases"},
        {"feature": "V4", "value": 4.12, "shap_value": 0.22, "impact": "increases"},
        {"feature": "V12", "value": -3.89, "shap_value": 0.18, "impact": "increases"},
        {"feature": "V10", "value": 0.09, "shap_value": 0.11, "impact": "increases"},
        {"feature": "V17", "value": 0.21, "shap_value": -0.03, "impact": "decreases"},
    ]
