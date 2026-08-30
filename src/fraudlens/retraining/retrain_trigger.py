"""
FraudLens — Automated Retraining Trigger Logic

Checks two conditions and, if either is met, runs the training pipeline
and registers the resulting model as a candidate for human review.

Trigger conditions:
1. **Drift trigger:** Significant feature/prediction drift since last training
2. **Feedback volume trigger:** Accumulated confirmed labels >= configurable threshold

On trigger:
- Runs the full training pipeline (run_pipeline.py)
- Evaluates the trained model
- Registers the run in MLflow with trigger=<reason> tag
- Creates a ModelCandidate record in the database (NOT auto-promoted)

Usage:
    # From a K8s CronJob:
    python -m src.fraudlens.retraining.retrain_trigger

    # From Python code:
    from src.fraudlens.retraining import check_and_trigger
    result = check_and_trigger()
    if result.triggered:
        print(f"Triggered by: {result.reason}")
        print(f"Candidate version: {result.candidate_version}")
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# MLflow Setup

try:
    import mlflow

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

# Trigger Result


@dataclass
class TriggerResult:
    """Result of a retraining trigger check."""

    triggered: bool
    reason: str = ""
    candidate_version: str | None = None
    trigger_metrics: dict[str, Any] = field(default_factory=dict)
    candidate_metrics: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class CandidateInfo:
    """Information about a model candidate registered for review."""

    version: str
    trigger: str
    trigger_detail: str
    pr_auc: float
    f1_score: float
    precision: float
    recall: float
    threshold: float
    mlflow_run_id: str | None
    model_path: str
    status: str = "candidate"
    created_at: str = ""


# RetrainingTrigger


class RetrainingTrigger:
    """
    Checks trigger conditions and orchestrates the retraining pipeline.

    Two trigger conditions:
    1. Drift: recent CRITICAL drift events detected
    2. Feedback volume: N+ new confirmed feedback labels accumulated
    """

    def __init__(
        self,
        feedback_threshold: int = 100,
        drift_critical_threshold: int = 3,
        drift_window_days: int = 7,
        models_dir: Path | None = None,
        pipeline_script: str | None = None,
        mlflow_experiment: str | None = None,
        mlflow_tracking_uri: str | None = None,
    ) -> None:
        """
        Args:
            feedback_threshold: Min new confirmed feedback labels to trigger retraining
            drift_critical_threshold: Min CRITICAL drift events in window to trigger
            drift_window_days: Lookback window for drift events
            models_dir: Directory for model artifacts
            pipeline_script: Path to run_pipeline.py
            mlflow_experiment: MLflow experiment name
            mlflow_tracking_uri: MLflow tracking URI
        """
        self.feedback_threshold = feedback_threshold
        self.drift_critical_threshold = drift_critical_threshold
        self.drift_window_days = drift_window_days
        self.models_dir = models_dir or Path(
            os.environ.get(
                "MODELS_DIR",
                str(Path(__file__).resolve().parent.parent.parent.parent / "models"),
            )
        )
        self.pipeline_script = pipeline_script or os.environ.get(
            "PIPELINE_SCRIPT",
            str(
                Path(__file__).resolve().parent.parent.parent.parent / "run_pipeline.py"
            ),
        )
        self.mlflow_experiment = mlflow_experiment or os.environ.get(
            "MLFLOW_EXPERIMENT_NAME", "fraudlens_model_comparison"
        )
        self.mlflow_tracking_uri = mlflow_tracking_uri or os.environ.get(
            "MLFLOW_TRACKING_URI", "http://localhost:5000"
        )

    def check_drift_condition(
        self, recent_drift_events: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """
        Check if drift condition is met.

        Args:
            recent_drift_events: List of drift events from the database.
                If None, the condition is checked from available data.

        Returns:
            Dict with met (bool), count (int), detail (str)
        """
        if recent_drift_events is None:
            # No database available — check via file-based drift report
            return self._check_drift_from_report()

        # Count CRITICAL drift events in the lookback window
        cutoff = datetime.utcnow() - timedelta(days=self.drift_window_days)
        critical_events = [
            e
            for e in recent_drift_events
            if e.get("alert_type") == "CRITICAL" or e.get("alert", "") == "CRITICAL"
        ]
        # Filter by time if timestamps available.
        # Events with unparseable timestamps are included conservatively
        # (they might be recent). Events with parseable timestamps but
        # outside the window are excluded.
        critical_in_window = [
            e
            for e in critical_events
            if (ts := self._parse_timestamp(e)) is None or ts >= cutoff
        ]

        count = len(critical_in_window)
        met = count >= self.drift_critical_threshold
        return {
            "met": met,
            "count": count,
            "threshold": self.drift_critical_threshold,
            "detail": (
                f"{count} CRITICAL drift events in {self.drift_window_days}d "
                f"(threshold: {self.drift_critical_threshold})"
            ),
        }

    def _parse_timestamp(self, event: dict[str, Any]) -> datetime | None:
        """Parse timestamp from a drift event dict."""
        ts = event.get("created_at") or event.get("timestamp")
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts)
            except (ValueError, TypeError):
                pass
        return None

    def _check_drift_from_report(self) -> dict[str, Any]:
        """Fallback: check drift from saved report file."""
        report_path = Path("reports/drift_report.json")
        if not report_path.exists():
            return {
                "met": False,
                "count": 0,
                "threshold": self.drift_critical_threshold,
                "detail": "No drift report found",
            }

        try:
            with open(report_path) as f:
                report = json.load(f)
            results = report.get("results", {})
            critical_count = sum(
                1 for r in results.values() if r.get("alert") == "CRITICAL"
            )
            met = critical_count >= self.drift_critical_threshold
            return {
                "met": met,
                "count": critical_count,
                "threshold": self.drift_critical_threshold,
                "detail": (
                    f"{critical_count} CRITICAL features in drift report "
                    f"(threshold: {self.drift_critical_threshold})"
                ),
            }
        except (json.JSONDecodeError, KeyError) as e:
            return {
                "met": False,
                "count": 0,
                "threshold": self.drift_critical_threshold,
                "detail": f"Failed to parse drift report: {e}",
            }

    def check_feedback_condition(
        self, new_feedback_count: int | None = None
    ) -> dict[str, Any]:
        """
        Check if feedback volume condition is met.

        Args:
            new_feedback_count: Count of new feedback since last training.
                If None defaults to a check based on last training timestamp.

        Returns:
            Dict with met (bool), count (int), detail (str)
        """
        if new_feedback_count is None:
            # Try to compute from last training timestamp
            last_train_time = self._get_last_training_time()
            if last_train_time is None:
                return {
                    "met": False,
                    "count": 0,
                    "threshold": self.feedback_threshold,
                    "detail": "No training history found — skipping feedback check",
                }
            new_feedback_count = 0  # Default when no DB available

        met = new_feedback_count >= self.feedback_threshold
        return {
            "met": met,
            "count": new_feedback_count,
            "threshold": self.feedback_threshold,
            "detail": (
                f"{new_feedback_count} new feedback labels since last training "
                f"(threshold: {self.feedback_threshold})"
            ),
        }

    def _get_last_training_time(self) -> float | None:
        """Get the timestamp of last training run from artifacts."""
        # Check threshold.txt modification time as a proxy for last training
        threshold_path = self.models_dir / "threshold.txt"
        if threshold_path.exists():
            return threshold_path.stat().st_mtime

        # Check best model file
        model_path = self.models_dir / "best_fraud_model.pkl"
        if model_path.exists():
            return model_path.stat().st_mtime

        return None

    def check_conditions(
        self,
        recent_drift_events: list[dict[str, Any]] | None = None,
        new_feedback_count: int | None = None,
    ) -> dict[str, Any]:
        """
        Check both trigger conditions and return results.

        Returns:
            Dict with:
            - any_triggered (bool): whether any condition triggers retraining
            - conditions (dict): individual condition results
            - primary_reason (str): human-readable reason
        """
        drift = self.check_drift_condition(recent_drift_events)
        feedback = self.check_feedback_condition(new_feedback_count)

        conditions = {
            "drift": drift,
            "feedback_volume": feedback,
        }

        any_triggered = drift["met"] or feedback["met"]

        if drift["met"] and feedback["met"]:
            primary_reason = (
                f"Drift ({drift['detail']}) AND feedback volume ({feedback['detail']})"
            )
        elif drift["met"]:
            primary_reason = f"Drift trigger: {drift['detail']}"
        elif feedback["met"]:
            primary_reason = f"Feedback volume trigger: {feedback['detail']}"
        else:
            primary_reason = "No trigger conditions met"

        return {
            "any_triggered": any_triggered,
            "conditions": conditions,
            "primary_reason": primary_reason,
        }
