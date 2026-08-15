"""
FraudLens — Locust Load Tests

Measures p50/p95/p99 latency for /predict and /predict/batch endpoints.

Usage:
    # Start the API server first:
    uvicorn api.main:app --host 0.0.0.0 --port 8000

    # Run locust:
    locust -f tests/load/locustfile.py --host http://localhost:8000

    # Or run headless for CI:
    locust -f tests/load/locustfile.py --host http://localhost:8000 \\
        --headless -u 10 -r 2 --run-time 30s --csv=tests/load/results
"""

import random

from locust import HttpUser, between, task

# Sample transaction data (generated from PCA distribution)

_SAMPLE_TRANSACTIONS: list[dict[str, float]] = []
for _ in range(100):
    tx: dict[str, float] = {"Time": random.uniform(0, 172792)}
    for i in range(1, 29):
        tx[f"V{i}"] = random.uniform(-5, 5)
    tx["Amount"] = random.uniform(0, 1000)
    _SAMPLE_TRANSACTIONS.append(tx)


class FraudPredictionUser(HttpUser):
    """Simulates a user hitting the fraud prediction API."""

    wait_time = between(0.5, 2.0)  # Wait 0.5-2s between tasks

    def on_start(self) -> None:
        """Prepare headers and test data on user start."""
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": "test-load-key",
        }

    @task(7)  # 70% of requests — single prediction (hot path)
    def predict_single(self) -> None:
        """Test single prediction endpoint."""
        tx = random.choice(_SAMPLE_TRANSACTIONS)
        with self.client.post(
            "/predict",
            json=tx,
            headers=self.headers,
            catch_response=True,
            name="/predict",
        ) as response:
            if response.status_code not in (200, 503):
                response.failure(f"Unexpected status: {response.status_code}")

    @task(2)  # 20% of requests — single prediction with SHAP
    def predict_single_with_explain(self) -> None:
        """Test single prediction with SHAP explanation enabled."""
        tx = random.choice(_SAMPLE_TRANSACTIONS)
        with self.client.post(
            "/predict?explain=true",
            json=tx,
            headers=self.headers,
            catch_response=True,
            name="/predict (explain)",
        ) as response:
            if response.status_code not in (200, 503):
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)  # 10% of requests — batch prediction
    def predict_batch(self) -> None:
        """Test batch prediction endpoint."""
        batch = {"transactions": random.choices(_SAMPLE_TRANSACTIONS, k=10)}
        with self.client.post(
            "/predict/batch",
            json=batch,
            headers=self.headers,
            catch_response=True,
            name="/predict/batch",
        ) as response:
            if response.status_code not in (200, 503):
                response.failure(f"Unexpected status: {response.status_code}")
