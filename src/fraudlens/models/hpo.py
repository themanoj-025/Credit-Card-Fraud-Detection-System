"""
FraudLens — Hyperparameter Optimization (Optuna)

Tunes XGBoost and LightGBM hyperparameters for maximum PR-AUC on
imbalanced fraud data. Stores best trials in MLflow.

Usage:
    from src.fraudlens.models.hpo import HyperparameterOptimizer

    optimizer = HyperparameterOptimizer(n_trials=50, cv_folds=3)
    best_params = optimizer.tune_xgboost(X_train, y_train)
    best_params = optimizer.tune_lightgbm(X_train, y_train)
"""

import logging
import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold

logger = logging.getLogger(__name__)

# Optional MLflow
try:
    import mlflow

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


class HyperparameterOptimizer:
    """
    Optuna-based hyperparameter optimization for fraud detection models.

    Optimizes for PR-AUC (average precision) which is the right metric
    for highly imbalanced fraud datasets (0.17% fraud rate).
    """

    def __init__(
        self,
        n_trials: int = 50,
        cv_folds: int = 3,
        random_state: int = 42,
        timeout_seconds: int | None = None,
    ) -> None:
        """
        Args:
            n_trials: Number of Optuna trials per model
            cv_folds: Number of cross-validation folds
            random_state: Random seed for reproducibility
            timeout_seconds: Optional timeout for the optimization
        """
        self.n_trials = n_trials
        self.cv_folds = cv_folds
        self.random_state = random_state
        self.timeout_seconds = timeout_seconds
        self.best_params: dict[str, Any] = {}
        self.best_score: float = 0.0
        self.study = None

    def _cv_score(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        model_class: Any,
        params: dict[str, Any],
    ) -> float:
        """
        Compute cross-validated PR-AUC for a given model configuration.

        Args:
            X: Features
            y: Labels
            model_class: sklearn-compatible model class
            params: Hyperparameters for the model

        Returns:
            Mean PR-AUC across CV folds
        """
        skf = StratifiedKFold(
            n_splits=self.cv_folds,
            shuffle=True,
            random_state=self.random_state,
        )
        scores = []
        for train_idx, val_idx in skf.split(X, y):
            X_t, X_v = X.iloc[train_idx], X.iloc[val_idx]
            y_t, y_v = y.iloc[train_idx], y.iloc[val_idx]

            model = model_class(**params)
            model.fit(X_t, y_t)
            y_proba = model.predict_proba(X_v)[:, 1]
            score = average_precision_score(y_v, y_proba)
            scores.append(score)

        return float(np.mean(scores))

    def _compute_scale_pos_weight(self, y: pd.Series) -> float:
        """Compute scale_pos_weight for XGBoost based on class imbalance."""
        n_neg = (y == 0).sum()
        n_pos = (y == 1).sum()
        return float(n_neg / n_pos) if n_pos > 0 else 1.0

    def tune_xgboost(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_trials: int | None = None,
    ) -> dict[str, Any] -> None:
        """
        Tune XGBoost hyperparameters using Optuna.

        Args:
            X: Training features
            y: Training labels
            n_trials: Override for number of trials

        Returns:
            Best hyperparameters dictionary
        """
        try:
            import optuna
        except ImportError:
            logger.warning("optuna not installed. Install with: pip install optuna")
            return {"n_estimators": 200, "max_depth": 6, "learning_rate": 0.1}

        from xgboost import XGBClassifier

        scale_pos_weight = self._compute_scale_pos_weight(y)

        def objective(trial: Any) -> float:
            """Optuna objective function for XGBoost."""
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
                "max_depth": trial.suggest_int("max_depth", 3, 12),
                "learning_rate": trial.suggest_float(
                    "learning_rate", 0.01, 0.3, log=True
                ),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "gamma": trial.suggest_float("gamma", 0.0, 5.0),
                "scale_pos_weight": scale_pos_weight,
                "random_state": self.random_state,
                "eval_metric": "aucpr",
                "use_label_encoder": False,
                "n_jobs": -1,
            }
            return self._cv_score(X, y, XGBClassifier, params)

        logger.info(
            "Starting XGBoost hyperparameter optimization (%d trials)...",
            n_trials or self.n_trials,
        )
        start_time = time.time()

        study = optuna.create_study(
            direction="maximize",
            study_name="xgboost_hpo",
            sampler=optuna.samplers.TPESampler(seed=self.random_state),
        )
        study.optimize(
            objective,
            n_trials=n_trials or self.n_trials,
            timeout=self.timeout_seconds,
            show_progress_bar=False,
        )

        elapsed = time.time() - start_time
        self.best_params = study.best_params
        self.best_score = study.best_value
        self.study = study

        # Add fixed params
        self.best_params["scale_pos_weight"] = scale_pos_weight
        self.best_params["random_state"] = self.random_state
        self.best_params["eval_metric"] = "aucpr"
        self.best_params["use_label_encoder"] = False
        self.best_params["n_jobs"] = -1

        logger.info(
            "XGBoost HPO complete: best PR-AUC = %.4f (%d trials in %.1fs)",
            self.best_score,
            n_trials or self.n_trials,
            elapsed,
        )

        # Log to MLflow
        self._log_hpo_to_mlflow("xgboost", study, elapsed)

        return self.best_params

    def tune_lightgbm(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_trials: int | None = None,
    ) -> dict[str, Any] -> None:
        """
        Tune LightGBM hyperparameters using Optuna.

        Args:
            X: Training features
            y: Training labels
            n_trials: Override for number of trials

        Returns:
            Best hyperparameters dictionary
        """
        try:
            import optuna
        except ImportError:
            logger.warning("optuna not installed. Install with: pip install optuna")
            return {
                "n_estimators": 200,
                "max_depth": 6,
                "learning_rate": 0.1,
                "is_unbalance": True,
            }

        import lightgbm as lgb

        def objective(trial: Any) -> float:
            """Optuna objective function for LightGBM."""
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
                "max_depth": trial.suggest_int("max_depth", 3, 12),
                "learning_rate": trial.suggest_float(
                    "learning_rate", 0.01, 0.3, log=True
                ),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
                "num_leaves": trial.suggest_int("num_leaves", 15, 127),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
                "is_unbalance": True,
                "random_state": self.random_state,
                "verbose": -1,
                "n_jobs": -1,
            }
            return self._cv_score(X, y, lgb.LGBMClassifier, params)

        logger.info(
            "Starting LightGBM hyperparameter optimization (%d trials)...",
            n_trials or self.n_trials,
        )
        start_time = time.time()

        study = optuna.create_study(
            direction="maximize",
            study_name="lightgbm_hpo",
            sampler=optuna.samplers.TPESampler(seed=self.random_state),
        )
        study.optimize(
            objective,
            n_trials=n_trials or self.n_trials,
            timeout=self.timeout_seconds,
            show_progress_bar=False,
        )

        elapsed = time.time() - start_time
        self.best_params = study.best_params
        self.best_score = study.best_value
        self.study = study

        # Add fixed params
        self.best_params["is_unbalance"] = True
        self.best_params["random_state"] = self.random_state
        self.best_params["verbose"] = -1
        self.best_params["n_jobs"] = -1

        logger.info(
            "LightGBM HPO complete: best PR-AUC = %.4f (%d trials in %.1fs)",
            self.best_score,
            n_trials or self.n_trials,
            elapsed,
        )

        self._log_hpo_to_mlflow("lightgbm", study, elapsed)

        return self.best_params

    def tune_catboost(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_trials: int | None = None,
    ) -> dict[str, Any] -> None:
        """
        Tune CatBoost hyperparameters using Optuna (if CatBoost is installed).

        Args:
            X: Training features
            y: Training labels
            n_trials: Override for number of trials

        Returns:
            Best hyperparameters dictionary
        """
        try:
            import optuna
            from catboost import CatBoostClassifier
        except ImportError:
            logger.warning("CatBoost or optuna not installed. Skipping CatBoost HPO.")
            return {"iterations": 200, "depth": 6, "learning_rate": 0.1}

        def objective(trial: Any) -> float:
            """Optuna objective function for CatBoost."""
            params = {
                "iterations": trial.suggest_int("iterations", 100, 500, step=50),
                "depth": trial.suggest_int("depth", 4, 10),
                "learning_rate": trial.suggest_float(
                    "learning_rate", 0.01, 0.3, log=True
                ),
                "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
                "random_seed": self.random_state,
                "verbose": False,
                "auto_class_weights": "Balanced",
            }
            return self._cv_score(X, y, CatBoostClassifier, params)

        logger.info(
            "Starting CatBoost hyperparameter optimization (%d trials)...",
            n_trials or self.n_trials,
        )
        start_time = time.time()

        study = optuna.create_study(
            direction="maximize",
            study_name="catboost_hpo",
            sampler=optuna.samplers.TPESampler(seed=self.random_state),
        )
        study.optimize(
            objective,
            n_trials=n_trials or self.n_trials,
            timeout=self.timeout_seconds,
            show_progress_bar=False,
        )

        elapsed = time.time() - start_time
        self.best_params = study.best_params
        self.best_score = study.best_value
        self.study = study

        self.best_params["random_seed"] = self.random_state
        self.best_params["verbose"] = False
        self.best_params["auto_class_weights"] = "Balanced"

        logger.info(
            "CatBoost HPO complete: best PR-AUC = %.4f (%d trials in %.1fs)",
            self.best_score,
            n_trials or self.n_trials,
            elapsed,
        )

        self._log_hpo_to_mlflow("catboost", study, elapsed)

        return self.best_params

    def _log_hpo_to_mlflow(self, model_name: str, study: Any, elapsed: float) -> None:
        """Log HPO results to MLflow."""
        if not MLFLOW_AVAILABLE:
            return
        try:
            from src.fraudlens.config import MLFLOW_EXPERIMENT_NAME, MLFLOW_TRACKING_URI

            mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
            mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
            with mlflow.start_run(run_name=f"{model_name}_hpo"):
                mlflow.set_tag("hpo_model", model_name)
                mlflow.set_tag("hpo_trials", str(study.trials))
                mlflow.log_metric("best_pr_auc", study.best_value)
                mlflow.log_metric("hpo_duration_s", round(elapsed, 2))
                for k, v in study.best_params.items():
                    if isinstance(v, (int, float, str, bool)):
                        mlflow.log_param(f"best_{k}", v)
                # Log top-5 trials
                for i, trial in enumerate(study.best_trials[:5]):
                    mlflow.log_metric(f"trial_{i}_value", trial.value)
        except (RuntimeError, ValueError) as e:
            logger.warning("MLflow HPO logging failed: %s", e)

    def get_trials_dataframe(self) -> Any:
        """Get a DataFrame of all trials (requires optuna)."""
        if self.study is not None:
            try:
                return self.study.trials_dataframe()
            except (ImportError, ValueError):
                return None
        return None
