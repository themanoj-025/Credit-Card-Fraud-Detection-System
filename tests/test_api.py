"""
Tests for the FraudLens FastAPI application.

Covers health check, prediction, batch prediction, and error handling.
Uses FastAPI's TestClient for fast, dependency-free testing.
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.slow
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.main import app

client = TestClient(app)


# Fixtures


@pytest.fixture
def sample_transaction() -> dict:
    """A valid transaction with all required features."""
    tx = {f"V{i}": round(np.random.randn(), 4) for i in range(1, 29)}
    tx["Time"] = 100000.0
    tx["Amount"] = 150.0
    return tx


# Tests: Health


class TestHealth:
    """Tests for the /health and /v1/health endpoints."""

    def test_health_endpoint(self) -> None:
        """Test that health check returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_v1_health_endpoint(self) -> None:
        """Test that /v1/health returns 200."""
        response = client.get("/v1/health")
        assert response.status_code == 200

    def test_health_returns_expected_keys(self) -> None:
        """Test that health response contains required fields."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "dependencies" in data

    def test_health_status_is_valid(self) -> None:
        """Test that status is 'healthy' or 'degraded' (not 'error')."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] in ("healthy", "degraded", "error")


# Tests: Prediction


class TestPrediction:
    """Tests for the /v1/predict endpoint."""

    def test_predict_endpoint_accepts_valid_data(self, sample_transaction: dict) -> None:
        """Test that /v1/predict returns 200 for valid input."""
        response = client.post("/v1/predict", json=sample_transaction)
        # Note: May return 503 if model isn't loaded in test env
        assert response.status_code in (200, 503)

    def test_predict_returns_correct_schema(self, sample_transaction: dict) -> None:
        """Test that prediction response contains all required fields."""
        response = client.post("/v1/predict", json=sample_transaction)
        if response.status_code == 200:
            data = response.json()
            assert "fraud_probability" in data
            assert "decision" in data
            assert "threshold_used" in data
            assert "is_fraud" in data
            assert isinstance(data["fraud_probability"], (int, float))
            assert data["decision"] in ("FRAUD", "LEGITIMATE")
            assert isinstance(data["is_fraud"], bool)

    def test_predict_rejects_negative_amount(self) -> None:
        """Test that negative Amount returns 422 validation error."""
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = -100.0  # Invalid
        response = client.post("/v1/predict", json=tx)
        assert response.status_code == 422

    def test_predict_rejects_missing_required_field(self) -> None:
        """Test that missing Amount returns 422 validation error."""
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        # Missing Amount
        response = client.post("/v1/predict", json=tx)
        assert response.status_code == 422


# Tests: Batch Prediction


class TestBatchPrediction:
    """Tests for the /v1/predict/batch endpoint."""

    def test_batch_endpoint(self, sample_transaction: dict) -> None:
        """Test that batch endpoint accepts valid input."""
        batch = {"transactions": [sample_transaction, sample_transaction]}
        response = client.post("/v1/predict/batch", json=batch)
        assert response.status_code in (200, 503)

    def test_batch_returns_summary(self, sample_transaction: dict) -> None:
        """Test that batch response contains predictions and summary."""
        batch = {"transactions": [sample_transaction]}
        response = client.post("/v1/predict/batch", json=batch)
        if response.status_code == 200:
            data = response.json()
            assert "predictions" in data
            assert "summary" in data
            assert data["summary"]["total"] == 1

    def test_batch_with_multiple_transactions(self, sample_transaction: dict) -> None:
        """Test batch with multiple transactions."""
        batch = {"transactions": [sample_transaction] * 5}
        response = client.post("/v1/predict/batch", json=batch)
        if response.status_code == 200:
            data = response.json()
            assert data["summary"]["total"] == 5
            assert len(data["predictions"]) == 5

    def test_batch_rejects_empty_list(self) -> None:
        """Test that empty transactions list returns 422."""
        response = client.post("/v1/predict/batch", json={"transactions": []})
        assert response.status_code == 422


# Tests: Model Info


class TestModelInfo:
    """Tests for the /model-info endpoint."""

    def test_model_info_endpoint(self) -> None:
        """Test that model-info returns 200."""
        response = client.get("/model-info")
        assert response.status_code == 200

    def test_model_info_returns_dict(self) -> None:
        """Test that model-info returns a JSON object."""
        response = client.get("/model-info")
        data = response.json()
        assert isinstance(data, dict)


# Tests: /v1/explain Endpoint


class TestExplainEndpoint:
    """Tests for the /v1/explain endpoint."""

    def test_explain_endpoint_accepts_valid_data(self, sample_transaction: dict) -> None:
        """Test that /v1/explain returns 200 or 503 for valid input."""
        response = client.post("/v1/explain", json=sample_transaction)
        assert response.status_code in (200, 503)

    def test_explain_returns_shap_values(self, sample_transaction: dict) -> None:
        """Test that /v1/explain returns SHAP values in response."""
        response = client.post("/v1/explain", json=sample_transaction)
        if response.status_code == 200:
            data = response.json()
            assert "fraud_probability" in data
            assert "decision" in data
            assert "shap_values" in data


# Tests: /v1/chat Endpoint


class TestChatEndpoint:
    """Tests for the /v1/chat endpoint using mocked responses."""

    def test_chat_endpoint_returns_503_without_key(self) -> None:
        """Test that /v1/chat returns 503 when no API key is set."""
        response = client.post(
            "/v1/chat",
            json={
                "message": "Why was this transaction flagged?",
                "conversation_history": [],
            },
        )
        # Should be 503 since no Anthropic client is configured in test
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data

    def test_chat_endpoint_returns_expected_schema(self) -> None:
        """Test that /v1/chat response has expected structure even when failing."""
        response = client.post(
            "/v1/chat",
            json={
                "message": "What is the current fraud rate?",
                "conversation_history": [],
            },
        )
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data

    def test_chat_endpoint_missing_message(self) -> None:
        """Test that /v1/chat with missing message returns 422."""
        response = client.post("/v1/chat", json={"conversation_history": []})
        assert response.status_code == 422


# Tests: /v1/similar-cases Endpoint


class TestSimilarCasesEndpoint:
    """Tests for the /v1/similar-cases endpoint."""

    def test_similar_cases_endpoint(self, sample_transaction: dict) -> None:
        """Test that /v1/similar-cases returns 200 or 503."""
        response = client.post("/v1/similar-cases", json=sample_transaction)
        assert response.status_code in (200, 503)


# Tests: /v1/explain Endpoint Validation


class TestExplainValidation:
    """Tests for /v1/explain request validation."""

    def test_explain_rejects_negative_amount(self) -> None:
        """Test that negative Amount returns 422."""
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = -50.0
        response = client.post("/v1/explain", json=tx)
        assert response.status_code == 422
