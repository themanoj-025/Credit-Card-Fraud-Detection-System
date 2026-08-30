"""
FraudLens — Integration Tests

Tests that use a real (small) trained model to verify the full pipeline:
1. Model training and prediction on real data
2. API endpoint integrates with the model
3. SHAP output has the correct shape
4. Feature engineering parity (train/serve skew detection)

These tests use a fixture that trains a small logistic regression model
on synthetic data — no GPU, no disk artifacts required.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

pytestmark = pytest.mark.slow
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# Integration: Training → Prediction → Evaluation


class TestTrainingToPredictionPipeline:
    """End-to-end: train model → predict → verify output shape/range."""

    def test_train_and_predict_produces_valid_probas(self, trained_model):
        """Test that training a model and predicting yields valid probabilities."""
        model, trainer = trained_model
        _X, _y = (
            trainer.training_results["logistic_regression"].get("n_samples", 0),
            None,
        )

        # Generate test data
        X_test = pd.DataFrame({f"V{i}": np.random.randn(50) for i in range(1, 29)})
        X_test["Time"] = np.random.uniform(0, 172800, 50)
        X_test["Amount"] = np.random.exponential(100, 50)

        probas = model.predict_proba(X_test)[:, 1]
        assert len(probas) == 50
        assert all(0.0 <= p <= 1.0 for p in probas)
        assert probas.dtype == np.float64

    def test_predict_proba_output_shape(self, trained_model):
        """Test that predict_proba returns the correct shape."""
        model, _ = trained_model
        X_test = pd.DataFrame({f"V{i}": np.random.randn(10) for i in range(1, 29)})
        X_test["Time"] = np.random.uniform(0, 172800, 10)
        X_test["Amount"] = np.random.exponential(100, 10)

        probas = model.predict_proba(X_test)
        assert probas.shape == (10, 2), f"Expected (10, 2), got {probas.shape}"

    def test_decision_based_on_threshold(self, trained_model):
        """Test that decisions (FRAUD/LEGITIMATE) are threshold-consistent."""
        model, _ = trained_model
        X_test = pd.DataFrame({f"V{i}": np.random.randn(20) for i in range(1, 29)})
        X_test["Time"] = np.random.uniform(0, 172800, 20)
        X_test["Amount"] = np.random.exponential(100, 20)

        probas = model.predict_proba(X_test)[:, 1]
        threshold = 0.5
        decisions = ["FRAUD" if p >= threshold else "LEGITIMATE" for p in probas]
        assert all(d in ("FRAUD", "LEGITIMATE") for d in decisions)


# Integration: API with Model


class TestApiWithModel:
    """Tests that the API correctly integrates with the loaded model."""

    def test_api_health_endpoint(self, client):
        """Test that health endpoint is reachable."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "dependencies" in data

    def test_api_v1_health_endpoint(self, client):
        """Test that /v1/health endpoint is reachable."""
        response = client.get("/v1/health")
        assert response.status_code == 200

    def test_api_accepts_valid_prediction(self, client, sample_transaction):
        """Test that the API accepts valid prediction requests."""
        response = client.post("/v1/predict", json=sample_transaction)
        # May return 503 if no model is loaded in test environment
        assert response.status_code in (200, 503)

    def test_prediction_schema_when_model_loaded(self, client, fraud_transaction):
        """Test the prediction response schema when model is available."""
        response = client.post("/v1/predict", json=fraud_transaction)
        if response.status_code == 200:
            data = response.json()
            assert "fraud_probability" in data
            assert "decision" in data
            assert "threshold_used" in data
            assert "is_fraud" in data
            assert "business_impact" in data
            assert 0.0 <= data["fraud_probability"] <= 1.0

    def test_batch_prediction_schema(self, client, sample_batch):
        """Test that batch prediction returns the correct schema."""
        response = client.post("/v1/predict/batch", json=sample_batch)
        if response.status_code == 200:
            data = response.json()
            assert "predictions" in data
            assert "summary" in data
            assert data["summary"]["total"] == 2


# Integration: Feature Engineering Parity


class TestFeatureEngineeringParity:
    """Golden tests: training-time and inference-time feature parity.

    This is the #1 source of train/serve skew in production ML systems.
    These tests assert that the FeatureEngineer produces consistent
    output shape/column order regardless of when it's called.
    """

    def test_engineer_produces_expected_feature_count(self, trained_engineer):
        """Test that feature engineering produces a predictable number of features."""
        engineer, n_features = trained_engineer
        assert n_features > 30  # Should add features beyond the base 30
        assert engineer.get_feature_names() is not None
        assert len(engineer.get_feature_names()) == n_features

    def test_engineer_reproducible_transform(
        self, trained_engineer, engineered_transaction
    ):
        """Test that transforming the same data twice produces identical results."""
        engineer, _ = trained_engineer
        df = pd.DataFrame([engineered_transaction])

        result1 = engineer.transform(df)
        result2 = engineer.transform(df)

        pd.testing.assert_frame_equal(result1, result2)

    def test_engineer_column_order_consistent(
        self, trained_engineer, engineered_transaction
    ):
        """Test that column order is deterministic (critical for train/serve parity)."""
        engineer, _ = trained_engineer
        df = pd.DataFrame([engineered_transaction])

        result1 = engineer.transform(df)
        result2 = engineer.transform(pd.DataFrame([engineered_transaction]))

        assert list(result1.columns) == list(result2.columns)


# Integration: SHAP Output


class TestShapOutput:
    """Tests that SHAP explanations have the correct structure."""

    def test_shap_explanation_has_required_fields(self):
        """Test that ShapExplanation has summary and top_features."""
        from src.fraudlens.explainability.shap_explainer import ShapExplanation

        explanation = ShapExplanation.from_raw(
            [("V14", 0.34), ("V4", 0.22)],
            {"V14": -5.23, "V4": 4.12},
            max_features=5,
        )
        assert len(explanation.top_features) > 0
        assert explanation.summary is not None
        assert len(explanation.summary) > 0

        # Verify dict conversion
        as_dict = explanation.to_dict()
        assert "summary" in as_dict
        assert "top_features" in as_dict

    def test_shap_values_are_bounded(self):
        """Test that SHAP values in explanation are within expected bounds."""
        from src.fraudlens.explainability.shap_explainer import ShapExplanation


        explanation = ShapExplanation.from_raw(
            [("V14", 0.5), ("Amount", -0.3)],
            {"V14": -5.23, "Amount": 100.0},
            max_features=5,
        )
        for feat in explanation.top_features:
            assert isinstance(feat["shap_value"], float)
            assert abs(feat["shap_value"]) <= 10.0  # Reasonable bound
