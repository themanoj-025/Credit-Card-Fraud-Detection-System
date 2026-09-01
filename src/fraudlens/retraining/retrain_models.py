"""
FraudLens — Retraining trigger models and logic.

Extracted from retrain_trigger.py for modularity.
Contains TriggerResult, CandidateInfo, and RetrainingTrigger.
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

try:
    import mlflow

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


@dataclass
class TriggerResult:
    """Result of a retraining trigger check."""

    triggered: bool
    reason: str = ""
    candidate_version: str | None = None
    trigger_metrics: dict[str, Any] = field(default_factory=dict)
    candidate_metrics: dict[str, float] | None = None
    error: str | None = None


@dataclass
class CandidateInfo:
    """Information about a candidate model."""

    version: str
    trigger: str
    trigger_detail: str
    metrics: dict[str, float]
    mlflow_run_id: str | None = None


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
        if recent_drift_events is None:
            return self._check_drift_from_report()

        cutoff = datetime.utcnow() - timedelta(days=self.drift_window_days)
        critical_events = [
            e
            for e in recent_drift_events
            if e.get("alert_type") == "CRITICAL" or e.get("alert", "") == "CRITICAL"
        ]
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
        if new_feedback_count is None:
            last_train_time = self._get_last_training_time()
            if last_train_time is None:
                return {
                    "met": False,
                    "count": 0,
                    "threshold": self.feedback_threshold,
                    "detail": "No training history found — skipping feedback check",
                }
            new_feedback_count = 0

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
        threshold_path = self.models_dir / "threshold.txt"
        if threshold_path.exists():
            return threshold_path.stat().st_mtime

        model_path = self.models_dir / "best_fraud_model.pkl"
        if model_path.exists():
            return model_path.stat().st_mtime

        return None

    def check_conditions(
        self,
        recent_drift_events: list[dict[str, Any]] | None = None,
        new_feedback_count: int | None = None,
    ) -> dict[str, Any]:
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
                timeout=3600,
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
        now = datetime.utcnow()
        return now.strftime("v%Y%m%d_%H%M%S")

    def trigger(
        self,
        recent_drift_events: list[dict[str, Any]] | None = None,
        new_feedback_count: int | None = None,
        dry_run: bool = False,
    ) -> TriggerResult:
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

        pipeline_ok = self.run_pipeline()
        if not pipeline_ok:
            return TriggerResult(
                triggered=True,
                reason=check["primary_reason"],
                trigger_metrics=check,
                error="Training pipeline failed",
            )

        metrics = self.extract_metrics()
        if metrics is None:
            return TriggerResult(
                triggered=True,
                reason=check["primary_reason"],
                trigger_metrics=check,
                error="Failed to extract metrics after training",
            )

        trigger_type = (
            "drift" if check["conditions"]["drift"]["met"] else "feedback_volume"
        )
        mlflow_run_id = self.register_mlflow_run(
            trigger=trigger_type,
            trigger_detail=check["primary_reason"],
            metrics=metrics,
        )

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
