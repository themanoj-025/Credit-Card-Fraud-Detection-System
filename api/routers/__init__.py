"""FastAPI router modules for FraudLens."""

from . import admin, chat, explain, models_admin, predict, similar_cases

__all__ = ["admin", "chat", "explain", "models_admin", "predict", "similar_cases"]
