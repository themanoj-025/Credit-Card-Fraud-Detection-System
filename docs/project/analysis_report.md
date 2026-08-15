# FraudLens — Repository Analysis Report (v5.0)

> Generated during the Ultra Master Repository Modernization pass.
> Scope: inventory, classification, duplicate/dead-code audit, and risk assessment.

## 1. Overview

| Attribute | Value |
|---|---|
| **Project** | FraudLens — Production-Grade Credit Card Fraud Detection with Explainability |
| **Stack** | Python 3.11+ (src-layout), FastAPI, SQLAlchemy + Alembic, XGBoost, SHAP, Streamlit, RQ/Redis, LLM (case narration + RAG) |
| **Entry points** | `run_pipeline.py` (CLI), `train_and_compare.py` (CLI), `api/main.py` (FastAPI app), `app/streamlit_app.py` (dashboard), `scripts/*` |
| **Package layout** | `src/fraudlens/` (src-layout), `api/`, `app/`, `tests/`, `infra/`, `docs/` |
| **Tests** | 26 files, ~450 tests, `pytest` + `ruff` |

## 2. Entry Points

| Path | Kind | Purpose |
|---|---|---|
| `run_pipeline.py` | CLI | End-to-end training pipeline runner (data → train → eval → register) |
| `train_and_compare.py` | CLI | Baseline-vs-candidate model comparison harness |
| `api/main.py` | ASGI | FastAPI application factory (auth, rate limiting, routers) |
| `app/streamlit_app.py` | GUI | Streamlit analytics dashboard (analyst copilot, live monitor, governance) |
| `alembic/env.py` | Migration | Alembic migration environment |

## 3. Module Inventory (top-level packages)

### `src/fraudlens/` — core package
| Module | Category | Purpose |
|---|---|---|
| `config.py` | Configuration | Pydantic settings, env-var driven |
| `common/enums.py` | Domain | Shared enums (model status, feedback types, etc.) |
| `analysis/eda.py` | Domain/analysis | Exploratory data analysis helpers |
| `data/download.py`, `data/loaders.py`, `data/preprocessing.py` | Data access | Dataset download (DVC), loaders, preprocessing |
| `features/engineering.py` | Domain | Feature engineering |
| `models/anomaly.py`, `models/hpo.py`, `models/model_selection.py`, `models/train.py` | Domain | Model zoo: anomaly, hyperparameter optimization, selection, training |
| `evaluation/business_cost.py`, `evaluation/metrics.py` | Domain | Business-cost-aware and standard metrics |
| `explainability/shap_explainer.py`, `explainability/shap_utils.py` | Domain | SHAP explainability |
| `llm/case_narrator.py`, `llm/cost_tracker.py`, `llm/rag_similar_cases.py` | Domain | LLM narratives, cost tracking, RAG case retrieval |
| `monitoring/drift.py` | Domain | Drift detection |
| `persistence/database.py`, `persistence/models.py`, `persistence/repositories/*` | Data access | SQLAlchemy models + repository pattern (base, api_keys, drift_events, feedback, llm_calls, model_candidates, predictions) |
| `prediction/model_loader.py` | Domain | Model loading/serving |
| `retraining/retrain_trigger.py` | Domain | Retraining trigger logic |

### `api/` — FastAPI interface layer
| Module | Category | Purpose |
|---|---|---|
| `main.py` | Entry/API | App factory |
| `auth.py`, `providers.py` | Cross-cutting | AuthN/Z, provider abstraction |
| `rate_limit.py` | Cross-cutting | Rate limiting |
| `routers/{predict,explain,chat,similar_cases,admin,models_admin}.py` | API | Route handlers |
| `schemas.py` | API | Pydantic request/response models |
| `errors.py`, `exceptions.py` | Cross-cutting | Error handling |
| `logging_config.py`, `tracing.py`, `metrics.py`, `state.py` | Cross-cutting | Observability and app state |

### `app/` — Streamlit presentation layer
| Module | Category | Purpose |
|---|---|---|
| `streamlit_app.py` | Entry/Presentation | Streamlit entry |
| `pages/{analyst_copilot,case_investigator,live_monitor,model_governance,model_performance}.py` | Presentation | Dashboard pages |
| `api_client.py` | API | Streamlit ↔ FastAPI client |
| `components/metric_cards.py` | Presentation | Reusable UI components |

### Infrastructure & tooling
| Path | Category | Purpose |
|---|---|---|
| `infra/` | Infrastructure | Deployment manifests / Docker orchestration |
| `alembic/`, `alembic.ini` | Data access | Migrations |
| `Dockerfile`, `docker-compose.yml` | Infrastructure | Container build & run |
| `.github/workflows/*` | Infrastructure | CI/CD |
| `scripts/` | Infrastructure | Operational scripts |
| `notebooks/` | Docs/Research | Analysis notebooks |
| `docs/` | Docs | Full documentation suite (community, decisions, design, product, project, reference, technical) |

## 4. Duplicate / Dead Code Audit

| Item | Verdict | Evidence |
|---|---|---|
| `AGENTS_FIX.md` (root) | **DELETE** | Leftover "ULTRA MASTER FIX PROMPT v7.0" AI-scaffolding file, present as a duplicate in 16 sibling repos; zero code/config references (only a `.dockerignore` exclusion, now removed) |
| `fraudlens.db` (root, tracked) | **UNTRACK** | Runtime SQLite database committed by mistake; already covered by `.gitignore` (`fraudlens.db`, line 47); regenerated at runtime; removed from index (kept on disk) |
| `api/errors.py` vs `api/exceptions.py` | **FLAG** | Two overlapping error modules; not provably redundant — left for human review |
| `Dataset/` (root, untracked) | **OK** | Ignored by `.gitignore` (`Dataset/`, line 36); not in git |
| Cache dirs (`.pytest_cache/`, `.ruff_cache/`, `.hypothesis/`, `__pycache__/`) | **OK** | All gitignored; not tracked |

## 5. Security / Quality Findings (flag-only)

- API uses API-key auth + rate limiting; secrets come from env (`.env.example` present). No hardcoded credentials found.
- LLM cost tracker present (guardrail against unbounded LLM spend). No action needed.
- No silent `except: pass` found via ruff pass.

## 6. Verification Summary (this pass)

| Check | Result |
|---|---|
| Per-file pytest (26 files) | **447 passed, 3 skipped, 0 failed** |
| Full-suite single-process run | Crashes in this environment (native dep incompatibility w/ Python 3.14.5); per-file runs all green — environmental, not code |
| `ruff check .` | Clean (exit 0) |
| Import check | `src.fraudlens` package imports OK |
| Git hygiene | Working tree clean after commit (modifications to `.dockerignore` + deletions staged) |

## 7. Needs Human Review

1. `api/errors.py` vs `api/exceptions.py` — candidate merge; not auto-resolved.
2. Whether `infra/` overlaps with `Dockerfile`/`docker-compose.yml` responsibilities — out of scope for this pass.
