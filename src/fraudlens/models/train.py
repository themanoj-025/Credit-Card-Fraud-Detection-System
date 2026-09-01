"""
Training Module

Trains multiple fraud detection models for comparison and selection.
"""

import logging
import time
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from xgboost import XGBClassifier

from src.fraudlens.config import (
    CATBOOST_DEPTH,
    CATBOOST_ITERATIONS,
    CATBOOST_VERBOSE,
    CROSS_VALIDATION_FOLDS,
    CROSS_VALIDATION_SCORING,
    DEFAULT_MODELS,
    MLFLOW_EXPERIMENT_NAME,
    MODELS_DIR,
    RANDOM_STATE,
)

logger = logging.getLogger(__name__)

# MLflow setup
try:
    import mlflow

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.info("MLflow not installed. Experiment tracking disabled.")

logger = logging.getLogger(__name__)


class FraudTrainer:
    """
    Train and compare multiple fraud detection models.

    Now includes optional feature engineering via FeatureEngineer,
    ensuring train-time and inference-time features stay in sync.

    Models:
    - Logistic Regression (baseline, interpretable)
    - Random Forest (tree ensemble, robust)
    - Gradient Boosting (sklearn native, sequential trees)
    - XGBoost (optimized gradient boosting, top performer)
    - LightGBM (lightweight gradient boosting, fast)
    - CatBoost (categorical boosting, handles imbalance)
    """

    DEFAULT_CONFIGS: dict[str, dict] = {
        "logistic_regression": {
            "model_class": LogisticRegression,
            "params": {
                "max_iter": 1000,
                "random_state": RANDOM_STATE,
                "class_weight": "balanced",
                "solver": "lbfgs",
                "n_jobs": -1,
            },
            "uses_class_weight": True,
        },
        "random_forest": {
            "model_class": RandomForestClassifier,
            "params": {
                "n_estimators": 200,
                "max_depth": 10,
                "min_samples_split": 5,
                "min_samples_leaf": 2,
                "random_state": RANDOM_STATE,
                "class_weight": "balanced",
                "n_jobs": -1,
            },
            "uses_class_weight": True,
        },
        "gradient_boosting": {
            "model_class": GradientBoostingClassifier,
            "params": {
                "n_estimators": 200,
                "max_depth": 4,
                "learning_rate": 0.1,
                "min_samples_split": 5,
                "min_samples_leaf": 2,
                "random_state": RANDOM_STATE,
            },
            "uses_class_weight": False,
        },
        "xgboost": {
            "model_class": XGBClassifier,
            "params": {
                "n_estimators": 200,
                "max_depth": 6,
                "learning_rate": 0.1,
                "scale_pos_weight": 1,
                "random_state": RANDOM_STATE,
                "eval_metric": "aucpr",
                "use_label_encoder": False,
                "n_jobs": -1,
            },
            "uses_class_weight": False,
        },
        "lightgbm": {
            "model_class": lgb.LGBMClassifier,
            "params": {
                "n_estimators": 200,
                "max_depth": 6,
                "learning_rate": 0.1,
                "is_unbalance": True,
                "random_state": RANDOM_STATE,
                "verbose": -1,
                "n_jobs": -1,
            },
            "uses_class_weight": False,
        },
        "catboost": {
            "model_class": None,  # Set dynamically in __init__
            "params": {
                "iterations": CATBOOST_ITERATIONS,
                "depth": CATBOOST_DEPTH,
                "learning_rate": 0.1,
                "random_seed": RANDOM_STATE,
                "verbose": CATBOOST_VERBOSE,
                "auto_class_weights": "Balanced",
            },
            "uses_class_weight": False,
        },
    }

    def __init__(
        self,
        models_to_train: list[str] | None = None,
        custom_configs: dict | None = None,
        use_feature_engineering: bool = False,
    ) -> None:
        """
        Initialize the trainer.

        Args:
            models_to_train: List of model names to train (default from config)
            custom_configs: Custom model configurations to override defaults
            use_feature_engineering: Whether to apply FeatureEngineer before training.
                When True, the trainer stores the fitted engineer for inference-time use,
                ensuring train/serve feature parity.
        """
        self.configs = {**self.DEFAULT_CONFIGS}
        if custom_configs:
            # Deep-merge custom configs into defaults to preserve model_class,
            # uses_class_weight, and other keys from DEFAULT_CONFIGS
            for name, cfg in custom_configs.items():
                if name in self.configs:
                    self.configs[name].update(cfg)
                else:
                    self.configs[name] = cfg

        # Try to load CatBoost — graceful fallback if not installed
        try:
            from catboost import CatBoostClassifier

            self.configs["catboost"]["model_class"] = CatBoostClassifier
        except ImportError:
            logger.info("CatBoost not installed. Removing from configs.")
            if "catboost" in self.configs:
                del self.configs["catboost"]

        self.models_to_train = [
            m for m in (models_to_train or DEFAULT_MODELS) if m in self.configs
        ]
        self.trained_models: dict[str, Any] = {}
        self.training_results: dict[str, dict] = {}
        self.use_feature_engineering = use_feature_engineering
        self.feature_engineer: Any | None = None

    def _apply_feature_engineering(self, X: pd.DataFrame) -> pd.DataFrame:
        """Apply feature engineering if enabled, caching the engineer for inference.

        This is the golden test point: training-time and inference-time feature
        vectors must have identical shape/order to prevent train/serve skew.

        Args:
            X: Input features

        Returns:
            Transformed features with engineered columns
        """
        if not self.use_feature_engineering:
            return X

        from src.fraudlens.features.engineering import FeatureEngineer

        self.feature_engineer = FeatureEngineer(
            create_interactions=True, create_bins=True
        )
        X_eng = self.feature_engineer.transform(X)
        logger.info(
            "Feature engineering applied: %d → %d features",
            X.shape[1],
            X_eng.shape[1],
        )
        return X_eng

    def get_engineered_feature_names(self) -> list[str] | None:
        """Get feature names after engineering (for inference parity)."""
        if self.feature_engineer is not None:
            return self.feature_engineer.get_feature_names()
        return None

    def _compute_scale_pos_weight(self, y: pd.Series) -> float:
        """Compute scale_pos_weight for XGBoost based on class imbalance."""
        n_neg = (y == 0).sum()
        n_pos = (y == 1).sum()
        return n_neg / n_pos if n_pos > 0 else 1.0

    def _log_to_mlflow(self, name: str, params: dict, train_time: float, model) -> None:
        """Log model training run to MLflow if available."""
        if not MLFLOW_AVAILABLE:
            return
        try:
            mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
            with mlflow.start_run(run_name=name) as run:
                # Set custom tags for reliable lookup by model_selection.py
                mlflow.set_tag("run_name", name)
                mlflow.set_tag("model_name", name)

                # Log hyperparameters
                for k, v in params.items():
                    if isinstance(v, (int, float, str, bool)):
                        mlflow.log_param(k, v)

                # Log training metadata
                mlflow.log_param("model_name", name)
                n_samples = (
                    len(self.training_results.get(name, {}).get("n_samples", 0))
                    if name in self.training_results
                    else 0
                )
                n_features = (
                    len(self.training_results.get(name, {}).get("n_features", 0))
                    if name in self.training_results
                    else 0
                )
                mlflow.log_param("n_samples", n_samples)
                mlflow.log_param("n_features", n_features)
                mlflow.log_metric("train_time_s", round(train_time, 2))

                # Log the model artifact
                try:
                    mlflow.sklearn.log_model(model, artifact_path="model")
                except (OSError, ImportError, ValueError):
                    import tempfile

                    import joblib

                    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
                        joblib.dump(model, f.name)
                        mlflow.log_artifact(f.name, artifact_path="model")

                logger.info(
                    "  MLflow run logged: %s (tagged as %s)", run.info.run_id, name
                )
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning("  MLflow logging failed for %s: %s", name, e)

    def _log_cv_to_mlflow(self, name: str, cv_results: dict) -> None:
        """Log cross-validation results to MLflow."""
        if not MLFLOW_AVAILABLE:
            return
        try:
            mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
            with mlflow.start_run(run_name=f"{name}_cv") as _run:
                mlflow.log_param("model_name", name)
                mlflow.log_param("type", "cross_validation")
                mlflow.log_metric("cv_mean_score", cv_results["mean_score"])
                mlflow.log_metric("cv_std_score", cv_results["std_score"])
                for i, s in enumerate(cv_results["scores"]):
                    mlflow.log_metric(f"cv_fold_{i + 1}_score", s)
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning("  MLflow CV logging failed for %s: %s", name, e)

    def train_model(self, name: str, X_train: pd.DataFrame, y_train: pd.Series) -> Any:
        """
        Train a single model.

        Args:
            name: Model name
            X_train: Training features
            y_train: Training labels

        Returns:
            Trained model
        """
        config = self.configs[name]
        params = config["params"].copy()

        if name == "xgboost":
            params["scale_pos_weight"] = self._compute_scale_pos_weight(y_train)

        logger.info("Training %s...", name)
        start_time = time.time()

        model = config["model_class"](**params)
        model.fit(X_train, y_train)

        train_time = time.time() - start_time
        logger.info("  %s trained in %.2fs", name, train_time)

        self.trained_models[name] = model
        self.training_results[name] = {
            "train_time": train_time,
            "n_samples": len(X_train),
            "n_features": X_train.shape[1],
        }

        # Log to MLflow (AFTER training_results is populated)
        self._log_to_mlflow(name, params, train_time, model)

        return model

    def train_all(self, X_train: pd.DataFrame, y_train: pd.Series) -> dict[str, Any]:
        """
        Train all configured models.

        Applies feature engineering before training if enabled.

        Args:
            X_train: Training features
            y_train: Training labels

        Returns:
            Dictionary of trained models
        """
        # Apply feature engineering before training
        X_train_eng = self._apply_feature_engineering(X_train)

        logger.info("Training %d models...", len(self.models_to_train))
        for name in self.models_to_train:
            self.train_model(name, X_train_eng, y_train)
        logger.info("All models trained: %s", list(self.trained_models.keys()))
        return self.trained_models

    def save_model(self, name: str, path: str | None = None) -> str:
        """
        Save a trained model to disk.

        Args:
            name: Model name
            path: Save path (default: models/{name}.pkl)

        Returns:
            Path where model was saved
        """
        if name not in self.trained_models:
            raise ValueError(f"Model '{name}' not found in trained models.")

        if path is None:
            path = str(MODELS_DIR / f"{name}.pkl")

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.trained_models[name], path)
        logger.info("Model '%s' saved to %s", name, path)
        return path

    def save_all_models(self, directory: str = "models") -> list[str]:
        """Save all trained models to a directory."""
        return [
            self.save_model(name, f"{directory}/{name}.pkl")
            for name in self.trained_models
        ]

    def load_model(self, name: str, path: str | None = None) -> Any:
        """Load a trained model from disk."""
        if path is None:
            path = str(MODELS_DIR / f"{name}.pkl")
        model = joblib.load(path)
        self.trained_models[name] = model
        logger.info("Model '%s' loaded from %s", name, path)
        return model

    def cross_validate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        cv: int = CROSS_VALIDATION_FOLDS,
        scoring: str = CROSS_VALIDATION_SCORING,
    ) -> dict[str, dict] -> None:
        """
        Cross-validate all models.

        Args:
            X: Training features
            y: Training labels
            cv: Number of CV folds
            scoring: Scoring metric

        Returns:
            Dictionary with CV results for each model
        """
        results = {}
        for name in self.models_to_train:
            config = self.configs[name]
            params = config["params"].copy()

            if name == "xgboost":
                params["scale_pos_weight"] = self._compute_scale_pos_weight(y)

            model = config["model_class"](**params)
            skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=RANDOM_STATE)
            scores = cross_val_score(model, X, y, cv=skf, scoring=scoring)

            cv_result = {
                "mean_score": round(float(scores.mean()), 4),
                "std_score": round(float(scores.std()), 4),
                "scores": [round(float(s), 4) for s in scores],
            }
            results[name] = cv_result
            logger.info("  %s: %.4f ± %.4f", name, scores.mean(), scores.std())

            # Log CV results to MLflow
            self._log_cv_to_mlflow(name, cv_result)

        return results
