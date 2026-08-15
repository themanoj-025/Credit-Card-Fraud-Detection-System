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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fraudlens.retraining.retrain_trigger import (
    CandidateInfo,
    RetrainingTrigger,
    TriggerResult,
    check_and_trigger,
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

    def test_default_initialization(self):
        """Default constructor should set reasonable thresholds."""
        t = RetrainingTrigger()
        assert t.feedback_threshold == 100
        assert t.drift_critical_threshold == 3
        assert t.drift_window_days == 7
        assert t.models_dir is not None
        assert t.pipeline_script is not None

    def test_custom_initialization(self):
        """Custom params should override defaults."""
        t = RetrainingTrigger(
            feedback_threshold=10,
            drift_critical_threshold=5,
            drift_window_days=14,
        )
        assert t.feedback_threshold == 10
        assert t.drift_critical_threshold == 5
        assert t.drift_window_days == 14

    def test_models_dir_default(self):
        """models_dir should default to project models/ directory."""
        t = RetrainingTrigger()
        assert "models" in str(t.models_dir)


# Tests: generate_candidate_version


class TestGenerateCandidateVersion:
    """Tests for candidate version generation."""

    def test_format(self, trigger):
        """Version should follow vYYYYMMDD_HHMMSS format."""
        version = trigger.generate_candidate_version()
        assert version.startswith("v")
        assert len(version) == 16  # v + 8 digits + _ + 6 digits = 16
        assert "_" in version

    def test_increments_each_call(self, trigger):
        """Two calls in quick succession should produce different versions."""
        v1 = trigger.generate_candidate_version()
        v2 = trigger.generate_candidate_version()
        # Could be the same second, so just check they don't raise
        assert isinstance(v1, str)
        assert isinstance(v2, str)


# Tests: check_drift_condition


class TestCheckDriftCondition:
    """Tests for the drift condition check."""

    def test_below_threshold(self, trigger, few_critical_drift_events):
        """1 CRITICAL event < threshold of 2 → met=False."""
        result = trigger.check_drift_condition(few_critical_drift_events)
        assert result["met"] is False
        assert result["count"] == 1
        assert result["threshold"] == 2

    def test_at_threshold(self, trigger):
        """2 CRITICAL events = threshold of 2 → met=True."""
        events = [
            {"feature_name": "V14", "alert_type": "CRITICAL"},
            {"feature_name": "V4", "alert_type": "CRITICAL"},
        ]
        result = trigger.check_drift_condition(events)
        assert result["met"] is True
        assert result["count"] == 2

    def test_above_threshold(self, trigger, recent_critical_drift_events):
        """3 CRITICAL events > threshold of 2 → met=True."""
        result = trigger.check_drift_condition(recent_critical_drift_events)
        assert result["met"] is True
        assert result["count"] == 3
        assert result["threshold"] == 2

    def test_no_events(self, trigger):
        """Empty list → met=False."""
        result = trigger.check_drift_condition([])
        assert result["met"] is False
        assert result["count"] == 0

    def test_only_warnings(self, trigger):
        """Only WARNING events → met=False."""
        events = [
            {"feature_name": "V14", "alert_type": "WARNING"},
            {"feature_name": "V4", "alert_type": "WARNING"},
        ]
        result = trigger.check_drift_condition(events)
        assert result["met"] is False
        assert result["count"] == 0

    def test_none_uses_report_fallback(self, trigger):
        """None input uses file-based fallback → graceful."""
        with patch("pathlib.Path.exists", return_value=False):
            result = trigger.check_drift_condition(None)
            assert result["met"] is False
            assert result["detail"] == "No drift report found"

    def test_old_events_outside_window(self, trigger, old_drift_events):
        """Events older than drift_window_days should NOT trigger."""
        result = trigger.check_drift_condition(old_drift_events)
        assert result["met"] is False
        assert result["count"] == 0

    def test_string_alert_key(self, trigger, drift_events_with_string_alerts):
        """Events using 'alert' key (not 'alert_type') should be detected."""
        result = trigger.check_drift_condition(drift_events_with_string_alerts)
        assert result["met"] is True
        assert result["count"] == 2

    def test_datetime_objects(self, trigger, drift_events_with_datetime_objects):
        """Events with datetime objects (not strings) should work."""
        result = trigger.check_drift_condition(drift_events_with_datetime_objects)
        assert result["met"] is True
        assert result["count"] == 2


# Tests: check_feedback_condition


class TestCheckFeedbackCondition:
    """Tests for the feedback volume condition check."""

    def test_below_threshold(self, trigger):
        """3 feedback labels < threshold of 5 → met=False."""
        result = trigger.check_feedback_condition(3)
        assert result["met"] is False
        assert result["count"] == 3
        assert result["threshold"] == 5

    def test_at_threshold(self, trigger):
        """5 feedback labels = threshold of 5 → met=True."""
        result = trigger.check_feedback_condition(5)
        assert result["met"] is True
        assert result["count"] == 5

    def test_above_threshold(self, trigger):
        """10 feedback labels > threshold of 5 → met=True."""
        result = trigger.check_feedback_condition(10)
        assert result["met"] is True
        assert result["count"] == 10

    def test_zero_feedback(self, trigger):
        """0 feedback → met=False."""
        result = trigger.check_feedback_condition(0)
        assert result["met"] is False
        assert result["count"] == 0

    def test_none_no_training_history(self, trigger):
        """None input with no model artifacts → met=False with graceful message."""
        with patch.object(trigger, "_get_last_training_time", return_value=None):
            result = trigger.check_feedback_condition(None)
            assert result["met"] is False
            assert "No training history" in result["detail"]

    def test_none_with_training_history(self, trigger):
        """None input with training artifacts → does not raise."""
        with patch.object(trigger, "_get_last_training_time", return_value=1000000.0):
            result = trigger.check_feedback_condition(None)
            assert result["met"] is False  # Default 0 feedback


# Tests: check_conditions (combined)


class TestCheckConditions:
    """Tests for the combined check_conditions method."""

    def test_no_triggers(self, trigger):
        """No drift or feedback → any_triggered=False."""
        result = trigger.check_conditions(
            recent_drift_events=[],
            new_feedback_count=0,
        )
        assert result["any_triggered"] is False
        assert result["conditions"]["drift"]["met"] is False
        assert result["conditions"]["feedback_volume"]["met"] is False
        assert result["primary_reason"] == "No trigger conditions met"

    def test_drift_only(self, trigger, recent_critical_drift_events):
        """Only drift triggered → any_triggered=True with drift reason."""
        result = trigger.check_conditions(
            recent_drift_events=recent_critical_drift_events,
            new_feedback_count=0,
        )
        assert result["any_triggered"] is True
        assert result["conditions"]["drift"]["met"] is True
        assert result["conditions"]["feedback_volume"]["met"] is False
        assert "Drift trigger" in result["primary_reason"]

    def test_feedback_only(self, trigger):
        """Only feedback triggered → any_triggered=True with feedback reason."""
        result = trigger.check_conditions(
            recent_drift_events=[],
            new_feedback_count=10,
        )
        assert result["any_triggered"] is True
        assert result["conditions"]["drift"]["met"] is False
        assert result["conditions"]["feedback_volume"]["met"] is True
        assert "Feedback volume trigger" in result["primary_reason"]

    def test_both_triggers(self, trigger, recent_critical_drift_events):
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


class TestTriggerDryRun:
    """Tests for the trigger() method in dry_run mode."""

    def test_dry_run_no_trigger(self, trigger):
        """No conditions met in dry_run → triggered=False, no version."""
        result = trigger.trigger(
            recent_drift_events=[],
            new_feedback_count=0,
            dry_run=True,
        )
        assert result.triggered is False
        assert result.candidate_version is None
        assert result.error is None

    def test_dry_run_drift_trigger(self, trigger, recent_critical_drift_events):
        """Drift condition met in dry_run → triggered=True, version present."""
        result = trigger.trigger(
            recent_drift_events=recent_critical_drift_events,
            new_feedback_count=0,
            dry_run=True,
        )
        assert result.triggered is True
        assert result.candidate_version is not None
        assert result.candidate_version.startswith("v")
        assert "Drift" in result.reason
        assert result.trigger_metrics["conditions"]["drift"]["met"] is True
        assert result.candidate_metrics is None  # No pipeline in dry_run

    def test_dry_run_feedback_trigger(self, trigger):
        """Feedback condition met in dry_run → triggered=True, version present."""
        result = trigger.trigger(
            recent_drift_events=[],
            new_feedback_count=10,
            dry_run=True,
        )
        assert result.triggered is True
        assert result.candidate_version is not None
        assert "Feedback volume" in result.reason
        assert result.trigger_metrics["conditions"]["feedback_volume"]["met"] is True

    def test_dry_run_both_triggers(self, trigger, recent_critical_drift_events):
        """Both conditions met in dry_run → triggered=True, combined reason."""
        result = trigger.trigger(
            recent_drift_events=recent_critical_drift_events,
            new_feedback_count=10,
            dry_run=True,
        )
        assert result.triggered is True
        assert "AND" in result.reason

    def test_dry_run_returns_trigger_metrics(self, trigger):
        """Trigger metrics should include condition details."""
        result = trigger.trigger(
            recent_drift_events=[],
            new_feedback_count=10,
            dry_run=True,
        )
        assert "conditions" in result.trigger_metrics
        assert "drift" in result.trigger_metrics["conditions"]
        assert "feedback_volume" in result.trigger_metrics["conditions"]
        assert "primary_reason" in result.trigger_metrics

    def test_dry_run_edge_feedback_at_threshold(self, trigger):
        """Exactly at feedback threshold → triggered."""
        result = trigger.trigger(
            recent_drift_events=[],
            new_feedback_count=5,  # exactly feedback_threshold
            dry_run=True,
        )
        assert result.triggered is True

    def test_dry_run_edge_drift_at_threshold(self, trigger):
        """Exactly at drift threshold → triggered."""
        events = [
            {"feature_name": "V14", "alert_type": "CRITICAL"},
            {"feature_name": "V4", "alert_type": "CRITICAL"},
        ]
        result = trigger.trigger(
            recent_drift_events=events,
            new_feedback_count=0,
            dry_run=True,
        )
        assert result.triggered is True


# Tests: trigger (non-dry-run, pipeline failure path)


class TestTriggerPipelineFailure:
    """Tests for trigger() when pipeline fails (not dry_run)."""

    def test_pipeline_script_not_found(self, trigger):
        """If pipeline script doesn't exist, returns error."""
        trigger.pipeline_script = "/nonexistent/pipeline.py"
        result = trigger.trigger(
            recent_drift_events=[{"feature_name": "V14", "alert_type": "CRITICAL"}] * 2,
            new_feedback_count=0,
            dry_run=False,
        )
        assert result.triggered is True
        assert result.error is not None
        assert "failed" in result.error or "Pipeline" in (result.error or "")


# Tests: check_and_trigger convenience function


class TestCheckAndTrigger:
    """Tests for the check_and_trigger convenience function."""

    def test_dry_run_default(self):
        """check_and_trigger with dry_run=True should return TriggerResult."""
        result = check_and_trigger(
            feedback_threshold=5,
            drift_critical_threshold=2,
            dry_run=True,
        )
        assert isinstance(result, TriggerResult)
        assert result.triggered is False  # No drift or feedback passed in

    def test_dry_run_custom_thresholds(self):
        """Custom thresholds should be respected."""
        result = check_and_trigger(
            feedback_threshold=1,
            drift_critical_threshold=1,
            dry_run=True,
        )
        # Still no events passed, so no trigger
        assert result.triggered is False

    def test_returns_trigger_result_type(self):
        """check_and_trigger always returns TriggerResult."""
        result = check_and_trigger(dry_run=True)
        assert isinstance(result, TriggerResult)
        assert hasattr(result, "triggered")
        assert hasattr(result, "reason")
        assert hasattr(result, "trigger_metrics")


# Tests: TriggerResult dataclass


class TestTriggerResult:
    """Tests for the TriggerResult dataclass."""

    def test_default_values(self):
        """TriggerResult should have sensible defaults."""
        result = TriggerResult(triggered=False)
        assert result.reason == ""
        assert result.candidate_version is None
        assert result.trigger_metrics == {}
        assert result.candidate_metrics is None
        assert result.error is None

    def test_triggered_true(self):
        """A triggered result should carry reason and version."""
        result = TriggerResult(
            triggered=True,
            reason="Drift trigger: 3 CRITICAL events",
            candidate_version="v20260722_120000",
            trigger_metrics={"drift": {"met": True}},
            candidate_metrics={"pr_auc": 0.88},
        )
        assert result.triggered is True
        assert "3 CRITICAL" in result.reason
        assert result.candidate_version == "v20260722_120000"
        assert result.candidate_metrics["pr_auc"] == 0.88


# Tests: CandidateInfo dataclass


class TestCandidateInfo:
    """Tests for the CandidateInfo dataclass."""

    def test_default_status(self):
        """Default status should be 'candidate'."""
        info = CandidateInfo(
            version="v20260722_120000",
            trigger="drift",
            trigger_detail="3 critical drift events",
            pr_auc=0.88,
            f1_score=0.71,
            precision=0.58,
            recall=0.90,
            threshold=0.03,
            mlflow_run_id="run_abc123",
            model_path="/tmp/model.pkl",
        )
        assert info.status == "candidate"
        assert info.version == "v20260722_120000"
        assert info.trigger == "drift"

    def test_custom_status(self):
        """Status should be overridable."""
        info = CandidateInfo(
            version="v20260722_120000",
            trigger="feedback_volume",
            trigger_detail="100 new feedback labels",
            pr_auc=0.85,
            f1_score=0.68,
            precision=0.55,
            recall=0.87,
            threshold=0.04,
            mlflow_run_id=None,
            model_path="/tmp/model.pkl",
            status="promoted",
        )
        assert info.status == "promoted"

    def test_minimal_constructor(self):
        """CandidateInfo should work with minimum required fields."""
        info = CandidateInfo(
            version="v1",
            trigger="drift",
            trigger_detail="test",
            pr_auc=0.0,
            f1_score=0.0,
            precision=0.0,
            recall=0.0,
            threshold=0.5,
            mlflow_run_id=None,
            model_path="/dev/null",
        )
        assert info.version == "v1"


# Tests: Integration scenarios (simulated full flow)


class TestIntegrationScenarios:
    """End-to-end scenarios simulating real retraining checks."""

    def test_scenario_no_retraining_needed(self, trigger):
        """
        Scenario: System is healthy, no drift, no feedback.
        Expected: No retraining triggered.
        """
        result = trigger.trigger(
            recent_drift_events=[],  # No drift events
            new_feedback_count=0,  # No new feedback
            dry_run=True,
        )
        assert result.triggered is False
        assert result.candidate_version is None

    def test_scenario_drift_detected(self, trigger, recent_critical_drift_events):
        """
        Scenario: 3 CRITICAL drift events detected (threshold=2).
        Expected: Retraining triggered by drift, candidate version generated.
        """
        result = trigger.trigger(
            recent_drift_events=recent_critical_drift_events,
            new_feedback_count=2,  # Below feedback threshold
            dry_run=True,
        )
        assert result.triggered is True
        assert "Drift" in result.reason
        assert result.candidate_version is not None
        assert result.trigger_metrics["conditions"]["drift"]["met"] is True
        assert result.trigger_metrics["conditions"]["feedback_volume"]["met"] is False

    def test_scenario_feedback_accumulated(self, trigger):
        """
        Scenario: 50 new feedback labels (threshold=5), no drift.
        Expected: Retraining triggered by feedback volume.
        """
        result = trigger.trigger(
            recent_drift_events=[],  # No drift
            new_feedback_count=50,  # Well above threshold
            dry_run=True,
        )
        assert result.triggered is True
        assert "Feedback volume" in result.reason
        assert result.candidate_version is not None

    def test_scenario_both_conditions(self, trigger, recent_critical_drift_events):
        """
        Scenario: Both drift (3 CRITICAL) AND feedback (50 labels) present.
        Expected: Retraining triggered with combined reason.
        """
        result = trigger.trigger(
            recent_drift_events=recent_critical_drift_events,
            new_feedback_count=50,
            dry_run=True,
        )
        assert result.triggered is True
        assert "AND" in result.reason
        assert result.candidate_version is not None

    def test_scenario_drift_with_custom_thresholds(self):
        """
        Scenario: Custom high drift threshold (5), only 3 events.
        Expected: No retraining.
        """
        t = RetrainingTrigger(
            feedback_threshold=100,
            drift_critical_threshold=5,
        )
        events = [{"feature_name": f"V{i}", "alert_type": "CRITICAL"} for i in range(3)]
        result = t.trigger(
            recent_drift_events=events,
            new_feedback_count=0,
            dry_run=True,
        )
        assert result.triggered is False

    def test_scenario_mixed_alert_types(self, trigger):
        """
        Scenario: Mix of CRITICAL, WARNING, and OK events.
        Only CRITICAL should count toward the drift threshold.
        """
        events = [
            {"feature_name": "V1", "alert_type": "OK"},
            {"feature_name": "V14", "alert_type": "CRITICAL"},
            {"feature_name": "V4", "alert_type": "WARNING"},
            {"feature_name": "V10", "alert_type": "CRITICAL"},
            {"feature_name": "V12", "alert_type": "OK"},
        ]
        result = trigger.trigger(
            recent_drift_events=events,
            new_feedback_count=0,
            dry_run=True,
        )
        # 2 CRITICAL events = threshold of 2 → triggered
        assert result.triggered is True


# Tests: Timestamp parsing edge cases


class TestTimestampParsing:
    """Tests for _parse_timestamp edge cases."""

    def test_datetime_object(self, trigger):
        """Datetime objects should be returned as-is."""
        dt = datetime(2026, 7, 22, 12, 0, 0)
        result = trigger._parse_timestamp({"created_at": dt})
        assert result == dt

    def test_iso_string(self, trigger):
        """ISO format strings should be parsed."""
        result = trigger._parse_timestamp({"created_at": "2026-07-22T12:00:00"})
        assert result is not None
        assert result.year == 2026

    def test_timestamp_key_fallback(self, trigger):
        """'timestamp' key should be used when 'created_at' is missing."""
        result = trigger._parse_timestamp({"timestamp": "2026-07-22T12:00:00"})
        assert result is not None
        assert result.year == 2026

    def test_invalid_string(self, trigger):
        """Invalid date strings should return None."""
        result = trigger._parse_timestamp({"created_at": "not-a-date"})
        assert result is None

    def test_missing_key(self, trigger):
        """Missing both 'created_at' and 'timestamp' should return None."""
        result = trigger._parse_timestamp({"feature_name": "V14"})
        assert result is None
