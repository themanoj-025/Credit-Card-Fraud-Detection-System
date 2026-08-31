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
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

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

    def run_pipeline(self) -> bool:
        """
        Execute the full training pipeline as a subprocess.

        Returns:
            True if pipeline completed successfully, False otherwise
        """
        pipeline = Path(self.pipeline_script)
        if not pipeline.exists():
            logger.error("Pipeline script not found: %s", pipeline)
            return False

        logger.info("Starting training pipeline: %s", pipeline)
        try:
            result = subprocess.run(
                [sys.executable, str(pipeline)],
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour max
                env={**os.environ},
            )
            if result.returncode == 0:
                logger.info("Pipeline completed successfully")
                logger.debug("Pipeline output:\n%s", result.stdout[-2000:])
                return True
            else:
                logger.error(
                    "Pipeline failed (exit code %d):\n%s",
                    result.returncode,
                    result.stderr[-2000:],
                )
                return False
        except subprocess.TimeoutExpired:
            logger.error("Pipeline timed out after 3600s")
            return False
        except (RuntimeError, ValueError, OSError) as e:
            logger.error("Pipeline execution failed: %s", e)
            return False

    def register_mlflow_run(
        self,
        trigger: str,
        trigger_detail: str,
        metrics: dict[str, float],
    ) -> str | None:
        """
        Tag the latest MLflow run and return the run ID.

        Args:
            trigger: Trigger type ("drift" or "feedback_volume")
            trigger_detail: Human-readable trigger description
            metrics: Evaluation metrics dict

        Returns:
            MLflow run ID string, or None if unavailable
        """
        if not MLFLOW_AVAILABLE:
            logger.warning("MLflow not available — skipping run registration")
            return None

        try:
            mlflow.set_tracking_uri(self.mlflow_tracking_uri)
            mlflow.set_experiment(self.mlflow_experiment)

            experiment = mlflow.get_experiment_by_name(self.mlflow_experiment)
            if experiment is None:
                logger.warning(
                    "MLflow experiment '%s' not found", self.mlflow_experiment
                )
                return None

            # Find the latest run in the experiment
            runs = mlflow.search_runs(
                experiment_ids=[experiment.experiment_id],
                order_by=["start_time DESC"],
                max_results=1,
            )

            if runs.empty:
                logger.warning("No MLflow runs found to tag")
                return None

            run_id = runs.iloc[0]["run_id"]
            with mlflow.start_run(run_id=run_id):
                mlflow.set_tag("trigger", trigger)
                mlflow.set_tag("trigger_detail", trigger_detail[:200])
                mlflow.set_tag("is_candidate", "true")

                # Log trigger metrics
                for k, v in metrics.items():
                    if isinstance(v, (int, float)):
                        mlflow.log_metric(f"candidate_{k}", v)

            logger.info(
                "MLflow run %s tagged as candidate (trigger=%s)", run_id[:12], trigger
            )
            return run_id

        except (RuntimeError, ValueError, OSError) as e:
            logger.warning("MLflow run registration failed: %s", e)
            return None

    def extract_metrics(self) -> dict[str, float] | None:
        """
        Extract evaluation metrics from the latest training run.

        Reads from reports/final_results.json generated by run_pipeline.py.

        Returns:
            Dict with pr_auc, f1, precision, recall, threshold or None
        """
        reports_dir = self.models_dir.parent / "reports"
        results_path = reports_dir / "final_results.json"

        if results_path.exists():
            try:
                with open(results_path) as f:
                    results = json.load(f)
                metrics = results.get("metrics", {})
                return {
                    "pr_auc": metrics.get("pr_auc", 0.0),
                    "f1": metrics.get("f1", 0.0),
                    "precision": metrics.get("precision", 0.0),
                    "recall": metrics.get("recall", 0.0),
                    "threshold": results.get("best_threshold", 0.5),
                    "model_name": results.get("best_model", "unknown"),
                }
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to read final_results.json: %s", e)

        # Fallback: read comparison CSV
        csv_path = reports_dir / "model_comparison_fraud.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                if not df.empty:
                    best = df.iloc[0]
                    return {
                        "pr_auc": float(best.get("PR-AUC", 0.0)),
                        "f1": float(best.get("F1", 0.0)),
                        "precision": float(best.get("Precision", 0.0)),
                        "recall": float(best.get("Recall", 0.0)),
                        "threshold": float(best.get("Threshold", 0.5)),
                        "model_name": best.get("Model", "unknown"),
                    }
            except (RuntimeError, ValueError, OSError) as e:
                logger.warning("Failed to read comparison CSV: %s", e)

        return None

    def generate_candidate_version(self) -> str:
        """Generate a candidate version string."""
        now = datetime.utcnow()
        return now.strftime("v%Y%m%d_%H%M%S")

    def trigger(
        self,
        recent_drift_events: list[dict[str, Any]] | None = None,
        new_feedback_count: int | None = None,
        dry_run: bool = False,
    ) -> TriggerResult:
        """
        Check conditions and, if triggered, run retraining pipeline.

        Args:
            recent_drift_events: Optional list of recent drift events from DB
            new_feedback_count: Optional count of new feedback since last training
            dry_run: If True, check conditions but don't run pipeline

        Returns:
            TriggerResult with outcome details
        """
        # Step 1: Check conditions
        check = self.check_conditions(recent_drift_events, new_feedback_count)

        if not check["any_triggered"]:
            logger.info("Retraining not triggered: %s", check["primary_reason"])
            return TriggerResult(
                triggered=False,
                reason=check["primary_reason"],
                trigger_metrics=check,
            )

        logger.info("Retraining triggered: %s", check["primary_reason"])

        if dry_run:
            return TriggerResult(
                triggered=True,
                reason=check["primary_reason"],
                trigger_metrics=check,
                candidate_version=self.generate_candidate_version(),
            )

        # Step 2: Run the training pipeline
        pipeline_ok = self.run_pipeline()
        if not pipeline_ok:
            return TriggerResult(
                triggered=True,
                reason=check["primary_reason"],
                trigger_metrics=check,
                error="Training pipeline failed",
            )

        # Step 3: Extract metrics from training output
        metrics = self.extract_metrics()
        if metrics is None:
            return TriggerResult(
                triggered=True,
                reason=check["primary_reason"],
                trigger_metrics=check,
                error="Failed to extract metrics after training",
            )

        # Step 4: Register in MLflow
        trigger_type = (
            "drift" if check["conditions"]["drift"]["met"] else "feedback_volume"
        )
        mlflow_run_id = self.register_mlflow_run(
            trigger=trigger_type,
            trigger_detail=check["primary_reason"],
            metrics=metrics,
        )

        # Step 5: Generate candidate version
        candidate_version = self.generate_candidate_version()

        logger.info(
            "Retraining complete: candidate=%s trigger=%s pr_auc=%.4f mlflow_run=%s",
            candidate_version,
            trigger_type,
            metrics.get("pr_auc", 0.0),
            mlflow_run_id or "N/A",
        )

        return TriggerResult(
            triggered=True,
            reason=check["primary_reason"],
            candidate_version=candidate_version,
            trigger_metrics=check,
            candidate_metrics=metrics,
        )


# Standalone CLI Entrypoint


def check_and_trigger(
    feedback_threshold: int | None = None,
    drift_critical_threshold: int | None = None,
    dry_run: bool = False,
) -> TriggerResult:
    """
    Convenience function to check conditions and trigger retraining.

    Reads configuration from environment variables:
    - RETRAINING_FEEDBACK_THRESHOLD (default: 100)
    - RETRAINING_DRIFT_CRITICAL_THRESHOLD (default: 3)
    - RETRAINING_DRY_RUN (set to "true" for dry run)

    Args:
        feedback_threshold: Override for feedback volume threshold
        drift_critical_threshold: Override for drift event threshold
        dry_run: If True, check conditions but don't run pipeline

    Returns:
        TriggerResult with outcome details
    """
    trigger = RetrainingTrigger(
        feedback_threshold=feedback_threshold
        or int(os.environ.get("RETRAINING_FEEDBACK_THRESHOLD", "100")),
        drift_critical_threshold=drift_critical_threshold
        or int(os.environ.get("RETRAINING_DRIFT_CRITICAL_THRESHOLD", "3")),
    )
    return trigger.trigger(dry_run=dry_run)


def run_retraining_pipeline() -> None:
    """
    Main entry point for K8s CronJob execution.

    Called as:
        python -m src.fraudlens.retraining.retrain_trigger

    Reads config from environment and logs results for CloudWatch/journald.
    """
    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    dry_run = os.environ.get("RETRAINING_DRY_RUN", "").lower() == "true"

    logger.info("Retraining trigger check starting (dry_run=%s)...", dry_run)

    result = check_and_trigger(dry_run=dry_run)

    if result.error:
        logger.error("Retraining failed: %s", result.error)
        sys.exit(1)

    if result.triggered:
        logger.info(
            "Retraining triggered: %s | candidate=%s | metrics=%s",
            result.reason,
            result.candidate_version or "N/A",
            json.dumps(result.candidate_metrics or {}),
        )
    else:
        logger.info("Retraining not triggered: %s", result.reason)

    # Output JSON summary to stdout for logging
    summary = {
        "triggered": result.triggered,
        "reason": result.reason,
        "candidate_version": result.candidate_version,
        "candidate_metrics": result.candidate_metrics,
        "error": result.error,
    }
    logger.info("Retraining summary:\n%s", json.dumps(summary, indent=2))


if __name__ == "__main__":
    run_retraining_pipeline()
