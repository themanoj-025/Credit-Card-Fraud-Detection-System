"""
FraudLens — Evaluation Metrics Tests

Tests for FraudEvaluator and print_evaluation_summary in evaluation/metrics.py.
Uses synthetic data for reproducible metrics calculations.
"""

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for testing

import numpy as np
import pytest

from src.fraudlens.evaluation.metrics import FraudEvaluator, print_evaluation_summary


@pytest.fixture
def synthetic_data():
    """Create synthetic labels and predictions for deterministic tests."""
    np.random.seed(42)
    n = 500
    y_true = np.random.choice([0, 1], size=n, p=[0.97, 0.03])
    # Good predictions: high for fraud, low for legitimate
    y_proba = np.where(
        y_true == 1,
        np.random.uniform(0.7, 1.0, size=n),
        np.random.uniform(0.0, 0.3, size=n),
    )
    return y_true, y_proba


@pytest.fixture
def perfect_data():
    """Perfect predictions (all probabilities match labels exactly)."""
    np.random.seed(42)
    n = 200
    y_true = np.random.choice([0, 1], size=n, p=[0.95, 0.05])
    # Overconfident correct predictions
    y_proba = y_true.astype(float).copy()
    # Add slight noise to test precision/recall boundaries
    noise = np.random.uniform(-0.01, 0.01, size=n)
    y_proba = np.clip(y_proba + noise, 0, 1)
    return y_true, y_proba


@pytest.fixture
def multiple_models_data():
    """Generate data for compare_models tests with multiple models."""
    np.random.seed(42)
    n = 500
    y_true = np.random.choice([0, 1], size=n, p=[0.97, 0.03])
    predictions = {
        "Model_A": np.where(
            y_true == 1,
            np.random.uniform(0.7, 1.0, n),
            np.random.uniform(0.0, 0.3, n),
        ),
        "Model_B": np.random.uniform(0.4, 0.6, n),  # Random guessing
    }
    thresholds = {"Model_A": 0.5, "Model_B": 0.5}
    business_costs = {
        "Model_A": {
            "fraud_caught_usd": 10000,
            "fraud_missed_usd": 500,
            "review_costs_usd": 200,
            "net_benefit_usd": 9300,
        },
        "Model_B": {
            "fraud_caught_usd": 3000,
            "fraud_missed_usd": 1000,
            "review_costs_usd": 500,
            "net_benefit_usd": 1500,
        },
    }
    return y_true, predictions, thresholds, business_costs


class TestFraudEvaluator:
    """Tests for FraudEvaluator."""

    def test_init_defaults(self):
        """Test default initialization with config values."""
        evaluator = FraudEvaluator()
        assert evaluator.avg_fraud_loss == 150.0
        assert evaluator.review_cost == 5.0

    def test_init_custom(self):
        """Test custom initialization values."""
        evaluator = FraudEvaluator(avg_fraud_loss=200.0, review_cost=10.0)
        assert evaluator.avg_fraud_loss == 200.0
        assert evaluator.review_cost == 10.0

    def test_compute_metrics_basic(self, synthetic_data):
        """Test compute_metrics returns all expected fields."""
        y_true, y_proba = synthetic_data
        evaluator = FraudEvaluator()

        metrics = evaluator.compute_metrics(y_true, y_proba, threshold=0.5)

        assert "pr_auc" in metrics
        assert "roc_auc" in metrics
        assert "f1" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "threshold" in metrics
        assert "confusion_matrix" in metrics
        assert metrics["threshold"] == 0.5

    def test_compute_metrics_types(self, synthetic_data):
        """Test all metrics are within valid ranges."""
        y_true, y_proba = synthetic_data
        evaluator = FraudEvaluator()

        metrics = evaluator.compute_metrics(y_true, y_proba)

        for key in ["pr_auc", "roc_auc", "f1", "precision", "recall"]:
            assert 0.0 <= metrics[key] <= 1.0, f"{key} out of range"

    def test_compute_metrics_threshold_at_zero(self, synthetic_data):
        """Test with threshold=0 (all predicted positive)."""
        y_true, y_proba = synthetic_data
        evaluator = FraudEvaluator()

        metrics = evaluator.compute_metrics(y_true, y_proba, threshold=0.0)

        assert metrics["recall"] == 1.0  # All positives caught

    def test_compute_metrics_threshold_at_one(self, synthetic_data):
        """Test with threshold=1 (all predicted negative)."""
        y_true, y_proba = synthetic_data
        evaluator = FraudEvaluator()

        metrics = evaluator.compute_metrics(y_true, y_proba, threshold=1.0)

        assert metrics["recall"] == 0.0  # No positives caught

    def test_compute_metrics_empty_positive(self):
        """Test with no positive samples."""
        y_true = np.zeros(100)
        y_proba = np.random.uniform(0, 1, 100)
        evaluator = FraudEvaluator()

        metrics = evaluator.compute_metrics(y_true, y_proba)
        assert metrics["pr_auc"] >= 0.0

    def test_compute_metrics_confusion_matrix_shape(self, synthetic_data):
        """Test confusion matrix is 2x2."""
        y_true, y_proba = synthetic_data
        evaluator = FraudEvaluator()

        metrics = evaluator.compute_metrics(y_true, y_proba)
        cm = np.array(metrics["confusion_matrix"])
        assert cm.shape == (2, 2)

    def test_evaluate_model_with_business_cost(self, synthetic_data):
        """Test evaluate_model includes business cost data."""
        y_true, y_proba = synthetic_data
        evaluator = FraudEvaluator()

        biz_cost = {
            "fraud_caught_usd": 5000,
            "fraud_missed_usd": 200,
            "review_costs_usd": 100,
            "net_benefit_usd": 4700,
        }
        result = evaluator.evaluate_model(
            y_true,
            y_proba,
            threshold=0.5,
            model_name="TestModel",
            business_cost=biz_cost,
        )

        assert result["model_name"] == "TestModel"
        assert result["business"]["net_benefit_usd"] == 4700

    def test_evaluate_model_without_business_cost(self, synthetic_data):
        """Test evaluate_model works without business cost data."""
        y_true, y_proba = synthetic_data
        evaluator = FraudEvaluator()

        result = evaluator.evaluate_model(y_true, y_proba, model_name="TestModel")

        assert result["business"] == {}

    def test_compare_models_sorting(self, multiple_models_data):
        """Test compare_models sorts by PR-AUC descending."""
        y_true, predictions, thresholds, business_costs = multiple_models_data
        evaluator = FraudEvaluator()

        comparison = evaluator.compare_models(
            y_true, predictions, thresholds, business_costs
        )

        assert comparison.iloc[0]["PR-AUC"] >= comparison.iloc[1]["PR-AUC"]
        assert comparison.iloc[0]["Model"] == "Model_A"

    def test_compare_models_columns(self, multiple_models_data):
        """Test compare_models has expected columns."""
        y_true, predictions, thresholds, business_costs = multiple_models_data
        evaluator = FraudEvaluator()

        comparison = evaluator.compare_models(
            y_true, predictions, thresholds, business_costs
        )

        expected_columns = [
            "Model",
            "Threshold",
            "PR-AUC",
            "ROC-AUC",
            "F1",
            "Precision",
            "Recall",
            "Net Benefit ($)",
            "Fraud Caught ($)",
            "Missed Fraud ($)",
        ]
        for col in expected_columns:
            assert col in comparison.columns

    def test_compare_models_default_threshold(self, multiple_models_data):
        """Test compare_models uses default threshold when none provided."""
        y_true, predictions, _, _ = multiple_models_data
        evaluator = FraudEvaluator()

        # Call without thresholds dict
        comparison = evaluator.compare_models(y_true, predictions)

        assert len(comparison) == 2
        assert comparison.iloc[0]["Threshold"] == 0.5

    def test_plot_precision_recall_curve(self, multiple_models_data):
        """Test plot_precision_recall_curve creates figure."""
        y_true, predictions, _, _ = multiple_models_data
        evaluator = FraudEvaluator()

        fig = evaluator.plot_precision_recall_curve(y_true, predictions)

        assert fig is not None

    def test_plot_precision_recall_curve_saves(self, multiple_models_data, tmp_path):
        """Test plot_precision_recall_curve saves to file."""
        y_true, predictions, _, _ = multiple_models_data
        evaluator = FraudEvaluator()

        save_path = str(tmp_path / "pr_curve.png")
        _fig = evaluator.plot_precision_recall_curve(y_true, predictions, save_path)

        assert (tmp_path / "pr_curve.png").exists()

    def test_plot_confusion_matrices(self, multiple_models_data):
        """Test plot_confusion_matrices creates figure."""
        y_true, predictions, _, _ = multiple_models_data
        evaluator = FraudEvaluator()

        fig = evaluator.plot_confusion_matrices(y_true, predictions)

        assert fig is not None

    def test_plot_confusion_matrices_single_model(self):
        """Test plot_confusion_matrices with a single model."""
        np.random.seed(42)
        y_true = np.random.choice([0, 1], size=100, p=[0.9, 0.1])
        y_proba = np.random.uniform(0, 1, 100)
        evaluator = FraudEvaluator()

        fig = evaluator.plot_confusion_matrices(
            y_true, {"SingleModel": y_proba}, top_n=1
        )

        assert fig is not None


class TestPrintEvaluationSummary:
    """Tests for print_evaluation_summary utility function."""

    def test_print_summary_format(self):
        """Test print_evaluation_summary returns formatted string."""
        results = {
            "model_name": "XGBoost",
            "threshold": 0.0298,
            "pr_auc": 0.8810,
            "roc_auc": 0.9724,
            "f1": 0.7068,
            "precision": 0.5828,
            "recall": 0.8980,
            "business": {
                "fraud_caught_usd": 13200.0,
                "fraud_missed_usd": 1500.0,
                "review_costs_usd": 755.0,
                "net_benefit_usd": 12445.0,
            },
        }

        output = print_evaluation_summary(results)

        assert "XGBoost" in output
        assert "0.8810" in output
        assert "PR-AUC" in output
        assert "Net Benefit" in output
        assert "$ 12,445.00" in output
        assert "$ 13,200.00" in output

    def test_print_summary_has_section_breaks(self):
        """Test print_evaluation_summary has proper section formatting."""
        results = {
            "model_name": "Test",
            "threshold": 0.5,
            "pr_auc": 0.75,
            "roc_auc": 0.85,
            "f1": 0.65,
            "precision": 0.60,
            "recall": 0.70,
            "business": {
                "fraud_caught_usd": 1000.0,
                "fraud_missed_usd": 500.0,
                "review_costs_usd": 100.0,
                "net_benefit_usd": 400.0,
            },
        }

        output = print_evaluation_summary(results)

        assert output.startswith("\n")
        assert "=" * 60 in output
        assert "BUSINESS IMPACT" in output
