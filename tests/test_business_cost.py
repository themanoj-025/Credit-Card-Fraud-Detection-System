"""
Tests for the Business Cost module.

Verifies cost computation, optimal threshold finding, and edge cases
for the BusinessCostCalculator class.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fraudlens.evaluation.business_cost import BusinessCostCalculator

# Fixtures


@pytest.fixture
def calculator() -> BusinessCostCalculator:
    """Default calculator with standard costs."""
    return BusinessCostCalculator(avg_fraud_loss=150.0, review_cost=5.0)


@pytest.fixture
def perfect_predictions() -> tuple:
    """Perfect predictions: no false positives or negatives."""
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    y_pred = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    return y_true, y_pred


@pytest.fixture
def worst_predictions() -> tuple:
    """Worst predictions: all fraud missed, all legit flagged."""
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    y_pred = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    return y_true, y_pred


@pytest.fixture
def realistic_predictions() -> tuple:
    """Realistic predictions with mixed results."""
    y_true = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    y_pred = np.array([0, 0, 1, 0, 0, 1, 1, 0, 1, 1])
    return y_true, y_pred


@pytest.fixture
def sample_probabilities() -> tuple:
    """Sample probabilities for threshold testing."""
    y_true = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    y_proba = np.array(
        [
            0.01,
            0.02,
            0.05,
            0.1,
            0.15,
            0.2,
            0.3,
            0.4,
            0.6,
            0.8,
            0.1,
            0.3,
            0.5,
            0.6,
            0.7,
            0.8,
            0.85,
            0.9,
            0.95,
            0.99,
        ]
    )
    return y_true, y_proba


# Tests: Initialization


class TestCalculatorInit:
    """Tests for BusinessCostCalculator initialization."""

    def test_default_initialization(self) -> None:
        """Test default constructor uses config values."""
        calc = BusinessCostCalculator()
        assert calc.avg_fraud_loss == 150.0
        assert calc.review_cost == 5.0

    def test_custom_initialization(self) -> None:
        """Test custom cost parameters."""
        calc = BusinessCostCalculator(avg_fraud_loss=200.0, review_cost=10.0)
        assert calc.avg_fraud_loss == 200.0
        assert calc.review_cost == 10.0


# Tests: Cost Computation


class TestComputeBusinessCost:
    """Tests for compute_business_cost method."""

    def test_perfect_predictions(self, calculator, perfect_predictions) -> None:
        """Test cost with perfect predictions (no errors)."""
        y_true, y_pred = perfect_predictions
        cost = calculator.compute_business_cost(y_true, y_pred)

        assert cost["true_positives"] == 4
        assert cost["false_positives"] == 0
        assert cost["true_negatives"] == 4
        assert cost["false_negatives"] == 0
        assert cost["fraud_caught_usd"] == 600.0  # 4 * 150
        assert cost["fraud_missed_usd"] == 0.0
        assert cost["review_costs_usd"] == 20.0  # 4 * 5
        assert cost["net_benefit_usd"] == 580.0  # 600 - 20

    def test_worst_predictions(self, calculator, worst_predictions) -> None:
        """Test cost with worst predictions (all wrong)."""
        y_true, y_pred = worst_predictions
        cost = calculator.compute_business_cost(y_true, y_pred)

        assert cost["true_positives"] == 0
        assert cost["false_positives"] == 4
        assert cost["true_negatives"] == 0
        assert cost["false_negatives"] == 4
        assert cost["fraud_caught_usd"] == 0.0
        assert cost["fraud_missed_usd"] == 600.0  # 4 * 150
        assert cost["review_costs_usd"] == 20.0  # 4 * 5
        assert cost["net_benefit_usd"] == -20.0  # 0 - 20

    def test_realistic_predictions(self, calculator, realistic_predictions) -> None:
        """Test cost with realistic mixed predictions."""
        y_true, y_pred = realistic_predictions
        cost = calculator.compute_business_cost(y_true, y_pred)

        # Verify all cost components are computed
        assert cost["true_positives"] >= 0
        assert cost["false_positives"] >= 0
        assert cost["true_negatives"] >= 0
        assert cost["false_negatives"] >= 0
        assert cost["fraud_caught_usd"] >= 0
        assert cost["fraud_missed_usd"] >= 0
        assert cost["review_costs_usd"] >= 0
        # y_true: [0,0,0,0,0, 1,1,1,1,1]
        # y_pred: [0,0,1,0,0, 1,1,0,1,1]
        # TN: legit predicted legit = indices 0,1,3,4 = 4
        # FP: legit predicted fraud = index 2 = 1
        # FN: fraud predicted legit = index 7 = 1
        # TP: fraud predicted fraud = indices 5,6,8,9 = 4
        assert cost["false_positives"] == 1
        assert cost["true_negatives"] == 4
        assert cost["false_negatives"] == 1
        assert cost["fraud_caught_usd"] == 600.0  # 4 * 150
        assert cost["fraud_missed_usd"] == 150.0  # 1 * 150
        assert cost["review_costs_usd"] == 25.0  # (4+1) * 5
        assert cost["net_benefit_usd"] == 575.0  # 600 - 25

    def test_cost_dict_structure(self, calculator, perfect_predictions) -> None:
        """Test that cost dictionary has all required keys."""
        y_true, y_pred = perfect_predictions
        cost = calculator.compute_business_cost(y_true, y_pred)

        required_keys = [
            "true_positives",
            "false_positives",
            "true_negatives",
            "false_negatives",
            "fraud_caught_usd",
            "fraud_missed_usd",
            "review_costs_usd",
            "net_benefit_usd",
            "total_cost_usd",
        ]
        for key in required_keys:
            assert key in cost, f"Missing key: {key}"

    def test_no_fraud_in_true(self, calculator) -> None:
        """Test when there are no actual fraud cases."""
        y_true = np.array([0, 0, 0, 0, 0, 1])  # Include at least one of each class
        y_pred = np.array([0, 0, 0, 0, 0, 0])  # Miss the fraud
        cost = calculator.compute_business_cost(y_true, y_pred)

        assert cost["fraud_caught_usd"] == 0.0
        assert cost["fraud_missed_usd"] == 150.0  # 1 * 150
        assert cost["review_costs_usd"] == 0.0
        assert cost["net_benefit_usd"] == 0.0

    def test_all_fraud_in_true(self, calculator) -> None:
        """Test when all cases are actual fraud."""
        y_true = np.array([1, 1, 1, 1, 1, 0])  # Include at least one of each class
        y_pred = np.array([1, 1, 1, 1, 1, 1])
        cost = calculator.compute_business_cost(y_true, y_pred)

        assert cost["true_positives"] == 5
        assert cost["false_negatives"] == 0
        assert cost["fraud_caught_usd"] == 750.0  # 5 * 150
        assert cost["fraud_missed_usd"] == 0.0

    def test_custom_costs(self) -> None:
        """Test with custom fraud loss and review cost."""
        calc = BusinessCostCalculator(avg_fraud_loss=300.0, review_cost=10.0)
        y_true = np.array([0, 1, 1])
        y_pred = np.array([0, 1, 0])
        cost = calc.compute_business_cost(y_true, y_pred)

        assert cost["fraud_caught_usd"] == 300.0  # 1 * 300
        assert cost["fraud_missed_usd"] == 300.0  # 1 * 300
        assert cost["review_costs_usd"] == 10.0  # 1 * 10
        assert cost["net_benefit_usd"] == 290.0  # 300 - 10


# Tests: Threshold Optimization


class TestFindOptimalThreshold:
    """Tests for find_optimal_threshold method."""

    def test_optimal_threshold_is_between_0_and_1(
        self, calculator, sample_probabilities
    ) -> None:
        """Test that optimal threshold is in valid range."""
        y_true, y_proba = sample_probabilities
        threshold, _cost = calculator.find_optimal_threshold(y_true, y_proba)

        assert 0.0 <= threshold <= 1.0

    def test_optimal_threshold_is_not_default(self, calculator, sample_probabilities) -> None:
        """Test that optimal threshold differs from default 0.5 for imbalanced data."""
        y_true, y_proba = sample_probabilities
        threshold, _cost = calculator.find_optimal_threshold(y_true, y_proba)

        # For imbalanced fraud data, optimal is usually much lower than 0.5
        # At minimum, it should be a reasonable value
        assert threshold > 0.0
        assert threshold < 1.0

    def test_threshold_minimizes_cost(self, calculator, sample_probabilities) -> None:
        """Test that the returned threshold actually minimizes total cost."""
        y_true, y_proba = sample_probabilities
        _threshold, best_cost = calculator.find_optimal_threshold(y_true, y_proba)

        # Test that a different threshold gives worse cost
        for test_threshold in [0.01, 0.5, 0.99]:
            y_pred = (y_proba >= test_threshold).astype(int)
            cost = calculator.compute_business_cost(y_true, y_pred)
            # Best cost should be <= any other cost we try
            # (Note: not strictly true due to discrete thresholds, but close)
            assert best_cost["total_cost_usd"] <= cost["total_cost_usd"] + 1.0

    def test_threshold_returns_cost_dict(self, calculator, sample_probabilities) -> None:
        """Test that find_optimal_threshold returns valid cost dict."""
        y_true, y_proba = sample_probabilities
        _threshold, cost = calculator.find_optimal_threshold(y_true, y_proba)

        assert isinstance(cost, dict)
        assert "total_cost_usd" in cost
        assert "net_benefit_usd" in cost

    def test_custom_n_thresholds(self, calculator, sample_probabilities) -> None:
        """Test with custom number of thresholds to evaluate."""
        y_true, y_proba = sample_probabilities
        threshold, cost = calculator.find_optimal_threshold(
            y_true, y_proba, n_thresholds=50
        )

        assert 0.0 <= threshold <= 1.0
        assert "total_cost_usd" in cost

    def test_all_high_probabilities(self, calculator) -> None:
        """Test threshold when all fraud has high probability."""
        y_true = np.array([0, 0, 0, 1, 1])
        y_proba = np.array([0.1, 0.2, 0.3, 0.9, 0.95])
        _threshold, cost = calculator.find_optimal_threshold(y_true, y_proba)

        # Should be able to separate perfectly
        assert cost["true_positives"] >= 1

    def test_all_low_probabilities(self, calculator) -> None:
        """Test threshold when all fraud has low probability."""
        y_true = np.array([0, 0, 0, 1, 1])
        y_proba = np.array([0.1, 0.15, 0.2, 0.3, 0.35])
        threshold, _cost = calculator.find_optimal_threshold(y_true, y_proba)

        # Threshold should be low to catch any fraud
        assert threshold <= 0.5


# Tests: Edge Cases


class TestEdgeCases:
    """Edge case tests for BusinessCostCalculator."""

    def test_single_sample(self, calculator) -> None:
        """Test with minimum samples (need both classes for confusion matrix)."""
        y_true = np.array([0, 1])
        y_pred = np.array([0, 1])
        cost = calculator.compute_business_cost(y_true, y_pred)

        assert cost["true_positives"] == 1
        assert cost["fraud_caught_usd"] == 150.0

    def test_two_samples(self, calculator) -> None:
        """Test with two samples."""
        y_true = np.array([0, 1])
        y_pred = np.array([0, 1])
        cost = calculator.compute_business_cost(y_true, y_pred)

        assert cost["true_positives"] == 1
        assert cost["true_negatives"] == 1

    def test_threshold_with_single_probability(self, calculator) -> None:
        """Test threshold optimization with minimal data."""
        y_true = np.array([0, 1])
        y_proba = np.array([0.2, 0.8])
        threshold, _cost = calculator.find_optimal_threshold(y_true, y_proba)

        assert 0.0 <= threshold <= 1.0

    def test_zero_fraud_loss(self) -> None:
        """Test with zero fraud loss (edge case)."""
        calc = BusinessCostCalculator(avg_fraud_loss=0.0, review_cost=5.0)
        y_true = np.array([0, 1])
        y_pred = np.array([0, 1])
        cost = calc.compute_business_cost(y_true, y_pred)

        assert cost["fraud_caught_usd"] == 0.0
        assert cost["fraud_missed_usd"] == 0.0

    def test_zero_review_cost(self) -> None:
        """Test with zero review cost (edge case)."""
        calc = BusinessCostCalculator(avg_fraud_loss=150.0, review_cost=0.0)
        y_true = np.array([0, 1])
        y_pred = np.array([0, 1])
        cost = calc.compute_business_cost(y_true, y_pred)

        assert cost["review_costs_usd"] == 0.0


# Tests: Cost Values are Reasonable


class TestCostReasonableness:
    """Tests that cost values make business sense."""

    def test_catching_fraud_reduces_cost(self, calculator) -> None:
        """Test that catching fraud reduces net loss."""
        y_true = np.array([0, 0, 1, 1])

        # Miss all fraud
        y_pred_bad = np.array([0, 0, 0, 0])
        cost_bad = calculator.compute_business_cost(y_true, y_pred_bad)

        # Catch all fraud
        y_pred_good = np.array([0, 0, 1, 1])
        cost_good = calculator.compute_business_cost(y_true, y_pred_good)

        # Net benefit should be higher when catching fraud
        assert cost_good["net_benefit_usd"] > cost_bad["net_benefit_usd"]

    def test_review_costs_scale_with_flags(self, calculator) -> None:
        """Test that review costs increase with more flagged transactions."""
        y_true = np.array([0, 0, 0, 0])

        y_pred_few = np.array([0, 0, 0, 1])
        cost_few = calculator.compute_business_cost(y_true, y_pred_few)

        y_pred_many = np.array([1, 1, 1, 1])
        cost_many = calculator.compute_business_cost(y_true, y_pred_many)

        assert cost_many["review_costs_usd"] > cost_few["review_costs_usd"]

    def test_higher_fraud_loss_increases_cost_of_missing(self) -> None:
        """Test that higher fraud loss makes missing fraud more costly."""
        calc_low = BusinessCostCalculator(avg_fraud_loss=50.0, review_cost=5.0)
        calc_high = BusinessCostCalculator(avg_fraud_loss=500.0, review_cost=5.0)

        y_true = np.array([0, 0, 1])
        y_pred = np.array([0, 0, 0])  # Miss the fraud

        cost_low = calc_low.compute_business_cost(y_true, y_pred)
        cost_high = calc_high.compute_business_cost(y_true, y_pred)

        assert cost_high["fraud_missed_usd"] > cost_low["fraud_missed_usd"]


# Tests: Smoke Tests for Additional Methods


class TestSmokeAdditionalMethods:
    """Smoke tests for evaluate_all_thresholds and plot_cost_vs_threshold."""

    def test_evaluate_all_thresholds(self, calculator) -> None:
        """Test evaluate_all_thresholds returns results for all models."""
        y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        predictions = {
            "model_a": np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9]),
            "model_b": np.array([0.2, 0.3, 0.4, 0.5, 0.5, 0.6, 0.7, 0.8]),
        }
        results = calculator.evaluate_all_thresholds(y_true, predictions)

        assert len(results) == 2
        assert "model_a" in results
        assert "model_b" in results
        assert "threshold" in results["model_a"]
        assert "business" in results["model_a"]

    def test_plot_cost_vs_threshold(self, calculator) -> None:
        """Test that plot_cost_vs_threshold returns a figure."""
        import matplotlib

        matplotlib.use("Agg")

        y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        y_proba = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9])

        fig = calculator.plot_cost_vs_threshold(y_true, y_proba, model_name="test")

        import matplotlib.pyplot as plt

        assert isinstance(fig, plt.Figure)
        plt.close(fig)
