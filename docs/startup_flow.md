# FraudLens — Startup Flow

FraudLens ships FastAPI (`api/main.py`) and Streamlit (`app/streamlit_app.py`)
entry points over the `src.fraudlens` package (src-layout; `PYTHONPATH=src`
in Docker/CI). The root `Dockerfile` runs API + UI together; compose runs them
as services.

## FastAPI startup (`uvicorn api.main:app`)

1. Import phase — `api/main.py` imports `src.fraudlens.*`:
   - `fraudlens.config` (paths/constants)
   - `fraudlens.persistence.init_db` — creates SQLite schema on first run
   - `fraudlens.prediction.model_loader.ModelLoader` — loads artifacts from
     `models/` (verified against `.sha256` checksums)
   - `ShapExplainer`, `CaseNarrator`, `SimilarCaseRetriever` — heavy objects
     built once in `api/providers.py` and injected via `Depends()`.
2. App assembly — CORS, rate limiter (`api/rate_limit.py`, shared with the
   Streamlit client), auth (`api/auth.py`), logging/tracing
   (`api/logging_config.py`, `api/tracing.py`), metrics (`api/metrics.py`).
3. Router registration — predict, explain, similar_cases, chat, admin,
   models_admin (thin, delegating to providers/repositories).
4. Ready — `/health`, `/docs`, business endpoints; predictions logged to
   `fraudlens.db` via repositories.

## Streamlit startup (`streamlit run app/streamlit_app.py`)

1. `streamlit_app.py` builds the same facades (model loader, persistence,
   monitoring) via `app/api_client.py` (calls the FastAPI service) or
   direct `src.fraudlens.*` imports.
2. Multipage router registers `app/pages/`: live_monitor, case_investigator,
   analyst_copilot, model_performance, model_governance; theme from
   `app/assets/theme.css`.
3. Pages call `show()` lazily; shared metric cards from `app/components/`.

## Training pipeline (root entries)

1. `python run_pipeline.py` — data (download/load → preprocess) → features →
   train + model_selection → artifacts to `models/` → `reports/eda_summary.json`.
2. `python train_and_compare.py` — cross-model comparison (logistic, RF, GB,
   XGB, LightGBM, CatBoost, anomaly) with business-cost evaluation.
3. Models registered as candidates in `fraudlens.db` (migration 002); LLM
   calls tracked (migration 003).

## Operational entry points

| Entry | Command |
|---|---|
| API | `uvicorn api.main:app --reload` (Makefile) |
| UI | `streamlit run app/streamlit_app.py` |
| Pipeline | `python run_pipeline.py` |
| Compare | `python train_and_compare.py` |
| Migrate | `alembic upgrade head` |
| Tests | `python -m pytest tests/` |
| Data (DVC) | `dvc pull` (dataset not committed directly) |

## What must exist at startup

- Trained artifacts in `models/` (+ `.sha256` checksums)
- Env keys from `.env.example` (DB path, API keys, LLM keys)
- Migrations applied; `fraudlens.db` created by `init_db`
