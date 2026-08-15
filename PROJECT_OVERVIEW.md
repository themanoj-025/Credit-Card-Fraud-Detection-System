# FraudLens — Credit Card Fraud Detection

> **Production-grade credit card fraud detection with SHAP explainability, LLM-powered case narratives, and RAG-based similar case retrieval.**

---

## Table of Contents

- [1. Title & Badges](#1-title--badges)
- [2. Executive Summary](#2-executive-summary)
- [3. Tech Stack & Core Technologies](#3-tech-stack--core-technologies)
- [4. High-Level Architecture](#4-high-level-architecture)
- [5. Complete Folder Structure Tree](#5-complete-folder-structure-tree)
- [6. Exhaustive File-by-File & Folder-by-Folder Breakdown](#6-exhaustive-file-by-file--folder-by-folder-breakdown)
- [7. Data Models & Schemas](#7-data-models--schemas)
- [8. API Surface](#8-api-surface)
- [9. Configuration & Environment Variables](#9-configuration--environment-variables)
- [10. Build, Run & Deployment Instructions](#10-build-run--deployment-instructions)
- [11. Data & Control Flow Walkthroughs](#11-data--control-flow-walkthroughs)
- [12. Dependency Graph Summary](#12-dependency-graph-summary)
- [13. Testing Strategy](#13-testing-strategy)
- [14. Known Issues, Technical Debt & Assumptions](#14-known-issues-technical-debt--assumptions)
- [15. Glossary](#15-glossary)
- [16. Changelog / Version History Summary](#16-changelog--version-history-summary)
- [17. Appendix](#17-appendix)
- [Security Notes](#security-notes)
- [Performance Considerations](#performance-considerations)
- [Suggested Onboarding Path](#suggested-onboarding-path)

---

## 1. Title & Badges

| | |
|---|---|
| **Project Name** | FraudLens |
| **Tagline** | Production-grade credit card fraud detection with explainability |
| **Version** | Not explicitly versioned |
| **License** | MIT |

![CI](https://img.shields.io/badge/CI-active-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Python](https://img.shields.io/badge/Python-3.10-blue)
![Coverage](https://img.shields.io/badge/coverage-78%25-yellowgreen)

---

## 2. Executive Summary

**FraudLens** is a comprehensive credit card fraud detection system designed for production use. It addresses the critical problem of identifying fraudulent transactions in real-time while providing full explainability for every prediction — a requirement in regulated financial environments.

The system implements **6 supervised models** (Logistic Regression, Random Forest, Gradient Boosting, XGBoost, LightGBM, CatBoost) and **1 unsupervised model** (Isolation Forest), training all candidates with k-fold cross-validation and automatically selecting the best performer based on **PR-AUC** (Precision-Recall Area Under Curve), the optimal metric for highly imbalanced fraud datasets.

**Key differentiators:**
- **SHAP Explainability:** Every prediction includes feature importance explanations that analysts can understand
- **LLM Case Narration:** Anthropic Claude generates plain-English summaries of fraud cases for analysts
- **RAG Similar Cases:** FAISS-powered retrieval of historical fraud precedents to assist investigation
- **Model Governance:** Human-in-the-loop review, compare, and promote/reject retrained model candidates
- **Automated Retraining:** Drift detection + feedback volume triggers retraining with MLflow tracking
- **Real-time Dashboard:** Streamlit UI with 5 pages: Live Monitor, Case Investigator, Model Performance, Model Governance, Analyst Copilot

**Target users:** Financial analysts, fraud investigators, ML engineers, and compliance officers at financial institutions.

**Why it exists:** Traditional fraud detection systems are black boxes. Regulators increasingly require explainability. FraudLens bridges the gap between high-performance ML and actionable transparency.

---

## 3. Tech Stack & Core Technologies

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Language** | Python | 3.10 | Core runtime |
| **ML Framework** | XGBoost | ≥1.7,<2.0 | Primary gradient boosting model |
| **ML Framework** | LightGBM | ≥3.3,<4.0 | Fast gradient boosting |
| **ML Framework** | CatBoost | — | Categorical boosting |
| **ML Framework** | scikit-learn | ≥1.2,<2.0 | LR, RF, preprocessing, metrics |
| **Imbalanced Learning** | imbalanced-learn | ≥0.10 | SMOTE, ADASYN resampling |
| **Explainability** | SHAP | ≥0.41 | Feature importance explanations |
| **LLM** | Anthropic Claude | — | Case narration, analyst copilot |
| **Vector Search** | FAISS | ≥1.7 | RAG similar-case retrieval |
| **API Framework** | FastAPI | ≥0.95 | REST API with async support |
| **Dashboard** | Streamlit | ≥1.22 | Interactive ML dashboard |
| **Database** | SQLAlchemy | ≥2.0 | ORM for predictions, cases |
| **Database** | PostgreSQL | — | Production database |
| **Database** | SQLite | — | Development fallback |
| **Caching** | Redis | ≥4.6 | Rate limiting, prediction cache |
| **Experiment Tracking** | MLflow | ≥2.3 | Model versioning, comparison |
| **HPO** | Optuna | ≥3.3 | Hyperparameter optimization |
| **Drift Detection** | Evidently | ≥0.3 | Data drift monitoring |
| **Observability** | structlog | ≥23.0 | Structured JSON logging |
| **Observability** | Prometheus | ≥6.0 | Metrics collection |
| **Observability** | OpenTelemetry | ≥1.22 | Distributed tracing (Jaeger) |
| **Testing** | pytest | ≥7.3 | Unit + integration tests |
| **Load Testing** | Locust | ≥2.20 | API load testing |
| **Code Quality** | Ruff | ≥0.0.276 | Linting |
| **Code Quality** | Black | ≥23.0 | Formatting |
| **Containerization** | Docker | — | Multi-stage builds |
| **CI/CD** | GitHub Actions | — | Automated pipeline |

---

## 4. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Dashboard (:8501)                 │
│  Live Monitor │ Case Investigator │ Model Performance │ ...     │
└───────────────┬─────────────────────────────────────────────────┘
                │ HTTP
┌───────────────▼─────────────────────────────────────────────────┐
│                  FastAPI Server (:8000)                          │
│  /predict  → XGBoost Model                                     │
│  /explain  → SHAP Explainer                                    │
│  /chat     → Anthropic Claude LLM                              │
│  /similar  → FAISS Vector Store                                │
│  /feedback → Human-in-the-loop                                 │
│  /drift    → Evidently Drift Detection                         │
└───────┬──────────┬──────────┬──────────┬────────────────────────┘
        │          │          │          │
   ┌────▼───┐ ┌───▼────┐ ┌──▼───┐ ┌───▼────┐
   │XGBoost │ │  SHAP  │ │Claude│ │  FAISS │
   │ Model  │ │Explainer│ │  LLM │ │  Index │
   └────────┘ └────────┘ └──────┘ └────────┘
        │          │          │          │
   ┌────▼──────────▼──────────▼──────────▼────┐
   │          PostgreSQL + Redis               │
   │  (predictions, cases, audit, cache)       │
   └──────────────────────────────────────────┘
```

**Architectural Pattern:** Layered architecture (Presentation → API → Services → Data/ML)

The system follows a clean separation of concerns:
- **Presentation Layer:** Streamlit dashboard for visualization
- **API Layer:** FastAPI handles HTTP requests, validation, rate limiting
- **Service Layer:** Business logic for predictions, explanations, case management
- **Data Layer:** SQLAlchemy ORM, Redis cache, FAISS index
- **ML Layer:** Model training, evaluation, HPO, drift detection

---

## 5. Complete Folder Structure Tree

```
Credit Card Fraud Detection/
├── api/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── auth.py                    # API authentication
│   ├── limiter.py                 # Rate limiting (Redis-backed)
│   ├── logging_config.py          # Structured logging setup
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── predict.py             # /predict endpoint
│   │   ├── explain.py             # /explain endpoint (SHAP)
│   │   ├── chat.py                # /chat endpoint (LLM)
│   │   ├── similar.py             # /similar endpoint (RAG)
│   │   ├── feedback.py            # /feedback endpoint
│   │   ├── drift.py               # /drift monitoring
│   │   ├── governance.py          # Model governance endpoints
│   │   └── health.py              # Health check
│   └── schemas.py                 # Pydantic request/response models
├── src/
│   └── fraudlens/
│       ├── __init__.py
│       ├── config.py              # Centralized configuration (Pydantic)
│       ├── data/
│       │   ├── __init__.py
│       │   ├── loaders.py         # Dataset loading (Kaggle/synthetic)
│       │   └── preprocessing.py   # Feature engineering, scaling, resampling
│       ├── models/
│       │   ├── __init__.py
│       │   ├── train.py           # Model training (6 algorithms)
│       │   ├── anomaly.py         # Isolation Forest detector
│       │   ├── hpo.py             # Optuna hyperparameter optimization
│       │   └── model_selection.py # Best model selection logic
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── metrics.py         # Precision, Recall, F1, PR-AUC
│       │   └── business_cost.py   # Business cost optimization
│       ├── inference/
│       │   ├── __init__.py
│       │   ├── predictor.py       # Prediction service
│       │   ├── explainer.py       # SHAP explanation service
│       │   └── llm_narrator.py    # LLM case narration
│       └── rag/
│           ├── __init__.py
│           ├── embeddings.py      # Feature embedding generation
│           └── retriever.py       # FAISS similar-case retrieval
├── tests/
│   ├── test_api.py                # API endpoint tests
│   ├── test_preprocessing.py      # Data preprocessing tests
│   ├── test_train.py              # Model training tests
│   └── test_rate_limit_shared.py  # Rate limiting tests
├── dashboard/
│   ├── streamlit_app.py           # Main dashboard entry
│   └── pages/
│       ├── 01_live_monitor.py     # Real-time transaction monitoring
│       ├── 02_case_investigator.py # Case investigation tools
│       ├── 03_model_performance.py # Model metrics visualization
│       ├── 04_model_governance.py  # Model review/promotion
│       └── 05_analyst_copilot.py   # LLM-assisted analysis
├── models/                        # Saved model artifacts
├── data/
│   ├── raw/                       # Raw datasets
│   └── processed/                 # Processed data + charts
├── reports/                       # Model comparison reports
├── requirements.txt               # Python dependencies
├── run_pipeline.py                # Full training pipeline
├── train_and_compare.py           # Model comparison script
├── Dockerfile                     # Multi-stage Docker build
├── docker-compose.yml             # Service orchestration
├── docker-compose.dev.yml         # Development overrides
├── docker-compose.prod.yml        # Production overrides
├── Makefile                       # Build/test/deploy commands
├── alembic.ini                    # Database migration config
├── README.md                      # Project documentation
├── PROJECT_ANALYSIS.md            # Codebase audit
├── LICENSE                        # MIT License
├── .gitignore                     # Git ignore rules
├── .dockerignore                  # Docker ignore rules
└── .pre-commit-config.yaml        # Pre-commit hooks
```

---

## 6. Exhaustive File-by-File & Folder-by-Folder Breakdown

### 6.1 Root Files

#### `run_pipeline.py`
- **Type:** Python script
- **Purpose:** Orchestrates the full model comparison pipeline (Stages 1-7)
- **Key Logic:**
  1. Data Loading — Loads creditcard.csv via `DataLoader`
  2. Preprocessing — Scales features, handles class imbalance
  3. Resampling Comparison — Tests none, random_under, SMOTE, ADASYN, SMOTE-Tomek
  4. Hyperparameter Optimization — Optional Optuna tuning for XGBoost/LightGBM
  5. Model Training — Trains 6 supervised + 1 unsupervised models
  6. Evaluation — Computes metrics, finds optimal thresholds
  7. Chart Generation — PR curves, ROC curves, confusion matrices, cost analysis
- **Outputs:** `models/best_fraud_model.pkl`, `models/threshold.txt`, comparison charts
- **Dependencies:** src.fraudlens.*, mlflow, joblib, matplotlib, seaborn

#### `requirements.txt`
- **Type:** Dependency manifest
- **Purpose:** Lists all Python packages with version constraints
- **Notable Dependencies:**
  - `anthropic` — LLM integration
  - `faiss-cpu` — Vector similarity search
  - `imbalanced-learn` — SMOTE resampling
  - `mlflow` — Experiment tracking
  - `optuna` — Hyperparameter optimization
  - `prometheus-fastapi-instrumentator` — Metrics

#### `Dockerfile`
- **Type:** Docker build configuration
- **Purpose:** Multi-stage build with `serve` and `train` targets
- **Stages:**
  1. `base` — Python 3.10-slim with system deps
  2. `deps-train` — Full training dependencies (TF, CatBoost, Optuna)
  3. `deps-serve` — Slim serving dependencies (no TF/CatBoost)
  4. `serve` — Production API image (~400MB)
  5. `train` — Full training image

#### `Makefile`
- **Type:** Build automation
- **Commands:** `setup`, `train`, `api`, `dashboard`, `test`, `lint`, `docker-up`

### 6.2 `api/` — FastAPI Application

#### `api/main.py`
- **Purpose:** FastAPI application factory with middleware, CORS, rate limiting
- **Key Components:**
  - CORS middleware for dashboard access
  - Rate limiter via slowapi
  - API key authentication
  - Structured request logging
- **Routes:** All prefixed with `/api/v1/`

#### `api/schemas.py`
- **Purpose:** Pydantic models for request/response validation
- **Key Schemas:**
  - `TransactionInput` — Transaction features for prediction
  - `PredictionResponse` — Prediction + probability + threshold
  - `ExplanationResponse` — SHAP values + feature importance
  - `ChatRequest/Response` — LLM interaction
  - `SimilarCasesResponse` — Retrieved precedents

#### `api/auth.py`
- **Purpose:** API key verification middleware
- **Logic:** Checks `X-API-Key` header against configured key

#### `api/limiter.py`
- **Purpose:** Redis-backed rate limiting configuration
- **Limits:** Configurable per endpoint (predict: 100/min, chat: 20/min)

### 6.3 `api/routers/` — API Endpoints

#### `predict.py`
- **Endpoint:** `POST /predict`
- **Purpose:** Score a transaction for fraud probability
- **Request:** `TransactionInput` (28 features + Amount)
- **Response:** Prediction (0/1), probability, threshold, SHAP explanation (optional)

#### `explain.py`
- **Endpoint:** `POST /explain`
- **Purpose:** Generate SHAP explanations for a prediction
- **Logic:** Computes SHAP values using TreeExplainer

#### `chat.py`
- **Endpoint:** `POST /chat`
- **Purpose:** LLM-powered case narration
- **Logic:** Sends prediction context to Claude, returns analyst-friendly summary

#### `similar.py`
- **Endpoint:** `POST /similar`
- **Purpose:** Retrieve similar historical fraud cases
- **Logic:** Generates embedding, searches FAISS index, returns top-K matches

### 6.4 `src/fraudlens/` — Core Library

#### `src/fraudlens/config.py`
- **Type:** Pydantic Settings
- **Purpose:** Centralized configuration with env var support
- **Key Settings:**
  - `AVG_FRAUD_LOSS` — Average fraud loss for business cost calculation
  - `REVIEW_COST` — Cost of manual review
  - `LLM_MODEL` — Claude model name
  - `RAG_TOP_K` — Number of similar cases to retrieve
  - `DRIFT_THRESHOLD` — KS-test threshold for drift detection

#### `src/fraudlens/data/loaders.py`
- **Purpose:** Load credit card fraud datasets
- **Key Functions:**
  - `load()` — Load from file or generate synthetic
  - `get_basic_stats()` — Dataset statistics

#### `src/fraudlens/data/preprocessing.py`
- **Purpose:** Feature engineering and data preparation
- **Key Classes:**
  - `FraudPreprocessor` — Scaling, train/test split
  - `Resampler` — SMOTE, ADASYN, undersampling strategies

#### `src/fraudlens/models/train.py`
- **Purpose:** Train multiple ML models
- **Key Class:** `FraudTrainer`
  - `train_all()` — Train all 6 supervised models
  - `cross_validate()` — K-fold CV for each model
  - `save_all_models()` — Persist trained models

#### `src/fraudlens/models/anomaly.py`
- **Purpose:** Isolation Forest for unsupervised anomaly detection
- **Key Class:** `IsolationForestDetector`

#### `src/fraudlens/models/hpo.py`
- **Purpose:** Optuna-based hyperparameter optimization
- **Key Class:** `HyperparameterOptimizer`
  - `tune_xgboost()` — XGBoost HPO
  - `tune_lightgbm()` — LightGBM HPO

#### `src/fraudlens/evaluation/metrics.py`
- **Purpose:** Comprehensive model evaluation
- **Key Class:** `FraudEvaluator`
  - `evaluate_model()` — Full metrics suite
  - `compare_models()` — Side-by-side comparison table

#### `src/fraudlens/evaluation/business_cost.py`
- **Purpose:** Business-aware threshold optimization
- **Key Class:** `BusinessCostCalculator`
  - `find_optimal_threshold()` — Minimize net fraud loss

### 6.5 `tests/` — Test Suite

| File | Purpose |
|------|---------|
| `test_api.py` | API endpoint validation |
| `test_preprocessing.py` | Data pipeline correctness |
| `test_train.py` | Model training verification |
| `test_rate_limit_shared.py` | Rate limiting behavior |

---

## 7. Data Models & Schemas

### Transaction Features (PCA-transformed)

| Feature | Type | Description |
|---------|------|-------------|
| `V1-V28` | float | PCA components (anonymized features) |
| `Amount` | float | Transaction amount |
| `Class` | int | Target: 0=legitimate, 1=fraud |

### Prediction Result

```python
{
    "prediction": int,           # 0 or 1
    "probability": float,        # 0.0 - 1.0
    "threshold": float,          # Decision threshold
    "shap_values": list[float],  # Feature contributions
    "top_features": list[dict]   # Feature name + importance
}
```

### Case Record

```python
{
    "case_id": str,
    "transaction_id": str,
    "prediction": int,
    "probability": float,
    "narrative": str,            # LLM-generated
    "similar_cases": list[dict], # RAG results
    "analyst_notes": str,
    "status": str                # pending, reviewed, confirmed
}
```

---

## 8. API Surface

### Core Endpoints

| Method | Path | Purpose | Auth | Rate Limit |
|--------|------|---------|------|------------|
| `POST` | `/api/v1/predict` | Score transaction | API Key | 100/min |
| `POST` | `/api/v1/explain` | SHAP explanation | API Key | 50/min |
| `POST` | `/api/v1/chat` | LLM case narration | API Key | 20/min |
| `POST` | `/api/v1/similar` | Find similar cases | API Key | 50/min |
| `POST` | `/api/v1/feedback` | Submit feedback | API Key | 100/min |
| `GET` | `/api/v1/drift` | Drift detection report | API Key | 10/min |
| `GET` | `/api/v1/health` | Health check | None | 1000/min |

### Request/Response Examples

**POST /predict**
```json
// Request
{
    "V1": -1.35, "V2": -0.07, /* ... V28 */ "Amount": 149.62
}

// Response
{
    "prediction": 1,
    "probability": 0.847,
    "threshold": 0.5,
    "explanation": {
        "V14": -2.34,
        "V4": 1.89,
        "Amount": 0.42
    }
}
```

---

## 9. Configuration & Environment Variables

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `ANTHROPIC_API_KEY` | Claude API key for LLM features | — | Yes (for LLM) |
| `DATABASE_URL` | PostgreSQL connection string | SQLite fallback | No |
| `REDIS_URL` | Redis connection string | In-memory fallback | No |
| `KAGGLE_USERNAME` | Kaggle username for data download | — | No |
| `KAGGLE_KEY` | Kaggle API key | — | No |
| `API_KEY` | API authentication key | — | Yes (for API) |
| `API_PORT` | API server port | `8000` | No |
| `DASHBOARD_PORT` | Streamlit dashboard port | `8501` | No |
| `MLFLOW_TRACKING_URI` | MLflow server URL | `http://localhost:5000` | No |
| `DRIFT_THRESHOLD` | KS-test drift threshold | `0.05` | No |
| `HPO_ENABLED` | Enable Optuna HPO | `True` | No |
| `HPO_N_TRIALS` | Number of HPO trials | `30` | No |

---

## 10. Build, Run & Deployment Instructions

### Prerequisites
- Python 3.10+
- Docker (optional)
- Kaggle account (for real dataset)

### Local Development

```bash
# 1. Clone and install
git clone <repo-url>
cd "Credit Card Fraud Detection"
pip install -r requirements.txt

# 2. Download/generate dataset
make setup-data

# 3. Train models
make train

# 4. Run API
make api

# 5. Run dashboard
make dashboard
```

### Docker

```bash
# Development
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Testing

```bash
make test           # All tests
make test-cov       # With coverage
make test-integration  # Integration only
make lint           # Code quality
```

---

## 11. Data & Control Flow Walkthroughs

### Flow 1: Transaction Prediction

```
1. Client sends POST /api/v1/predict with transaction features
2. api/routers/predict.py validates input via Pydantic schema
3. src/fraudlens/inference/predictor.py loads best model
4. Model predicts probability using preprocessor + scaler
5. If probability > threshold → fraud detected
6. Optionally compute SHAP values for explanation
7. Store prediction in database for audit trail
8. Return PredictionResponse to client
```

### Flow 2: Case Investigation with LLM

```
1. Analyst submits case for investigation
2. POST /api/v1/explain generates SHAP explanation
3. POST /api/v1/similar retrieves historical precedents
4. POST /api/v1/chat sends context to Claude
5. Claude generates plain-English narrative
6. Analyst reviews and adds notes
7. Case status updated to reviewed/confirmed
```

### Flow 3: Model Retraining

```
1. Drift detection triggers (KS-test > threshold)
2. System collects new labeled data from feedback
3. Optuna runs HPO with new data
4. MLflow tracks candidate model
5. Model governance UI shows comparison
6. Analyst reviews and promotes/rejects
7. If promoted, new model deployed to serving
```

---

## 12. Dependency Graph Summary

### Internal Dependencies

```
api/main.py
  ├── api/routers/* → api/schemas.py
  ├── src/fraudlens/inference/* → src/fraudlens/models/*
  ├── src/fraudlens/rag/* → src/fraudlens/data/*
  └── src/fraudlens/config.py (global)

run_pipeline.py
  ├── src/fraudlens/data/loaders.py
  ├── src/fraudlens/data/preprocessing.py
  ├── src/fraudlens/models/train.py
  ├── src/fraudlens/models/anomaly.py
  ├── src/fraudlens/models/hpo.py
  ├── src/fraudlens/evaluation/*
  └── src/fraudlens/config.py
```

### External Package Purposes

| Package | Purpose |
|---------|---------|
| `xgboost` | Gradient boosting classifier |
| `lightgbm` | Fast gradient boosting |
| `shap` | Model explainability |
| `anthropic` | LLM integration |
| `faiss-cpu` | Vector similarity search |
| `mlflow` | Experiment tracking |
| `optuna` | Hyperparameter optimization |
| `evidently` | Data drift detection |
| `fastapi` | REST API framework |
| `streamlit` | Interactive dashboard |

---

## 13. Testing Strategy

### Test Types
- **Unit tests:** Model training, preprocessing, evaluation
- **Integration tests:** API endpoints with mocked models
- **Load tests:** Locust for performance validation

### Coverage
- Current coverage: ~78%
- Target: 85%+

### Running Tests

```bash
# Unit tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/fraudlens --cov-report=term-missing

# Integration tests
pytest tests/ -m integration

# Load tests
locust -f tests/locustfile.py
```

### Known Test Issues
- `test_api.py` requires `structlog` module
- `test_preprocessing.py` requires `imblearn` module
- `test_train.py` requires `lightgbm` module

---

## 14. Known Issues, Technical Debt & Assumptions

### Known Issues
1. **Missing dependencies in requirements.txt:** `structlog`, `imblearn`, `lightgbm` not properly installed in some environments
2. **Pydantic deprecation warnings:** Using deprecated `env` kwarg on `Field`
3. **Test collection errors:** Some tests fail to import due to missing modules

### Technical Debt
1. **Model serialization:** Using pickle (fragile across versions)
2. **FAISS index rebuild:** No incremental update mechanism
3. **LLM rate limiting:** No token budget enforcement

### Assumptions
- Credit card fraud dataset follows standard PCA-transformed schema
- Amount is in same currency units
- Transaction features V1-V28 are normalized

---

## 15. Glossary

| Term | Definition |
|------|------------|
| **PR-AUC** | Precision-Recall Area Under Curve — metric for imbalanced classification |
| **SHAP** | SHapley Additive exPlanations — game theory-based model interpretability |
| **RAG** | Retrieval-Augmented Generation — combining search with LLM generation |
| **SMOTE** | Synthetic Minority Over-sampling Technique |
| **HPO** | Hyperparameter Optimization |
| **KS-test** | Kolmogorov-Smirnov test for distribution comparison |
| **Isolation Forest** | Unsupervised anomaly detection algorithm |

---

## 16. Changelog / Version History Summary

No explicit CHANGELOG.md found. Based on PROJECT_ANALYSIS.md:
- **Current state:** Verified & Cleaned
- **Known issues:** Test collection errors due to missing dependencies
- **CI/CD:** Verified and functional

---

## 17. Appendix

### License
MIT — see LICENSE file

### Dataset
- **Primary:** Credit Card Fraud Dataset from Kaggle (284,807 transactions, 492 fraud)
- **Fallback:** Synthetic dataset generated with matching schema

### Model Performance Benchmarks
| Model | PR-AUC | F1 | Train Time |
|-------|--------|-----|------------|
| XGBoost | Best | High | Fast |
| LightGBM | Good | Good | Fastest |
| Random Forest | Moderate | Moderate | Slow |
| Logistic Regression | Baseline | Low | Fastest |
| Isolation Forest | N/A | N/A | Fast |

---

*This document was auto-generated from comprehensive codebase analysis.*
