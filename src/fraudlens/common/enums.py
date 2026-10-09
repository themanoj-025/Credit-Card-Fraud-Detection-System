"""
FraudLens — Shared Enumerations

Central enum definitions to eliminate magic strings scattered across
the codebase. Import these instead of hardcoding string literals.
"""

from enum import Enum


class Decision(str, Enum):
    """Fraud classification decision."""

    FRAUD = "FRAUD"
    LEGITIMATE = "LEGITIMATE"


class DecisionAction(str, Enum):
    """Recommended action based on fraud decision."""

    FLAG_FOR_REVIEW = "FLAG for manual review"
    AUTO_APPROVE = "AUTO-APPROVE"


class ShapImpact(str, Enum):
    """Direction of SHAP feature impact."""

    INCREASES = "increases"
    DECREASES = "decreases"


class SimilarCaseOutcome(str, Enum):
    """Outcome of a similar historical case."""

    CONFIRMED_FRAUD = "confirmed_fraud"
    FALSE_POSITIVE = "false_positive"


class DriftAlertLevel(str, Enum):
    """Severity level for drift alerts."""

    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ApiKeyRole(str, Enum):
    """API key access tiers."""

    ADMIN = "admin"
    READONLY = "readonly"


class ResamplingStrategy(str, Enum):
    """Available resampling strategies for handling class imbalance."""

    NONE = "none"
    CLASS_WEIGHT = "class_weight"
    RANDOM_UNDER = "random_under"
    SMOTE = "smote"
    ADASYN = "adasyn"
    SMOTE_TOMEK = "smote_tomek"


class ModelName(str, Enum):
    """Names of supported ML models."""

    LOGISTIC_REGRESSION = "logistic_regression"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    CATBOOST = "catboost"
    ISOLATION_FOREST = "Isolation Forest"
