"""FraudLens — Retraining Trigger Tests

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
8. check_and_trigger() convenience function — Part 2."""

from datetime import datetime

from src.fraudlens.retraining.retrain_trigger import (
    CandidateInfo,
    RetrainingTrigger,
    TriggerResult,
    check_and_trigger,
)


class TestTriggerDryRun:
    """Tests for the trigger() method in dry_run mode."""

    def test_dry_run_no_trigger(self, trigger) -> None:
        """No conditions met in dry_run → triggered=False, no version."""
        result = trigger.trigger(
            recent_drift_events=[],
            new_feedback_count=0,
            dry_run=True,
        )
        assert result.triggered is False
        assert result.candidate_version is None
        assert result.error is None

    def test_dry_run_drift_trigger(self, trigger, recent_critical_drift_events) -> None:
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

    def test_dry_run_feedback_trigger(self, trigger) -> None:
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

    def test_dry_run_both_triggers(self, trigger, recent_critical_drift_events) -> None:
        """Both conditions met in dry_run → triggered=True, combined reason."""
        result = trigger.trigger(
            recent_drift_events=recent_critical_drift_events,
            new_feedback_count=10,
            dry_run=True,
        )
        assert result.triggered is True
        assert "AND" in result.reason

    def test_dry_run_returns_trigger_metrics(self, trigger) -> None:
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

    def test_dry_run_edge_feedback_at_threshold(self, trigger) -> None:
        """Exactly at feedback threshold → triggered."""
        result = trigger.trigger(
            recent_drift_events=[],
            new_feedback_count=5,  # exactly feedback_threshold
            dry_run=True,
        )
        assert result.triggered is True

    def test_dry_run_edge_drift_at_threshold(self, trigger) -> None:
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

    def test_pipeline_script_not_found(self, trigger) -> None:
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

    def test_dry_run_default(self) -> None:
        """check_and_trigger with dry_run=True should return TriggerResult."""
        result = check_and_trigger(
            feedback_threshold=5,
            drift_critical_threshold=2,
            dry_run=True,
        )
        assert isinstance(result, TriggerResult)
        assert result.triggered is False  # No drift or feedback passed in

    def test_dry_run_custom_thresholds(self) -> None:
        """Custom thresholds should be respected."""
        result = check_and_trigger(
            feedback_threshold=1,
            drift_critical_threshold=1,
            dry_run=True,
        )
        # Still no events passed, so no trigger
        assert result.triggered is False

    def test_returns_trigger_result_type(self) -> None:
        """check_and_trigger always returns TriggerResult."""
        result = check_and_trigger(dry_run=True)
        assert isinstance(result, TriggerResult)
        assert hasattr(result, "triggered")
        assert hasattr(result, "reason")
        assert hasattr(result, "trigger_metrics")


# Tests: TriggerResult dataclass


class TestTriggerResult:
    """Tests for the TriggerResult dataclass."""

    def test_default_values(self) -> None:
        """TriggerResult should have sensible defaults."""
        result = TriggerResult(triggered=False)
        assert result.reason == ""
        assert result.candidate_version is None
        assert result.trigger_metrics == {}
        assert result.candidate_metrics is None
        assert result.error is None

    def test_triggered_true(self) -> None:
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

    def test_default_status(self) -> None:
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

    def test_custom_status(self) -> None:
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

    def test_minimal_constructor(self) -> None:
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

    def test_scenario_no_retraining_needed(self, trigger) -> None:
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

    def test_scenario_drift_detected(self, trigger, recent_critical_drift_events) -> None:
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

    def test_scenario_feedback_accumulated(self, trigger) -> None:
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

    def test_scenario_both_conditions(self, trigger, recent_critical_drift_events) -> None:
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

    def test_scenario_drift_with_custom_thresholds(self) -> None:
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

    def test_scenario_mixed_alert_types(self, trigger) -> None:
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

    def test_datetime_object(self, trigger) -> None:
        """Datetime objects should be returned as-is."""
        dt = datetime(2026, 7, 22, 12, 0, 0)
        result = trigger._parse_timestamp({"created_at": dt})
        assert result == dt

    def test_iso_string(self, trigger) -> None:
        """ISO format strings should be parsed."""
        result = trigger._parse_timestamp({"created_at": "2026-07-22T12:00:00"})
        assert result is not None
        assert result.year == 2026

    def test_timestamp_key_fallback(self, trigger) -> None:
        """'timestamp' key should be used when 'created_at' is missing."""
        result = trigger._parse_timestamp({"timestamp": "2026-07-22T12:00:00"})
        assert result is not None
        assert result.year == 2026

    def test_invalid_string(self, trigger) -> None:
        """Invalid date strings should return None."""
        result = trigger._parse_timestamp({"created_at": "not-a-date"})
        assert result is None

    def test_missing_key(self, trigger) -> None:
        """Missing both 'created_at' and 'timestamp' should return None."""
        result = trigger._parse_timestamp({"feature_name": "V14"})
        assert result is None
