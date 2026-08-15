# FraudLens (Credit Card Fraud Detection) — Module Dependency Map

## Core package (src/fraudlens) internal dependencies

```
fraudlens.config                 ← imported by every domain module (paths, constants)
fraudlens.data.loaders           ← used by features, prediction, retraining
fraudlens.data.preprocessing     ← used by features.engineering, models.train
fraudlens.data.download          ← leaf (Kaggle bootstrap)
fraudlens.persistence.database   ← used by persistence.repositories.*, api, app
fraudlens.persistence.models     ← ORM models; used by repositories
fraudlens.persistence.repositories.* ← used by api routers, monitoring, retraining
fraudlens.features.engineering   ← depends on data.* only
fraudlens.models.train           ← depends on features, data.preprocessing
fraudlens.models.model_selection ← depends on models.train, evaluation.metrics
fraudlens.models.hpo             ← Optuna tuning; used by model_selection
fraudlens.models.anomaly         ← isolation-forest anomaly detector (leaf-ish)
fraudlens.evaluation.metrics     ← depends on models (predictions)
fraudlens.evaluation.business_cost ← used by model_selection, reports
fraudlens.explainability.shap_explainer / shap_utils ← depend on models, data
fraudlens.llm.case_narrator      ← depends on llm.cost_tracker
fraudlens.llm.rag_similar_cases  ← depends on models (embedding index), persistence
fraudlens.monitoring.drift       ← depends on models, persistence
fraudlens.retraining.retrain_trigger ← depends on monitoring, models, persistence
fraudlens.prediction.model_loader ← loads artifacts from models/ (used by api + app)
fraudlens.analysis.eda           ← depends on data.loaders (report generation)
```

## Interface layer → core

```
api/main.py          → src.fraudlens.* (config, prediction, explainability, llm,
                       persistence, monitoring, retraining)
api/providers.py     → src.fraudlens.explainability, prediction (DI singletons)
api/routers/*        → api.main (providers via Depends), api.schemas,
                       src.fraudlens.persistence.repositories.*
app/streamlit_app.py → src.fraudlens.* (prediction, persistence, monitoring)
app/pages/*          → facades from streamlit_app
```

## Dependency rules (why)

- **`src.fraudlens.prediction.model_loader` is the only sanctioned artifact
  loader** — api/app never read `models/` files directly.
- **`data.*` and `features.*` never import models/llm** — feature engineering
  stays upstream of modeling.
- **Repositories are the only persistence touchpoint** — services and routers
  never write SQL directly.
- **No circular imports** — layers depend downward only; DI providers in
  `api/providers.py` centralize wiring.
- **Alembic env.py** imports `fraudlens.persistence.models` for autogenerate.

## Entry scripts (root, must stay)

`run_pipeline.py` (end-to-end train/eval) and `train_and_compare.py`
(model comparison) import `src.fraudlens.*`; Docker/CI reference them by path.

## External dependencies

FastAPI + uvicorn · Streamlit · SQLite (SQLAlchemy + Alembic) · scikit-learn /
XGBoost / LightGBM / CatBoost (models) · SHAP (explainability) · Optuna (HPO) ·
DVC (data versioning) · an LLM provider (case narrator) · Prometheus/Grafana +
k8s manifests (infra/)
