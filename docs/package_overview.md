# FraudLens — Package & Module Inventory

## Installed package: `fraudlens` (src/fraudlens)

| Module | Responsibility |
|---|---|
| `config.py` | Paths, constants (AVG_FRAUD_LOSS, REVIEW_COST, MODELS_DIR) |
| `data/download.py` | Kaggle dataset bootstrap |
| `data/loaders.py` | Load raw + processed data |
| `data/preprocessing.py` | Scaling, encoding, train/test split |
| `features/engineering.py` | Feature construction |
| `models/train.py` | Model training (supervised + anomaly) |
| `models/model_selection.py` | Train-and-compare harness |
| `models/hpo.py` | Optuna hyperparameter optimization |
| `models/anomaly.py` | Isolation-forest anomaly detector |
| `evaluation/metrics.py` | Classification metrics |
| `evaluation/business_cost.py` | Cost-based evaluation (fraud loss vs review cost) |
| `explainability/shap_explainer.py` | SHAP explanations for predictions |
| `explainability/shap_utils.py` | SHAP helpers |
| `llm/case_narrator.py` | LLM narration of fraud cases |
| `llm/cost_tracker.py` | LLM cost accounting |
| `llm/rag_similar_cases.py` | RAG retrieval of similar historical cases |
| `monitoring/drift.py` | Data-drift detection |
| `retraining/retrain_trigger.py` | Retraining triggers |
| `prediction/model_loader.py` | Loads trained artifacts from `models/` |
| `persistence/database.py` | SQLite engine/session |
| `persistence/models.py` | ORM models |
| `persistence/repositories/` | `base`, `api_keys`, `drift_events`, `feedback`, `llm_calls`, `model_candidates`, `predictions` |
| `analysis/eda.py` | EDA report generation |

## Application packages

| Package | Responsibility |
|---|---|
| `api/` | FastAPI: `main.py` (factory + DI providers), `schemas.py`, `auth.py`, `errors.py`, `exceptions.py`, `logging_config.py`, `metrics.py`, `providers.py`, `rate_limit.py`, `state.py`, `tracing.py`, `routers/` (predict, explain, similar_cases, chat, admin, models_admin) |
| `app/` | Streamlit: `streamlit_app.py`, `pages/` (analyst_copilot, case_investigator, live_monitor, model_governance, model_performance), `components/metric_cards.py`, `api_client.py`, `assets/theme.css` |
| `tests/` | 27 modules: unit, integration, contract, load (`load/locustfile.py`), pipeline smoke |

## Non-package trees

| Path | Purpose |
|---|---|
| `notebooks/` | 4 EDA/preprocessing/modeling/explainability notebooks |
| `models/` | Trained artifacts (.pkl ×8 + scaler, threshold, sha256 checksums) |
| `reports/` | `eda_summary.json` |
| `infra/` | k8s manifests (kustomize), Grafana dashboards, Prometheus config |
| `alembic/` | 3 migrations (initial, model_candidates, llm_calls) |
| `scripts/` | `benchmark.py` |
| `.dvc/` | DVC config + cache (data versioning) |
| `Dataset/` | Source dataset (DVC-managed / not tracked directly) |
| `docs/` | Full suite (architecture, decisions, technical, migration/) |
| Root entries | `run_pipeline.py` (train pipeline), `train_and_compare.py` (comparison), `fraudlens.db` (runtime, untracked) |
