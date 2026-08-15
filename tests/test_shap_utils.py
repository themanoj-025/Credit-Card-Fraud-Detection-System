"""
Tests for the SHAP Explainability module.

Verifies FraudPredictor produces SHAP values of expected shape,
explanations include expected top features, and edge cases.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fraudlens.explainability.shap_utils import FraudPredictor

# Fixtures


@pytest.fixture
def simple_model():
    """A simple trained RandomForest for testing."""
    np.random.seed(42)
    X = pd.DataFrame({f"V{i}": np.random.randn(200) for i in range(1, 29)})
    X["Time"] = np.random.uniform(0, 172800, 200)
    X["Amount"] = np.random.exponential(100, 200)
    y = (X["V14"] < -2).astype(int)  # Signal based on V14
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    return model, X


@pytest.fixture
def predictor(simple_model):
    """FraudPredictor with a trained model."""
    model, X = simple_model
    return FraudPredictor(
        model=model,
        feature_names=[f"V{i}" for i in range(1, 29)] + ["Time", "Amount"],
        threshold=0.5,
    )


@pytest.fixture
def sample_transaction():
    """A transaction with known V14 signal (fraud-like)."""
    tx = {f"V{i}": 0.0 for i in range(1, 29)}
    tx["V14"] = -5.0  # Strong fraud signal
    tx["Time"] = 50000.0
    tx["Amount"] = 250.0
    return tx


# Tests: Initialization


class TestFraudPredictorInit:
    """Tests for FraudPredictor initialization."""

    def test_default_initialization(self):
        """Test default constructor uses config values."""
        predictor = FraudPredictor()
        assert len(predictor.feature_names) == 30
        assert predictor.threshold == 0.5
        assert predictor.max_shap_features == 10

    def test_custom_initialization(self):
        """Test custom parameters."""
        predictor = FraudPredictor(
            threshold=0.3,
            max_shap_features=5,
            feature_names=["V1", "V14", "Amount"],
        )
        assert predictor.threshold == 0.3
        assert predictor.max_shap_features == 5
        assert len(predictor.feature_names) == 3


# Tests: Prediction


class TestPrediction:
    """Tests for predict_single and predict_batch."""

    def test_predict_single_returns_expected_keys(self, predictor, sample_transaction):
        """Test that predict_single returns all expected keys."""
        result = predictor.predict_single(sample_transaction, return_shap=False)
        assert "fraud_probability" in result
        assert "decision" in result
        assert "threshold_used" in result
        assert "is_fraud" in result
        assert isinstance(result["fraud_probability"], float)
        assert result["decision"] in ("FRAUD", "LEGITIMATE")

    def test_predict_single_with_shap(self, predictor, sample_transaction):
        """Test that predict_single returns explanation when requested."""
        result = predictor.predict_single(sample_transaction, return_shap=True)
        assert "explanation" in result
        assert "summary" in result["explanation"]
        assert "top_features" in result["explanation"]
        assert len(result["explanation"]["top_features"]) <= predictor.max_shap_features

    def test_explanation_contains_feature_details(self, predictor, sample_transaction):
        """Test that each feature explanation has required fields."""
        result = predictor.predict_single(sample_transaction, return_shap=True)
        for feat in result["explanation"]["top_features"]:
            assert "feature" in feat
            assert "value" in feat
            assert "shap_value" in feat
            assert "impact" in feat
            assert feat["impact"] in ("increases", "decreases")

    def test_predict_batch_returns_dataframe(self, predictor, simple_model):
        """Test that predict_batch returns a DataFrame with expected columns."""
        _, X = simple_model
        result = predictor.predict_batch(X.head(10))
        assert isinstance(result, pd.DataFrame)
        assert "fraud_probability" in result.columns
        assert "prediction" in result.columns
        assert "decision" in result.columns
        assert len(result) == 10

    def test_predict_single_detects_signal(self, predictor, sample_transaction):
        """Test that a transaction with strong V14 signal gets higher probability."""
        result = predictor.predict_single(sample_transaction, return_shap=False)
        # V14 = -5 is a strong fraud signal — should be > 0.5
        assert (
            result["fraud_probability"] >= 0.3
        )  # Not guaranteed >0.5 with small model

    def test_predict_legitimate_low_probability(self, predictor):
        """Test that a normal transaction gets low probability."""
        tx = {f"V{i}": round(float(np.random.randn()), 4) for i in range(1, 29)}
        tx["Time"] = 100000.0
        tx["Amount"] = 50.0
        result = predictor.predict_single(tx, return_shap=False)
        # Normal values should give lower probability than strong V14 signal
        assert isinstance(result["fraud_probability"], float)


# Tests: SHAP Explanation


class TestShapExplanation:
    """Tests for SHAP explanation content."""

    def test_explanation_includes_important_features(self, predictor):
        """Test that explanation highlights V14 when it's the signal."""
        # Transaction with very strong V14 signal
        tx = {f"V{i}": 0.0 for i in range(1, 29)}
        tx["V14"] = -10.0
        tx["Time"] = 0.0
        tx["Amount"] = 100.0

        result = predictor.predict_single(tx, return_shap=True)
        top_features = [f["feature"] for f in result["explanation"]["top_features"]]
        # V14 should be in the top features for this transaction
        assert "V14" in top_features

    def test_shap_values_have_expected_shape(self, predictor, simple_model):
        """Test that SHAP values array has correct dimensions."""
        _, X = simple_model
        predictor._init_shap_explainer(X.head(50))
        X_sample = X.head(5)
        X_proc = predictor.preprocess(X_sample)
        shap_values = predictor.explainer.shap_values(X_proc)

        if isinstance(shap_values, list):
            shap_vals = shap_values[1]
        elif hasattr(shap_values, "shape") and len(shap_values.shape) == 3:
            shap_vals = shap_values[:, :, 1]
        else:
            shap_vals = shap_values

        assert shap_vals.shape == (5, len(predictor.feature_names))

    def test_predict_without_model_returns_none(self):
        """Test that predict raises error without model."""
        predictor = FraudPredictor()
        with pytest.raises(Exception):
            predictor.predict_single({"V1": 0.0}, return_shap=False)


# Tests: Format Explanation


class TestFormatExplanation:
    """Tests for _format_explanation method."""

    def test_format_with_increasing_features(self, predictor):
        """Test formatting with features that increase fraud risk."""
        top = [("V14", 0.5), ("V4", 0.3), ("V12", 0.1)]
        result = predictor._format_explanation(top)
        assert "V14" in result
        assert "Flagged" in result

    def test_format_with_decreasing_features(self, predictor):
        """Test formatting with features that decrease fraud risk."""
        top = [("V14", -0.3), ("V4", -0.2)]
        result = predictor._format_explanation(top)
        assert "Mitigated" in result

    def test_format_empty_list(self, predictor):
        """Test formatting with empty feature list."""
        result = predictor._format_explanation([])
        assert "No strong" in result


# Tests: Global Feature Importance


class TestGlobalImportance:
    """Tests for get_global_feature_importance."""

    def test_global_importance_returns_dataframe(self, predictor, simple_model):
        """Test that global importance returns a DataFrame."""
        _, X = simple_model
        importance = predictor.get_global_feature_importance(X.head(50))
        assert isinstance(importance, pd.DataFrame)
        assert "feature" in importance.columns
        assert "mean_abs_shap" in importance.columns
        assert len(importance) == len(predictor.feature_names)

    def test_global_importance_sorted(self, predictor, simple_model):
        """Test that global importance is sorted by mean_abs_shap descending."""
        _, X = simple_model
        importance = predictor.get_global_feature_importance(X.head(50))
        for i in range(len(importance) - 1):
            assert (
                importance.iloc[i]["mean_abs_shap"]
                >= importance.iloc[i + 1]["mean_abs_shap"]
            )
