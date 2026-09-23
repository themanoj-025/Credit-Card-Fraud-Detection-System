"""
FraudLens — Centralized Configuration (env-driven)

All configurable values live here as a pydantic BaseSettings class.
Loads from environment variables with sensible defaults.
No hardcoded constants remain — everything is configurable via .env or env vars.

Pydantic v2 (pydantic-settings 2.x): BaseSettings comes from pydantic_settings,
config is declared via SettingsConfigDict, and env vars map to field names.
CROSS_VALIDATION_* keeps its historical CV_FOLDS/CV_SCORING aliases for
backward compatibility.

Usage:
    from src.fraudlens.config import settings
    models_dir = settings.MODELS_DIR

    # Feature flags
    if settings.FEATURE_LLM_NARRATOR:
        narrate(case)

    # Module-level constants (backward-compatible aliases)
    from src.fraudlens.config import ALL_FEATURES, MODELS_DIR
"""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """FraudLens application settings, loaded from environment variables.

    All values have sensible defaults. Override via .env file or
    environment variables. See .env.example for documentation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # ════════════════════════════════════════════════════════════════
    # Paths (computed via @property below)
    # ════════════════════════════════════════════════════════════════
    PROJECT_ROOT: Path = Field(
        default=Path(__file__).resolve().parent.parent.parent,
        description="Root directory of the project",
    )

    @property
    def DATA_DIR(self) -> Path:
        return self.PROJECT_ROOT / "data"

    @property
    def RAW_DATA_DIR(self) -> Path:
        return self.PROJECT_ROOT / "data" / "raw"

    @property
    def PROCESSED_DATA_DIR(self) -> Path:
        return self.PROJECT_ROOT / "data" / "processed"

    @property
    def MODELS_DIR(self) -> Path:
        return self.PROJECT_ROOT / "models"

    @property
    def REPORTS_DIR(self) -> Path:
        return self.PROJECT_ROOT / "reports"

    @property
    def FIGURES_DIR(self) -> Path:
        return self.PROJECT_ROOT / "reports" / "figures"

    @property
    def NOTEBOOKS_DIR(self) -> Path:
        return self.PROJECT_ROOT / "notebooks"

    @property
    def DEFAULT_DATA_PATH(self) -> Path:
        return self.PROJECT_ROOT / "data" / "raw" / "creditcard.csv"

    @property
    def ALL_FEATURES(self) -> list[str]:
        return self.PCA_FEATURES + self.SCALE_FEATURES

    # ════════════════════════════════════════════════════════════════
    # Business Cost Assumptions
    # ════════════════════════════════════════════════════════════════
    AVG_FRAUD_LOSS: float = Field(
        150.0,
        description="Average dollar loss per missed fraud transaction",
    )
    REVIEW_COST: float = Field(
        5.0,
        description="Cost to manually review a flagged transaction",
    )

    # ════════════════════════════════════════════════════════════════
    # Data Split
    # ════════════════════════════════════════════════════════════════
    TEST_SIZE: float = Field(0.2)
    VAL_SIZE: float = Field(0.1)
    RANDOM_STATE: int = Field(42)

    # ════════════════════════════════════════════════════════════════
    # Features
    # ════════════════════════════════════════════════════════════════
    PCA_FEATURES: list[str] = [f"V{i}" for i in range(1, 29)]
    SCALE_FEATURES: list[str] = ["Time", "Amount"]
    TARGET_COLUMN: str = Field("Class")

    # ════════════════════════════════════════════════════════════════
    # Resampling
    # ════════════════════════════════════════════════════════════════
    RESAMPLING_STRATEGIES: list[str] = Field(
        ["none", "class_weight", "random_under", "smote", "adasyn", "smote_tomek"],
    )
    DEFAULT_RESAMPLING: str = Field("smote")

    # ════════════════════════════════════════════════════════════════
    # Model Training
    # ════════════════════════════════════════════════════════════════
    DEFAULT_MODELS: list[str] = Field(
        [
            "logistic_regression",
            "random_forest",
            "gradient_boosting",
            "xgboost",
            "lightgbm",
            "catboost",
        ],
    )
    MODEL_SELECTION_METRIC: str = Field("pr_auc")
    SELECTION_RULE_DESCRIPTION: str = (
        "Model with highest PR-AUC is selected as best. "
        "PR-AUC is preferred over ROC-AUC for imbalanced fraud data."
    )

    # Isolation Forest
    IFOREST_CONTAMINATION: float = Field(0.01)
    IFOREST_N_ESTIMATORS: int = Field(200)

    # CatBoost
    CATBOOST_VERBOSE: bool = Field(False)
    CATBOOST_ITERATIONS: int = Field(200)
    CATBOOST_DEPTH: int = Field(6)

    # ════════════════════════════════════════════════════════════════
    # Threshold Tuning
    # ════════════════════════════════════════════════════════════════
    N_THRESHOLDS: int = Field(100)

    # ════════════════════════════════════════════════════════════════
    # SHAP
    # ════════════════════════════════════════════════════════════════
    MAX_SHAP_FEATURES: int = Field(10)
    N_SHAP_BACKGROUND_SAMPLES: int = Field(100)

    # ════════════════════════════════════════════════════════════════
    # LLM / Copilot
    # ════════════════════════════════════════════════════════════════
    LLM_MODEL: str = Field("claude-sonnet-4-20250514")
    LLM_MAX_TOKENS: int = Field(1000)
    LLM_TEMPERATURE: float = Field(0.3)

    # RAG
    RAG_TOP_K: int = Field(3)
    EMBEDDING_DIM: int = Field(30)
    RAG_USE_PROJECTION: bool = Field(
        False,
        description="Apply learned PCA projection before FAISS indexing",
    )
    RAG_PROJECTION_COMPONENTS: int = Field(
        20,
        description="Target dimension for projected RAG embeddings",
    )

    # ════════════════════════════════════════════════════════════════
    # Drift Detection
    # ════════════════════════════════════════════════════════════════
    DRIFT_THRESHOLD: float = Field(0.05)
    DRIFT_ALERT_WINDOW: int = Field(1000)

    # ════════════════════════════════════════════════════════════════
    # Dashboard
    # ════════════════════════════════════════════════════════════════
    DASHBOARD_REFRESH_MS: int = Field(500)
    MAX_TRANSACTION_HISTORY: int = Field(500)
    SIMULATION_FRAUD_RATE: float = Field(0.02)
    SIMULATION_BATCH_SIZE: int = Field(10)

    # ════════════════════════════════════════════════════════════════
    # API
    # ════════════════════════════════════════════════════════════════
    API_URL: str = Field("http://localhost:8000")
    API_PORT: int = Field(8000)
    DASHBOARD_PORT: int = Field(8501)

    # ════════════════════════════════════════════════════════════════
    # Evaluation
    # ════════════════════════════════════════════════════════════════
    CROSS_VALIDATION_FOLDS: int = Field(
        5,
        validation_alias=AliasChoices("CROSS_VALIDATION_FOLDS", "CV_FOLDS"),
    )
    CROSS_VALIDATION_SCORING: str = Field(
        "average_precision",
        validation_alias=AliasChoices("CROSS_VALIDATION_SCORING", "CV_SCORING"),
    )

    # ════════════════════════════════════════════════════════════════
    # MLflow
    # ════════════════════════════════════════════════════════════════
    MLFLOW_EXPERIMENT_NAME: str = Field("fraudlens_model_comparison")
    MLFLOW_TRACKING_URI: str = Field("http://localhost:5000")
    MLFLOW_ARTIFACT_DIR: str = Field("mlruns")

    # ════════════════════════════════════════════════════════════════
    # Hyperparameter Optimization (Optuna)
    # ════════════════════════════════════════════════════════════════
    HPO_ENABLED: bool = Field(True)
    HPO_N_TRIALS: int = Field(30)
    HPO_CV_FOLDS: int = Field(3)
    HPO_MODELS: list[str] = Field(["xgboost", "lightgbm"])

    # ════════════════════════════════════════════════════════════════
    # Automated Retraining
    # ════════════════════════════════════════════════════════════════
    RETRAINING_ENABLED: bool = Field(
        True,
        description="Enable automated retraining trigger checks",
    )
    RETRAINING_FEEDBACK_THRESHOLD: int = Field(
        100,
        description="Min new confirmed feedback labels to trigger retraining",
    )
    RETRAINING_DRIFT_CRITICAL_THRESHOLD: int = Field(
        3,
        description="Min CRITICAL drift events to trigger retraining",
    )
    RETRAINING_DRIFT_WINDOW_DAYS: int = Field(
        7,
        description="Lookback window for drift events (days)",
    )

    # ════════════════════════════════════════════════════════════════
    # Feature Flags
    # ════════════════════════════════════════════════════════════════
    FEATURE_LLM_NARRATOR: bool = Field(
        True,
        description="Enable LLM-powered case narration for /v1/explain",
    )
    FEATURE_ANOMALY_SCORE: bool = Field(
        True,
        description="Include Isolation Forest anomaly score in predictions",
    )
    FEATURE_SHAP_EXPLANATION: bool = Field(
        True,
        description="Enable SHAP computation on the prediction path",
    )
    FEATURE_CACHE_PREDICTIONS: bool = Field(
        True,
        description="Enable LRU cache for duplicate predictions",
    )
    FEATURE_RAG_RETRIEVAL: bool = Field(
        True,
        description="Enable RAG-based similar case retrieval",
    )

    # ════════════════════════════════════════════════════════════════
    # Prediction threshold (runtime override)
    # ════════════════════════════════════════════════════════════════
    PREDICTION_THRESHOLD: float | None = Field(
        None,
        description="Override the model's optimal threshold. Null = use model default.",
    )


# Singleton Instance
# All modules should import from this instance for runtime config.
# Module-level aliases below provide backward compatibility.

settings = Settings()

# Backward-Compatible Module-Level Constants
# These aliases let existing imports continue to work unchanged.
# New code should prefer `from src.fraudlens.config import settings`.

# Paths
PROJECT_ROOT = settings.PROJECT_ROOT
DATA_DIR = settings.DATA_DIR
RAW_DATA_DIR = settings.RAW_DATA_DIR
PROCESSED_DATA_DIR = settings.PROCESSED_DATA_DIR
MODELS_DIR = settings.MODELS_DIR
REPORTS_DIR = settings.REPORTS_DIR
FIGURES_DIR = settings.FIGURES_DIR
NOTEBOOKS_DIR = settings.NOTEBOOKS_DIR
DEFAULT_DATA_PATH = settings.DEFAULT_DATA_PATH

# Business costs
AVG_FRAUD_LOSS = settings.AVG_FRAUD_LOSS
REVIEW_COST = settings.REVIEW_COST

# Data split
TEST_SIZE = settings.TEST_SIZE
VAL_SIZE = settings.VAL_SIZE
RANDOM_STATE = settings.RANDOM_STATE

# Features
PCA_FEATURES = settings.PCA_FEATURES
SCALE_FEATURES = settings.SCALE_FEATURES
ALL_FEATURES = settings.PCA_FEATURES + settings.SCALE_FEATURES
TARGET_COLUMN = settings.TARGET_COLUMN

# Resampling
RESAMPLING_STRATEGIES = settings.RESAMPLING_STRATEGIES
DEFAULT_RESAMPLING = settings.DEFAULT_RESAMPLING

# Model training
DEFAULT_MODELS = settings.DEFAULT_MODELS
MODEL_SELECTION_METRIC = settings.MODEL_SELECTION_METRIC
SELECTION_RULE_DESCRIPTION = settings.SELECTION_RULE_DESCRIPTION
IFOREST_CONTAMINATION = settings.IFOREST_CONTAMINATION
IFOREST_N_ESTIMATORS = settings.IFOREST_N_ESTIMATORS

CATBOOST_VERBOSE = settings.CATBOOST_VERBOSE
CATBOOST_ITERATIONS = settings.CATBOOST_ITERATIONS
CATBOOST_DEPTH = settings.CATBOOST_DEPTH

# Threshold
N_THRESHOLDS = settings.N_THRESHOLDS

# SHAP
MAX_SHAP_FEATURES = settings.MAX_SHAP_FEATURES
N_SHAP_BACKGROUND_SAMPLES = settings.N_SHAP_BACKGROUND_SAMPLES

# LLM
LLM_MODEL = settings.LLM_MODEL
LLM_MAX_TOKENS = settings.LLM_MAX_TOKENS
LLM_TEMPERATURE = settings.LLM_TEMPERATURE
RAG_TOP_K = settings.RAG_TOP_K
EMBEDDING_DIM = settings.EMBEDDING_DIM
RAG_USE_PROJECTION = settings.RAG_USE_PROJECTION
RAG_PROJECTION_COMPONENTS = settings.RAG_PROJECTION_COMPONENTS

# Drift
DRIFT_THRESHOLD = settings.DRIFT_THRESHOLD
DRIFT_ALERT_WINDOW = settings.DRIFT_ALERT_WINDOW

# Dashboard
DASHBOARD_REFRESH_MS = settings.DASHBOARD_REFRESH_MS
MAX_TRANSACTION_HISTORY = settings.MAX_TRANSACTION_HISTORY
SIMULATION_FRAUD_RATE = settings.SIMULATION_FRAUD_RATE
SIMULATION_BATCH_SIZE = settings.SIMULATION_BATCH_SIZE

# API
API_URL = settings.API_URL
API_PORT = settings.API_PORT
DASHBOARD_PORT = settings.DASHBOARD_PORT

# Evaluation
CROSS_VALIDATION_FOLDS = settings.CROSS_VALIDATION_FOLDS
CROSS_VALIDATION_SCORING = settings.CROSS_VALIDATION_SCORING

# MLflow
MLFLOW_EXPERIMENT_NAME = settings.MLFLOW_EXPERIMENT_NAME
MLFLOW_TRACKING_URI = settings.MLFLOW_TRACKING_URI
MLFLOW_ARTIFACT_DIR = settings.MLFLOW_ARTIFACT_DIR

# Retraining
RETRAINING_ENABLED = settings.RETRAINING_ENABLED
RETRAINING_FEEDBACK_THRESHOLD = settings.RETRAINING_FEEDBACK_THRESHOLD
RETRAINING_DRIFT_CRITICAL_THRESHOLD = settings.RETRAINING_DRIFT_CRITICAL_THRESHOLD
RETRAINING_DRIFT_WINDOW_DAYS = settings.RETRAINING_DRIFT_WINDOW_DAYS

# HPO
HPO_ENABLED = settings.HPO_ENABLED
HPO_N_TRIALS = settings.HPO_N_TRIALS
HPO_CV_FOLDS = settings.HPO_CV_FOLDS
HPO_MODELS = settings.HPO_MODELS
