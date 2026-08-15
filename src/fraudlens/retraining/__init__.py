"""
FraudLens — Automated Retraining Module

Provides trigger-based automated model retraining with human-gated promotion:
- Drift trigger: checks for CRITICAL drift events since last training
- Feedback volume trigger: checks if accumulated feedback >= threshold
- Runs the full training pipeline when triggered
- Registers the trained model as a candidate (never auto-promotes)
- Exposes candidates for human review via admin API

Usage:
    from src.fraudlens.retraining.retrain_trigger import check_and_trigger
    result = check_and_trigger()  # Returns TriggerResult
"""

from .retrain_trigger import (
    CandidateInfo,
    RetrainingTrigger,
    TriggerResult,
    check_and_trigger,
    run_retraining_pipeline,
)

__all__ = [
    "RetrainingTrigger",
    "TriggerResult",
    "CandidateInfo",
    "check_and_trigger",
    "run_retraining_pipeline",
]
