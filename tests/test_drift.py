"""
Tests for the Drift Detection module.

Verifies KS-test correctly flags a shifted distribution,
correctly passes an unshifted one, and alert level thresholds behave.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fraudlens.monitoring.drift import DriftDetector, simulate_drift

# Fixtures


@pytest.fixture
def reference_data() -> pd.DataFrame:
    """Normal reference distribution."""
    np.random.seed(42)
    return pd.DataFrame(
        {
            "V1": np.random.randn(1000),
            "V14": np.random.randn(1000),
            "Amount": np.random.exponential(100, 1000),
        }
    )


@pytest.fixture
def drifted_data() -> pd.DataFrame:
    """Data with a shifted distribution."""
    np.random.seed(42)
    return pd.DataFrame(
        {
            "V1": np.random.randn(1000) + 2.0,  # Shifted mean
            "V14": np.random.randn(1000) * 3.0,  # Different variance
            "Amount": np.random.exponential(200, 1000),  # Different scale
        }
    )


@pytest.fixture
def detector(reference_data) -> DriftDetector:
    """Default detector with reference data."""
    return DriftDetector(
        reference_data=reference_data,
        feature_names=["V1", "V14", "Amount"],
        significance_level=0.05,
    )


# Tests: Initialization


class TestDetectorInit:
    """Tests for DriftDetector initialization."""

    def test_default_initialization(self, reference_data):
        """Test default constructor."""
        detector = DriftDetector(reference_data)
        assert detector.significance_level == 0.05
        assert len(detector.feature_names) > 0

    def test_custom_significance_level(self, reference_data):
        """Test custom significance level."""
        detector = DriftDetector(reference_data, significance_level=0.01)
        assert detector.significance_level == 0.01

    def test_computes_reference_stats(self, reference_data):
        """Test that reference stats are computed on init."""
        detector = DriftDetector(reference_data)
        assert "V1" in detector.ref_stats
        assert "V14" in detector.ref_stats
        assert "mean" in detector.ref_stats["V1"]
        assert "std" in detector.ref_stats["V1"]


# Tests: Drift Detection


class TestDetectDrift:
    """Tests for detect_drift method."""

    def test_no_drift_with_same_distribution(self, detector, reference_data):
        """Test that unshifted data does not trigger drift."""
        results = detector.detect_drift(reference_data)
        for _feat, result in results.items():
            assert result["alert"] == "OK"

    def test_drift_detected_with_shifted_data(self, detector, drifted_data):
        """Test that shifted data triggers drift alerts."""
        results = detector.detect_drift(drifted_data)
        drifted_features = [f for f, r in results.items() if r["alert"] != "OK"]
        assert len(drifted_features) > 0

    def test_critical_drift_high_shift(self, reference_data):
        """Test that a very large shift triggers CRITICAL."""
        huge_shift = reference_data.copy()
        huge_shift["V1"] = huge_shift["V1"] + 10.0  # Extreme shift
        detector = DriftDetector(
            reference_data, feature_names=["V1"], significance_level=0.05
        )
        results = detector.detect_drift(huge_shift)
        assert results["V1"]["alert"] == "CRITICAL"

    def test_ok_for_identical_data(self, reference_data):
        """Test that identical data returns OK for all features."""
        detector = DriftDetector(
            reference_data, feature_names=["V1"], significance_level=0.05
        )
        results = detector.detect_drift(reference_data[["V1"]])
        assert results["V1"]["alert"] == "OK"
        assert results["V1"]["p_value"] > 0.05


# Tests: Drift Score


class TestDriftScore:
    """Tests for get_overall_drift_score method."""

    def test_zero_score_no_drift(self, detector, reference_data):
        """Test score is 0 when no drift detected."""
        results = detector.detect_drift(reference_data)
        score = detector.get_overall_drift_score(results)
        assert score == 0.0

    def test_nonzero_score_with_drift(self, detector, drifted_data):
        """Test score is > 0 when drift detected."""
        results = detector.detect_drift(drifted_data)
        score = detector.get_overall_drift_score(results)
        assert score > 0.0

    def test_max_score_one(self, detector):
        """Test score can reach 1.0 with all features critical."""
        all_critical = {
            "V1": {"alert": "CRITICAL"},
            "V14": {"alert": "CRITICAL"},
            "Amount": {"alert": "CRITICAL"},
        }
        score = detector.get_overall_drift_score(all_critical)
        assert score == 1.0


# Tests: Report Generation


class TestReport:
    """Tests for generate_report method."""

    def test_report_contains_keywords(self, detector, drifted_data):
        """Test that report contains expected sections."""
        results = detector.detect_drift(drifted_data)
        report = detector.generate_report(results)
        assert "DATA DRIFT REPORT" in report
        assert "Overall Score" in report
        assert "RECOMMENDATION" in report

    def test_report_identifies_drifted_features(self, detector, drifted_data):
        """Test that report names drifted features."""
        results = detector.detect_drift(drifted_data)
        report = detector.generate_report(results)
        # At least some features should be mentioned in the report
        assert any(f in report for f in ["V1", "V14", "Amount"])


# Tests: Drift History


class TestDriftHistory:
    """Tests for drift history tracking."""

    def test_history_records_detection(self, detector, reference_data, drifted_data):
        """Test that drift history records each detection call."""
        detector.detect_drift(reference_data)
        detector.detect_drift(drifted_data)
        assert len(detector.drift_history) == 2

    def test_history_contains_metadata(self, detector, drifted_data):
        """Test that drift history entries contain expected fields."""
        detector.detect_drift(drifted_data)
        entry = detector.drift_history[0]
        assert "timestamp" in entry
        assert "n_samples" in entry
        assert "n_critical" in entry
        assert "n_warnings" in entry


# Tests: simulate_drift


class TestSimulateDrift:
    """Tests for simulate_drift helper function."""

    def test_simulate_drift_returns_dataframe(self, reference_data):
        """Test that simulate_drift returns a DataFrame."""
        result = simulate_drift(reference_data)
        assert isinstance(result, pd.DataFrame)
        assert result.shape == reference_data.shape

    def test_simulate_drift_shifts_features(self, reference_data):
        """Test that simulate_drift actually shifts the data."""
        original_mean = reference_data["V1"].mean()
        drifted = simulate_drift(reference_data, drift_magnitude=1.0)
        # Mean should have shifted
        assert abs(drifted["V1"].mean() - original_mean) > 0.1

    def test_simulate_drift_zero_magnitude(self, reference_data):
        """Test that zero magnitude returns nearly original data."""
        drifted = simulate_drift(reference_data, drift_magnitude=0.0)
        # Should be very close to original
        assert np.allclose(
            drifted["Amount"].mean(), reference_data["Amount"].mean(), rtol=0.1
        )


# Tests: Edge Cases


class TestEdgeCases:
    """Edge case tests for DriftDetector."""

    def test_empty_new_data(self, detector):
        """Test detection with empty DataFrame."""
        empty = pd.DataFrame(columns=["V1", "V14", "Amount"])
        results = detector.detect_drift(empty)
        # Should not crash, but results will be empty since no data
        assert isinstance(results, dict)

    def test_single_feature_detector(self, reference_data):
        """Test detector with single feature."""
        detector = DriftDetector(
            reference_data, feature_names=["V1"], significance_level=0.05
        )
        results = detector.detect_drift(reference_data[["V1"]])
        assert "V1" in results
        assert results["V1"]["alert"] == "OK"

    def test_missing_feature_in_new_data(self, detector):
        """Test detection when new data is missing a feature."""
        partial = pd.DataFrame({"V1": np.random.randn(100)})
        results = detector.detect_drift(partial)
        # V14 and Amount should be skipped, but V1 should be checked
        assert "V1" in results
        assert "V14" not in results
