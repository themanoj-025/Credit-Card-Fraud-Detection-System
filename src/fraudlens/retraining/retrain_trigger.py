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
import sys

from src.fraudlens.retraining.retrain_models import (
    RetrainingTrigger,
    TriggerResult,
)

logger = logging.getLogger(__name__)


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
