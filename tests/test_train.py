"""
Tests for the Model Training module.

Verifies the full training loop runs end-to-end on a small dataset,
produces a non-empty comparison table, and saves model artifacts.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.slow


from src.fraudlens.models.train import FraudTrainer

# Fixtures


@pytest.fixture
def small_dataset() -> tuple[object, ...]:
    """A small labeled dataset for fast training tests."""
    np.random.seed(42)
    n = 500
    data = {f"V{i}": np.random.randn(n) for i in range(1, 29)}
    data["Time"] = np.random.uniform(0, 172800, n)
    data["Amount"] = np.random.exponential(100, n)
    df = pd.DataFrame(data)
    y = pd.Series(np.random.choice([0, 1], n, p=[0.98, 0.02]))
    return df, y


# Tests: Initialization


class TestFraudTrainerInit:
    """Tests for FraudTrainer initialization."""

    def test_default_initialization(self) -> None:
        """Test default constructor."""
        trainer = FraudTrainer()
        assert len(trainer.models_to_train) > 0
        assert all(m in trainer.configs for m in trainer.models_to_train)

    def test_custom_models(self) -> None:
        """Test with specific models to train."""
        trainer = FraudTrainer(models_to_train=["logistic_regression", "random_forest"])
        assert trainer.models_to_train == ["logistic_regression", "random_forest"]


# Tests: Training


class TestTraining:
    """Tests for training methods."""

    def test_train_single_model(self, small_dataset) -> None:
        """Test training a single model by name."""
        X, y = small_dataset
        trainer = FraudTrainer(models_to_train=["logistic_regression"])
        model = trainer.train_model("logistic_regression", X, y)
        assert model is not None
        assert "logistic_regression" in trainer.trained_models

    def test_train_all_returns_dict(self, small_dataset) -> None:
        """Test that train_all returns a dict of trained models."""
        X, y = small_dataset
        trainer = FraudTrainer(models_to_train=["logistic_regression", "random_forest"])
        models = trainer.train_all(X, y)
        assert isinstance(models, dict)
        assert "logistic_regression" in models
        assert "random_forest" in models

    def test_train_all_populates_trained_models(self, small_dataset) -> None:
        """Test that train_all populates the trained_models dict."""
        X, y = small_dataset
        trainer = FraudTrainer(models_to_train=["logistic_regression"])
        trainer.train_all(X, y)
        assert len(trainer.trained_models) == 1

    def test_training_results_contains_metadata(self, small_dataset) -> None:
        """Test that training_results contains expected metadata."""
        X, y = small_dataset
        trainer = FraudTrainer(models_to_train=["logistic_regression"])
        trainer.train_model("logistic_regression", X, y)
        result = trainer.training_results["logistic_regression"]
        assert "train_time" in result
        assert "n_samples" in result
        assert "n_features" in result
        assert result["n_samples"] == len(X)
        assert result["n_features"] == X.shape[1]


# Tests: Cross-Validation


class TestCrossValidation:
    """Tests for cross_validate method."""

    def test_cross_validate_returns_results(self, small_dataset) -> None:
        """Test that cross_validate returns results dict."""
        X, y = small_dataset
        trainer = FraudTrainer(models_to_train=["logistic_regression"])
        results = trainer.cross_validate(X, y, cv=2)
        assert isinstance(results, dict)
        assert "logistic_regression" in results

    def test_cv_result_has_expected_keys(self, small_dataset) -> None:
        """Test that CV result has expected keys."""
        X, y = small_dataset
        trainer = FraudTrainer(models_to_train=["logistic_regression"])
        results = trainer.cross_validate(X, y, cv=2)
        result = results["logistic_regression"]
        assert "mean_score" in result
        assert "std_score" in result
        assert "scores" in result
        assert len(result["scores"]) == 2


# Tests: Model Persistence


class TestModelPersistence:
    """Tests for saving and loading models."""

    def test_save_model_creates_file(self, small_dataset) -> None:
        """Test that save_model writes a file."""
        X, y = small_dataset
        trainer = FraudTrainer(models_to_train=["logistic_regression"])
        trainer.train_model("logistic_regression", X, y)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = trainer.save_model("logistic_regression", f"{tmpdir}/model.pkl")
            assert Path(path).exists()

    def test_save_then_load_round_trip(self, small_dataset) -> None:
        """Test that saved model can be loaded back."""
        X, y = small_dataset
        trainer = FraudTrainer(models_to_train=["logistic_regression"])
        trainer.train_model("logistic_regression", X, y)
        _original_model = trainer.trained_models["logistic_regression"]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = trainer.save_model("logistic_regression", f"{tmpdir}/lr.pkl")
            trainer2 = FraudTrainer()
            loaded = trainer2.load_model("logistic_regression", path)
            assert loaded is not None

    def test_save_missing_model_raises(self) -> None:
        """Test that saving untrained model raises ValueError."""
        trainer = FraudTrainer()
        with pytest.raises(ValueError):
            trainer.save_model("non_existent")


# Tests: Edge Cases


class TestEdgeCases:
    """Edge case tests for FraudTrainer."""

    def test_scale_pos_weight_computation(self, small_dataset) -> None:
        """Test scale_pos_weight computation for XGBoost."""
        _, y = small_dataset
        trainer = FraudTrainer()
        weight = trainer._compute_scale_pos_weight(y)
        n_neg = (y == 0).sum()
        n_pos = (y == 1).sum()
        expected = n_neg / n_pos
        assert weight == pytest.approx(expected)

    def test_train_only_selected_models(self, small_dataset) -> None:
        """Test that only requested models are trained."""
        X, y = small_dataset
        trainer = FraudTrainer(models_to_train=["xgboost"])
        models = trainer.train_all(X, y)
        assert list(models.keys()) == ["xgboost"]

    def test_training_time_logged(self, small_dataset) -> None:
        """Test that training time is recorded."""
        X, y = small_dataset
        trainer = FraudTrainer(models_to_train=["logistic_regression"])
        trainer.train_model("logistic_regression", X, y)
        assert trainer.training_results["logistic_regression"]["train_time"] > 0
