"""
FraudLens — Model Selection Tests

Tests for ModelSelector: selection logic, edge cases, and MLflow interaction.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.fraudlens.models.model_selection import ModelSelector


@pytest.fixture
def comparison_data():
    """Create a mock comparison DataFrame with two models."""
    return pd.DataFrame(
        {
            "Model": ["LogisticRegression", "XGBoost"],
            "PR-AUC": [0.75, 0.88],
            "ROC-AUC": [0.85, 0.93],
            "F1": [0.65, 0.78],
        }
    )


class _SimpleModel:
    """A simple pickle-able model stub for testing."""

    def __init__(self, name: str):
        self.name = name

    def predict(self, X):
        return [0] * len(X)


@pytest.fixture
def trained_models():
    """Create a dict of trained model objects (pickle-able)."""
    return {"LogisticRegression": _SimpleModel("LR"), "XGBoost": _SimpleModel("XGB")}


class TestModelSelector:
    """Tests for ModelSelector."""

    def test_init_defaults(self):
        """Test default initialization uses config values."""
        selector = ModelSelector()
        assert selector.metric == "pr_auc"
        assert selector.higher_is_better is True
        assert selector.selection_result is None

    def test_init_custom(self):
        """Test custom initialization."""
        selector = ModelSelector(metric="f1", higher_is_better=True)
        assert selector.metric == "f1"
        assert selector.higher_is_better is True

    def test_init_lower_is_better(self):
        """Test that lower_is_better works (e.g., for error metrics)."""
        selector = ModelSelector(metric="mse", higher_is_better=False)
        assert selector.higher_is_better is False

    def test_select_picks_highest_metric(self, comparison_data, trained_models):
        """Test select picks the model with highest PR-AUC."""
        selector = ModelSelector(metric="PR-AUC")
        result = selector.select(comparison_data, trained_models)

        assert result["best_model_name"] == "XGBoost"
        assert result["metric_value"] == 0.88
        assert "PR-AUC" in result["metric_used"]

    def test_select_returns_all_keys(self, comparison_data, trained_models):
        """Test select returns the expected result structure."""
        selector = ModelSelector(metric="PR-AUC")
        result = selector.select(comparison_data, trained_models)

        assert "best_model_name" in result
        assert "best_model" in result
        assert "metric_used" in result
        assert "metric_value" in result
        assert "reasoning" in result
        assert "ranking" in result

    def test_select_stores_selection_result(self, comparison_data, trained_models):
        """Test select updates self.selection_result."""
        selector = ModelSelector(metric="PR-AUC")
        selector.select(comparison_data, trained_models)

        assert selector.selection_result is not None
        assert selector.selection_result["best_model_name"] == "XGBoost"

    def test_select_ranking_is_sorted(self, comparison_data, trained_models):
        """Test ranking DataFrame is sorted by metric descending."""
        selector = ModelSelector(metric="PR-AUC")
        result = selector.select(comparison_data, trained_models)

        ranking = result["ranking"]
        assert ranking.iloc[0]["PR-AUC"] >= ranking.iloc[1]["PR-AUC"]

    def test_select_with_lower_is_better(self, trained_models):
        """Test select picks lowest metric when higher_is_better is False."""
        data = pd.DataFrame(
            {
                "Model": ["ModelA", "ModelB"],
                "mse": [0.5, 0.3],
            }
        )
        models = {"ModelA": MagicMock(), "ModelB": MagicMock()}
        selector = ModelSelector(metric="mse", higher_is_better=False)
        result = selector.select(data, models)

        assert result["best_model_name"] == "ModelB"  # Lower MSE is better

    def test_select_metric_not_found(self, comparison_data, trained_models):
        """Test select raises ValueError when metric column is missing."""
        selector = ModelSelector(metric="nonexistent")

        with pytest.raises(ValueError, match="Metric 'nonexistent' not found"):
            selector.select(comparison_data, trained_models)

    def test_select_model_not_in_dict(self, comparison_data):
        """Test select raises KeyError when best model not in trained_models."""
        selector = ModelSelector(metric="PR-AUC")
        empty_models = {}

        with pytest.raises(KeyError, match="not found in trained_models"):
            selector.select(comparison_data, empty_models)

    def test_select_single_model(self, trained_models):
        """Test select works with only one model."""
        data = pd.DataFrame(
            {
                "Model": ["OnlyModel"],
                "PR-AUC": [0.82],
            }
        )
        single_model = {"OnlyModel": MagicMock()}
        selector = ModelSelector(metric="PR-AUC")
        result = selector.select(data, single_model)

        assert result["best_model_name"] == "OnlyModel"

    def test_select_reasoning_includes_description(
        self, comparison_data, trained_models
    ):
        """Test reasoning includes the selection rule description."""
        selector = ModelSelector(metric="PR-AUC")
        result = selector.select(comparison_data, trained_models)

        assert "PR-AUC" in result["reasoning"]
        assert "XGBoost" in result["reasoning"]

    def test_save_best_model_raises_before_select(self):
        """Test save_best_model raises if select() hasn't been called."""
        selector = ModelSelector()
        with pytest.raises(ValueError, match="No selection result"):
            selector.save_best_model()

    def test_save_best_model_creates_file(
        self, comparison_data, trained_models, tmp_path
    ):
        """Test save_best_model writes a pickle file."""
        save_path = str(tmp_path / "best_model.pkl")
        selector = ModelSelector(metric="PR-AUC")
        _result = selector.select(comparison_data, trained_models)

        with patch("src.fraudlens.models.model_selection.Path.mkdir"):
            actual_path = selector.save_best_model(path=save_path)

        assert actual_path == save_path
        assert (tmp_path / "best_model.pkl").exists()

    def test_get_selection_summary_before_select(self):
        """Test get_selection_summary returns 'not selected' message."""
        selector = ModelSelector()
        summary = selector.get_selection_summary()
        assert summary == "No model selected yet."

    def test_get_selection_summary_after_select(self, comparison_data, trained_models):
        """Test get_selection_summary returns formatted string after selection."""
        selector = ModelSelector(metric="PR-AUC")
        selector.select(comparison_data, trained_models)
        summary = selector.get_selection_summary()

        assert "XGBoost" in summary
        assert "0.8800" in summary or "0.88" in summary
        assert "Selection Metric" in summary

    def test_mlflow_tracking_when_not_available(self, comparison_data, trained_models):
        """Test selection works when MLflow is not available."""
        with patch("src.fraudlens.models.model_selection.MLFLOW_AVAILABLE", False):
            selector = ModelSelector(metric="PR-AUC")
            result = selector.select(comparison_data, trained_models)

            assert result["best_model_name"] == "XGBoost"
