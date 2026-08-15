# FraudLens — Architecture

> Textual architecture of the Credit Card Fraud Detection system (as-is; no behavior changes).

## System Overview

FraudLens is a layered, production-grade fraud-detection platform with four primary surfaces:

1. **CLI / Pipeline** — `run_pipeline.py` and `train_and_compare.py` drive data → feature → train → evaluate → register flows.
2. **API (FastAPI)** — REST endpoints for prediction, explanation, LLM case narration, similar-case RAG retrieval, admin and model governance. Protected by API-key auth and rate limiting.
3. **Dashboard (Streamlit)** — analyst copilot, case investigator, live monitor, model performance and governance pages; talks to the API via `app/api_client.py`.
4. **ML Core (`src/fraudlens`)** — data, features, models, evaluation, explainability, LLM, monitoring, persistence, prediction, retraining.

```mermaid
graph TD
    subgraph CLI
        RP[run_pipeline.py]
        TC[train_and_compare.py]
    end

    subgraph API[FastAPI api/]
        API_MAIN[main.py]
        ROUTERS[routers: predict, explain, chat,
                 similar_cases, admin, models_admin]
        AUTH[auth.py]
        RL[rate_limit.py]
    end

    subgraph DASH[Streamlit app/]
        SA[streamlit_app.py]
        PAGES[pages: analyst_copilot, case_investigator,
               live_monitor, model_governance, model_performance]
        CLI2[api_client.py]
    end

    subgraph CORE[src/fraudlens]
        DATA[data: download, loaders, preprocessing]
        FEAT[features: engineering]
        MODELS[models: anomaly, hpo, selection, train]
        EVAL[evaluation: metrics, business_cost]
        EXPL[explainability: shap]
        LLM[llm: case_narrator, rag_similar_cases, cost_tracker]
        MON[monitoring: drift]
        PERS[persistence: repositories]
        PRED[prediction: model_loader]
        RETR[retraining: retrain_trigger]
    end

    subgraph INFRA
        DB[(SQLite/Postgres via Alembic)]
        REDIS[(Redis / RQ)]
    end

    RP --> CORE
    TC --> CORE
    API_MAIN --> ROUTERS
    ROUTERS --> AUTH
    ROUTERS --> RL
    ROUTERS --> CORE
    SA --> PAGES
    PAGES --> CLI2
    CLI2 --> API_MAIN
    CORE --> PERS --> DB
    CORE --> MON --> REDIS
    MODELS --> EVAL
    EXPL --> PRED
    LLM --> EXPL
    RETR --> MODELS
```

## Layering Rules (as observed)

- **API layer** (`api/`) depends on `src/fraudlens/`; never the reverse.
- **Persistence** is isolated behind a repository pattern (`persistence/repositories/base.py` + typed repositories).
- **Dashboard** (`app/`) talks to the system only through the API client — no direct DB access.
- **LLM usage** is wrapped (`llm/case_narrator.py`) with a cost tracker to bound spend.
- **Configuration** is centralized in `src/fraudlens/config.py` (Pydantic settings) and API-level config in `api/state.py`.

## Data Flow (prediction path)

```
POST /predict ──► auth ──► rate_limit ──► router ──► model_loader ──► features.engineering
                                                          │
                                                          ▼
                                             model inference (XGBoost)
                                                          │
                              ┌───────────────────────────┼───────────────────────────┐
                              ▼                           ▼                           ▼
                     explainability (SHAP)        persistence (prediction repo)   drift monitoring
                              │
                              ▼
                     LLM case narrator + RAG similar cases (optional)
                              │
                              ▼
                        JSON response
```

## Deployment

- `Dockerfile` + `docker-compose.yml` + `infra/` for containerized deployment.
- `alembic` manages schema migrations.
- DVC tracks the raw dataset (`data/raw/creditcard.csv.dvc`); models are checksummed (`models/*.sha256`).
