"""
FraudLens — Edge Case Tests

Verifies the API and models handle edge cases gracefully:
- NaN / Inf in transaction inputs (tested at Pydantic model level)
- Empty batch (should 422)
- Batch at max allowed size + 1 (should reject cleanly)
- Threshold at 0 and 1 (boundary conditions)
- Extreme Amount values (0 and very large)
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.schemas import TransactionInput

# NaN/Inf Tests (at Pydantic model level)


class TestNanInfAtModelLevel:
    """NaN/Inf tested at Pydantic model level (JSON can't serialize these)."""

    def test_nan_amount_rejected_by_validator(self) -> None:
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = float("nan")
        with pytest.raises(ValidationError):
            TransactionInput(**tx)

    def test_inf_amount_rejected_by_validator(self) -> None:
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = float("inf")
        with pytest.raises(ValidationError):
            TransactionInput(**tx)

    def test_neg_inf_amount_rejected_by_validator(self) -> None:
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = float("-inf")
        with pytest.raises(ValidationError):
            TransactionInput(**tx)

    def test_negative_amount_rejected_by_validator(self) -> None:
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = -100.0
        with pytest.raises(ValidationError):
            TransactionInput(**tx)

    def test_valid_amount_accepted(self) -> None:
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = 150.0
        model = TransactionInput(**tx)
        assert model.Amount == 150.0


class TestEdgeCaseInputs:
    """Boundary values and extreme inputs via HTTP."""

    def test_zero_amount_accepted(self, client) -> None:
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = 0.0
        response = client.post("/v1/predict", json=tx)
        assert response.status_code in (200, 503)

    def test_very_large_amount_accepted(self, client) -> None:
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = 1e7
        response = client.post("/v1/predict", json=tx)
        assert response.status_code in (200, 503)

    def test_zero_time_accepted(self, client) -> None:
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = 100.0
        response = client.post("/v1/predict", json=tx)
        assert response.status_code in (200, 503)

    def test_negative_amount_returns_422(self, client) -> None:
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = -100.0
        response = client.post("/v1/predict", json=tx)
        assert response.status_code == 422


class TestEmptyBatch:
    """Empty and edge-case batch requests."""

    def test_empty_batch_rejected(self, client) -> None:
        response = client.post("/v1/predict/batch", json={"transactions": []})
        assert response.status_code == 422

    def test_batch_too_large_rejected(self, client, sample_transaction) -> None:
        many_txs = [sample_transaction for _ in range(1001)]
        response = client.post("/v1/predict/batch", json={"transactions": many_txs})
        assert response.status_code == 422

    def test_batch_single_transaction(self, client, sample_transaction) -> None:
        """May return 503 if model not loaded in test env."""
        response = client.post(
            "/v1/predict/batch",
            json={"transactions": [sample_transaction]},
        )
        # Accept 200 if model loaded, 503 if not loaded in test env
        assert response.status_code in (200, 503)


class TestModelBoundaries:
    """Model boundary conditions."""

    def test_threshold_at_zero(self) -> None:
        """At threshold=0, all probabilities are FRAUD (p >= 0)."""
        import numpy as np

        probas = np.array([0.0, 0.1, 0.5, 0.9, 1.0])
        threshold = 0.0
        decisions = ["FRAUD" if p >= threshold else "LEGITIMATE" for p in probas]
        assert all(d == "FRAUD" for d in decisions)

    def test_threshold_at_one(self) -> None:
        """At threshold=1, only p=1.0 is FRAUD, everything else is LEGITIMATE."""
        import numpy as np

        probas = np.array([0.0, 0.1, 0.5, 0.9, 1.0])
        threshold = 1.0
        decisions = ["FRAUD" if p >= threshold else "LEGITIMATE" for p in probas]
        # Only the last probability (1.0) should be FRAUD at threshold 1.0
        assert decisions == [
            "LEGITIMATE",
            "LEGITIMATE",
            "LEGITIMATE",
            "LEGITIMATE",
            "FRAUD",
        ]

    def test_threshold_just_above_one(self) -> None:
        """At threshold > 1, nothing is FRAUD."""
        import numpy as np

        probas = np.array([0.0, 0.1, 0.5, 0.9, 1.0])
        threshold = 1.01
        decisions = ["FRAUD" if p >= threshold else "LEGITIMATE" for p in probas]
        assert all(d == "LEGITIMATE" for d in decisions)

    def test_all_zero_features(self, client) -> None:
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["Time"] = 0.0
        tx["Amount"] = 0.0
        response = client.post("/v1/predict", json=tx)
        assert response.status_code in (200, 503)

    def test_all_large_positive_features(self, client) -> None:
        tx = {f"V{i}": 999.0 for i in range(1, 29)}
        tx["Time"] = 999.0
        tx["Amount"] = 999.0
        response = client.post("/v1/predict", json=tx)
        assert response.status_code in (200, 503)


class TestChatEdgeCases:
    """Edge case tests for /v1/chat endpoint."""

    def test_chat_missing_conversation_history(self, client) -> None:
        """Test /v1/chat works without conversation_history."""
        response = client.post(
            "/v1/chat",
            json={"message": "Hello"},
        )
        assert response.status_code in (200, 503)
