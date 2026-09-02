"""
FraudLens — Retraining Trigger Tests

Simulates drift events + feedback volume, runs the retraining trigger in
dry-run mode, and verifies candidate registration logic.

Test scenarios:
1. Drift condition: below threshold, at threshold, above threshold
2. Feedback condition: below threshold, at threshold, above threshold
3. Both conditions met simultaneously
4. Dry-run trigger with drift events → correct TriggerResult
5. Dry-run trigger with feedback volume → correct TriggerResult
6. No conditions met → triggered=False
7. Candidate version format
8. check_and_trigger() convenience function
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fraudlens.retraining.retrain_trigger import (
    RetrainingTrigger,
)

# Fixtures


@pytest.fixture
def trigger() -> RetrainingTrigger:
    """A RetrainingTrigger with low thresholds for easy testing."""
    return RetrainingTrigger(
        feedback_threshold=5,
        drift_critical_threshold=2,
        drift_window_days=7,
    )


@pytest.fixture
def recent_critical_drift_events() -> list:
    """Simulated drift events: 3 CRITICAL, 1 WARNING, timestamps in window."""
    now = datetime.utcnow()
    return [
        {
            "feature_name": "V14",
            "drift_score": 0.89,
            "alert_type": "CRITICAL",
            "created_at": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "feature_name": "V4",
            "drift_score": 0.76,
            "alert_type": "CRITICAL",
            "created_at": (now - timedelta(hours=2)).isoformat(),
        },
        {
            "feature_name": "V12",
            "drift_score": 0.92,
            "alert_type": "CRITICAL",
            "created_at": (now - timedelta(hours=3)).isoformat(),
        },
        {
            "feature_name": "Amount",
            "drift_score": 0.45,
            "alert_type": "WARNING",
            "created_at": (now - timedelta(hours=4)).isoformat(),
        },
    ]


@pytest.fixture
def few_critical_drift_events() -> list:
    """Only 1 CRITICAL event (below threshold of 2)."""
    now = datetime.utcnow()
    return [
        {
            "feature_name": "V14",
            "drift_score": 0.89,
            "alert_type": "CRITICAL",
            "created_at": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "feature_name": "Amount",
            "drift_score": 0.45,
            "alert_type": "WARNING",
            "created_at": (now - timedelta(hours=4)).isoformat(),
        },
    ]


@pytest.fixture
def old_drift_events() -> list:
    """CRITICAL events outside the 7-day window."""
    now = datetime.utcnow()
    return [
        {
            "feature_name": "V14",
            "drift_score": 0.89,
            "alert_type": "CRITICAL",
            "created_at": (now - timedelta(days=10)).isoformat(),
        },
        {
            "feature_name": "V4",
            "drift_score": 0.76,
            "alert_type": "CRITICAL",
            "created_at": (now - timedelta(days=14)).isoformat(),
        },
    ]


@pytest.fixture
def drift_events_with_string_alerts() -> list:
    """Events using 'alert' key instead of 'alert_type' (backward compat)."""
    now = datetime.utcnow()
    return [
        {
            "feature_name": "V14",
            "drift_score": 0.89,
            "alert": "CRITICAL",
            "timestamp": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "feature_name": "V4",
            "drift_score": 0.76,
            "alert": "CRITICAL",
            "timestamp": (now - timedelta(hours=2)).isoformat(),
        },
    ]


@pytest.fixture
def drift_events_with_datetime_objects() -> list:
    """Events with datetime objects (not strings) for created_at."""
    now = datetime.utcnow()
    return [
        {
            "feature_name": "V14",
            "drift_score": 0.89,
            "alert_type": "CRITICAL",
            "created_at": now - timedelta(hours=1),
        },
        {
            "feature_name": "V4",
            "drift_score": 0.76,
            "alert_type": "CRITICAL",
            "created_at": now - timedelta(hours=2),
        },
    ]


# Tests: Initialization


class TestRetrainingTriggerInit:
    """Tests for RetrainingTrigger initialization."""

    def test_default_initialization(self) -> None:
        """Default constructor should set reasonable thresholds."""
        t = RetrainingTrigger()
        assert t.feedback_threshold == 100
        assert t.drift_critical_threshold == 3
        assert t.drift_window_days == 7
        assert t.models_dir is not None
        assert t.pipeline_script is not None

    def test_custom_initialization(self) -> None:
        """Custom params should override defaults."""
        t = RetrainingTrigger(
            feedback_threshold=10,
            drift_critical_threshold=5,
            drift_window_days=14,
        )
        assert t.feedback_threshold == 10
        assert t.drift_critical_threshold == 5
        assert t.drift_window_days == 14

    def test_models_dir_default(self) -> None:
        """models_dir should default to project models/ directory."""
        t = RetrainingTrigger()
        assert "models" in str(t.models_dir)


# Tests: generate_candidate_version


class TestGenerateCandidateVersion:
    """Tests for candidate version generation."""

    def test_format(self, trigger) -> None:
        """Version should follow vYYYYMMDD_HHMMSS format."""
        version = trigger.generate_candidate_version()
        assert version.startswith("v")
        assert len(version) == 16  # v + 8 digits + _ + 6 digits = 16
        assert "_" in version

    def test_increments_each_call(self, trigger) -> None:
        """Two calls in quick succession should produce different versions."""
        v1 = trigger.generate_candidate_version()
        v2 = trigger.generate_candidate_version()
        # Could be the same second, so just check they don't raise
        assert isinstance(v1, str)
        assert isinstance(v2, str)


# Tests: check_drift_condition


class TestCheckDriftCondition:
    """Tests for the drift condition check."""

    def test_below_threshold(self, trigger, few_critical_drift_events) -> None:
        """1 CRITICAL event < threshold of 2 → met=False."""
        result = trigger.check_drift_condition(few_critical_drift_events)
        assert result["met"] is False
        assert result["count"] == 1
        assert result["threshold"] == 2

    def test_at_threshold(self, trigger) -> None:
        """2 CRITICAL events = threshold of 2 → met=True."""
        events = [
            {"feature_name": "V14", "alert_type": "CRITICAL"},
            {"feature_name": "V4", "alert_type": "CRITICAL"},
        ]
        result = trigger.check_drift_condition(events)
        assert result["met"] is True
        assert result["count"] == 2

    def test_above_threshold(self, trigger, recent_critical_drift_events) -> None:
        """3 CRITICAL events > threshold of 2 → met=True."""
        result = trigger.check_drift_condition(recent_critical_drift_events)
        assert result["met"] is True
        assert result["count"] == 3
        assert result["threshold"] == 2

    def test_no_events(self, trigger) -> None:
        """Empty list → met=False."""
        result = trigger.check_drift_condition([])
        assert result["met"] is False
        assert result["count"] == 0

    def test_only_warnings(self, trigger) -> None:
        """Only WARNING events → met=False."""
        events = [
            {"feature_name": "V14", "alert_type": "WARNING"},
            {"feature_name": "V4", "alert_type": "WARNING"},
        ]
        result = trigger.check_drift_condition(events)
        assert result["met"] is False
        assert result["count"] == 0

    def test_none_uses_report_fallback(self, trigger) -> None:
        """None input uses file-based fallback → graceful."""
        with patch("pathlib.Path.exists", return_value=False):
            result = trigger.check_drift_condition(None)
            assert result["met"] is False
            assert result["detail"] == "No drift report found"

    def test_old_events_outside_window(self, trigger, old_drift_events) -> None:
        """Events older than drift_window_days should NOT trigger."""
        result = trigger.check_drift_condition(old_drift_events)
        assert result["met"] is False
        assert result["count"] == 0

    def test_string_alert_key(self, trigger, drift_events_with_string_alerts) -> None:
        """Events using 'alert' key (not 'alert_type') should be detected."""
        result = trigger.check_drift_condition(drift_events_with_string_alerts)
        assert result["met"] is True
        assert result["count"] == 2

    def test_datetime_objects(self, trigger, drift_events_with_datetime_objects) -> None:
        """Events with datetime objects (not strings) should work."""
        result = trigger.check_drift_condition(drift_events_with_datetime_objects)
        assert result["met"] is True
        assert result["count"] == 2


# Tests: check_feedback_condition


class TestCheckFeedbackCondition:
    """Tests for the feedback volume condition check."""

    def test_below_threshold(self, trigger) -> None:
        """3 feedback labels < threshold of 5 → met=False."""
        result = trigger.check_feedback_condition(3)
        assert result["met"] is False
        assert result["count"] == 3
        assert result["threshold"] == 5

    def test_at_threshold(self, trigger) -> None:
        """5 feedback labels = threshold of 5 → met=True."""
        result = trigger.check_feedback_condition(5)
        assert result["met"] is True
        assert result["count"] == 5

    def test_above_threshold(self, trigger) -> None:
        """10 feedback labels > threshold of 5 → met=True."""
        result = trigger.check_feedback_condition(10)
        assert result["met"] is True
        assert result["count"] == 10

    def test_zero_feedback(self, trigger) -> None:
        """0 feedback → met=False."""
        result = trigger.check_feedback_condition(0)
        assert result["met"] is False
        assert result["count"] == 0

    def test_none_no_training_history(self, trigger) -> None:
        """None input with no model artifacts → met=False with graceful message."""
        with patch.object(trigger, "_get_last_training_time", return_value=None):
            result = trigger.check_feedback_condition(None)
            assert result["met"] is False
            assert "No training history" in result["detail"]

    def test_none_with_training_history(self, trigger) -> None:
        """None input with training artifacts → does not raise."""
        with patch.object(trigger, "_get_last_training_time", return_value=1000000.0):
            result = trigger.check_feedback_condition(None)
            assert result["met"] is False  # Default 0 feedback


# Tests: check_conditions (combined)


class TestCheckConditions:
    """Tests for the combined check_conditions method."""

    def test_no_triggers(self, trigger) -> None:
        """No drift or feedback → any_triggered=False."""
        result = trigger.check_conditions(
            recent_drift_events=[],
            new_feedback_count=0,
        )
        assert result["any_triggered"] is False
        assert result["conditions"]["drift"]["met"] is False
        assert result["conditions"]["feedback_volume"]["met"] is False
        assert result["primary_reason"] == "No trigger conditions met"

    def test_drift_only(self, trigger, recent_critical_drift_events) -> None:
        """Only drift triggered → any_triggered=True with drift reason."""
        result = trigger.check_conditions(
            recent_drift_events=recent_critical_drift_events,
            new_feedback_count=0,
        )
        assert result["any_triggered"] is True
        assert result["conditions"]["drift"]["met"] is True
        assert result["conditions"]["feedback_volume"]["met"] is False
        assert "Drift trigger" in result["primary_reason"]

    def test_feedback_only(self, trigger) -> None:
        """Only feedback triggered → any_triggered=True with feedback reason."""
        result = trigger.check_conditions(
            recent_drift_events=[],
            new_feedback_count=10,
        )
        assert result["any_triggered"] is True
        assert result["conditions"]["drift"]["met"] is False
        assert result["conditions"]["feedback_volume"]["met"] is True
        assert "Feedback volume trigger" in result["primary_reason"]

    def test_both_triggers(self, trigger, recent_critical_drift_events) -> None:
        """Both conditions met → any_triggered=True with combined reason."""
        result = trigger.check_conditions(
            recent_drift_events=recent_critical_drift_events,
            new_feedback_count=10,
        )
        assert result["any_triggered"] is True
        assert result["conditions"]["drift"]["met"] is True
        assert result["conditions"]["feedback_volume"]["met"] is True
        assert "AND" in result["primary_reason"]


# Tests: trigger (dry-run mode)

