# FraudLens — Folder Structure

```
Credit Card Fraud Detection/
├── run_pipeline.py               # CLI: end-to-end training pipeline
├── train_and_compare.py          # CLI: model comparison harness
├── requirements.txt              # Dependency manifest
├── Makefile                      # Task runner
├── alembic.ini                   # Alembic configuration
├── Dockerfile                    # Container build
├── docker-compose.yml            # Container orchestration
├── .env.example                  # Env-var template
├── .pre-commit-config.yaml       # Git hooks
├── LICENSE                       # License
├── README.md                     # Project readme
├── PROJECT_ANALYSIS.md           # Historical analysis doc
├── PROJECT_OVERVIEW.md           # Project overview doc
│
├── src/fraudlens/                # Core ML package (src-layout)
│   ├── __init__.py
│   ├── config.py                 # Pydantic settings
│   ├── common/                   # enums
│   ├── analysis/                 # eda.py
│   ├── data/                     # download, loaders, preprocessing
│   ├── features/                 # engineering
│   ├── models/                   # anomaly, hpo, model_selection, train
│   ├── evaluation/               # metrics, business_cost
│   ├── explainability/           # shap_explainer, shap_utils
│   ├── llm/                      # case_narrator, rag_similar_cases, cost_tracker
│   ├── monitoring/               # drift
│   ├── persistence/              # database, models, repositories/*
│   ├── prediction/               # model_loader
│   └── retraining/               # retrain_trigger
│
├── api/                          # FastAPI service layer
│   ├── main.py                   # App factory
│   ├── auth.py                   # API-key auth
│   ├── rate_limit.py             # Rate limiting
│   ├── routers/                  # predict, explain, chat, similar_cases, admin, models_admin
│   ├── schemas.py                # Pydantic DTOs
│   ├── errors.py / exceptions.py # Error handling
│   ├── logging_config.py / tracing.py / metrics.py / state.py
│   └── providers.py
│
├── app/                          # Streamlit dashboard
│   ├── streamlit_app.py          # Entry
│   ├── api_client.py             # API client
│   ├── pages/                    # analyst_copilot, case_investigator, live_monitor,
│   │                             #   model_governance, model_performance
│   └── components/               # metric_cards
│
├── tests/                        # 26 pytest files (~450 tests)
│   ├── conftest.py
│   └── load/                     # locust load-test script
│
├── alembic/                      # DB migrations
├── infra/                        # Deployment manifests
├── scripts/                      # Operational scripts
├── notebooks/                    # Analysis notebooks
├── docs/                         # Full documentation suite
│   ├── project/                  # analysis_report.md (this pass), plans, tracker
│   ├── community/ decisions/ design/ product/ reference/ technical/
├── data/                         # DVC-tracked dataset pointers
├── models/                       # Model checksums (.sha256)
├── reports/                      # Generated reports
└── Dataset/                      # (untracked, gitignored) raw dataset
```

## Root Hygiene

- Root contains only entry points, manifests, config, and top-level directories — consistent with the v5.0 target architecture.
- `AGENTS_FIX.md` (AI-scaffolding duplicate) **removed** in this pass.
- `fraudlens.db` (runtime SQLite) **untracked** — regenerated at runtime, already gitignored.
