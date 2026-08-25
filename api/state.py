"""
FraudLens API — Shared Application State.

Extracts global state from api/main.py into a separate module so routers
can import it without creating circular import cycles.

Usage:
    from api.state import get_predictor, get_anomaly_detector
"""

import logging

logger = logging.getLogger(__name__)

# Internal State (set by api/main.py during startup)
_predictor = None
_anomaly_detector = None
_case_narrator = None
_case_retriever = None
_copilot_client = None


# Setter functions (called from api/main.py lifespan)


def set_predictor(predictor) -> None:
    global _predictor
    _predictor = predictor


def set_anomaly_detector(detector) -> None:
    global _anomaly_detector
    _anomaly_detector = detector


def set_case_narrator(narrator) -> None:
    global _case_narrator
    _case_narrator = narrator


def set_case_retriever(retriever) -> None:
    global _case_retriever
    _case_retriever = retriever


def set_copilot_client(client) -> None:
    global _copilot_client
    _copilot_client = client


# Getter functions (called from routers)


def get_predictor():
    return _predictor


def get_anomaly_detector() -> Any:
    return _anomaly_detector


def get_case_narrator():
    return _case_narrator


def get_case_retriever() -> Any:
    return _case_retriever


def get_copilot_client() -> Any:
    return _copilot_client
