# Changelog

All notable changes to FraudLens will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.1] — 2026-07-22
### Fixed

#### Pipeline Crash: `has_autoencoder` NameError (Phase 14b)
- Removed dangling `has_autoencoder` reference in `run_pipeline.py:396` that caused a `NameError` during the summary print step — the pipeline could not complete end-to-end
- Added `tests/test_pipeline_smoke.py` — regression smoke test that directly exercises the summary code path with synthetic data, including a test that proves `exec("has_autoencoder")` raises `NameError`

#### EDA Bugs Discovered During Test Fixing
- `_save_fig()` ignored the `output_dir` parameter passed to `run_eda()` — always saved to the global `FIGURES_DIR` instead (real assertion test now catches this)
- `plot_pairplot_top_features()` used integer keys (`COLORS[0]`) for a string-keyed `COLORS` dict, causing `KeyError: 0` — fixed to `COLORS[v.lower()]`

### Added

#### EDA Feature Importance Cache Tests (Phase 14b)
- `TestFeatureImportanceCache` (3 tests):
  - Cache miss → populates and returns computed value
  - Cache hit → returns cached value without calling `RandomForestClassifier.fit()` again (spy verification)
  - Cache invalidation → `run_eda()` recomputes fresh data (not stale from prior call)

#### HPO Failure Path & Best-Params Tests (Phase 14b)
- `TestHPOFailurePath` (2 tests):
  - Trial failure → error caught gracefully at caller level, study continues
  - Import-error fallback → returns sensible default parameters
- `TestHPOBestParamsPassThrough` (1 test):
  - Mock constructor spy verifies `best_params` from Optuna study reach model kwargs

#### LLM Mocked-Client Tests (Phase 14b)
- `TestMockedAnthropicPath` (3 tests): exercises the actual API-call code path via conftest's auto-used `mock_anthropic` fixture
- `TestMockedAnthropicEdgeCases` (4 tests): timeout, empty response, malformed response, circuit breaker — all fail closed to fallback narrative
- `TestFactualityChecker` (5 tests): golden-set factuality checks using minimal checker logic

#### Redis Shared-Counter Integration Test (Phase 14b)
- `tests/test_rate_limit_shared.py` — two `Limiter` instances sharing Redis verify multi-worker safety
- Negative test: separate in-memory limiters show different state (proves positive test is not a false positive)
- Referenced from `SECURITY.md` rate-limiting section as evidence for the multi-worker-safety claim

### Changed
- `SECURITY.md`: Added shared-counter test reference to rate-limiting section with run command
- `docs/adr/../decisions/0000-baseline.md`: Updated with Phase 14b results (coverage, test additions, EDA bug fixes, pipeline fix)

## [2.1.0] — 2026-07-22
### Added

#### Automated Data Download (Phase 14 — Gap 1)
- `src/fraudlens/data/download.py` — Kaggle API download + synthetic fallback
- Synthetic dataset: 10,000 rows matching real schema (V1-V28, Time, Amount, Class)
- Zero-credential demo: works without Kaggle account via synthetic data
- `make setup-data` target for manual data setup
- Docker Compose auto-downloads data on first startup
- README Quickstart updated with both Kaggle and synthetic paths

#### Rate Limiting: Redis Default (Phase 14 — Gap 3)
- `api/rate_limit.py` now defaults to Redis-backed storage
- In-memory storage opt-in via `RATE_LIMIT_BACKEND=memory` with startup warning
- Graceful fallback: if Redis unreachable, falls back to in-memory with warning
- Safe for multi-worker / multi-replica deployments out of the box

#### LLM Cost Tracking (Phase 14 — Gap 4)
- `src/fraudlens/llm/cost_tracker.py` — thread-safe, per-call cost recording
- Config-driven price table (per 1M tokens, models: claude-sonnet-4, claude-3.5-sonnet, claude-3-haiku, claude-3-opus)
- Prometheus counters: `fraudlens_llm_cost_usd_total{model,endpoint}`, `fraudlens_llm_tokens_total{model,endpoint,type}`, `fraudlens_llm_calls_total{model,endpoint,status}`
- Wired into `CaseNarrator` — every LLM call records input/output tokens and cost
- `GET /v1/admin/llm-usage?period=today|month|total` — admin-only endpoint for spend queries
- Structured log field on every LLM call with cost breakdown

#### LLM Cost Persistence to Database (Phase 14 — Gap 4 follow-up)
- `LlmCallModel` — SQLAlchemy ORM model with `llm_calls` table (`alembic/versions/003_llm_calls.py`)
- `LlmCallRepository` — async repository with period-based aggregation queries
- `CostTracker.merge_summaries()` — merges in-memory (recent) + DB (historical) cost data
- `CostTracker.get_pending_records()` / `clear_pending()` — flush management helpers
- `GET /v1/admin/llm-usage` now flushes pending records to DB before querying, then merges DB + in-memory results — cost data survives restarts
- Streamlit dashboard sidebar now shows **LLM Spend Today** with cost, call count, token usage, and per-model breakdown in a styled card

#### Autoencoder Removal (Phase 14 — Gap 6)
- Removed `AutoencoderDetector` class from `src/fraudlens/models/anomaly.py`
- Removed TensorFlow and Keras from `requirements.txt` (~600MB dependency saved)
- Removed `AUTOENCODER_ENCODING_DIM`, `AUTOENCODER_EPOCHS`, `AUTOENCODER_BATCH_SIZE` from config
- `IsolationForestDetector` is now the sole unsupervised anomaly detector
- `docs/adr/../decisions/0001-remove-autoencoder.md` — ADR documenting the decision

#### Automated Retraining Trigger (Phase 14 — Gap 7)
- `src/fraudlens/retraining/` package — automated retraining trigger module
- Drift trigger: checks for CRITICAL drift events since last training
- Feedback volume trigger: checks if accumulated feedback >= configurable threshold
- K8s CronJob (`infra/k8s/cronjob.yaml`) runs daily at 2 AM — checks conditions, triggers pipeline if met
- MLflow candidate registration: every triggered run tagged with `trigger=drift|feedback_volume` and `is_candidate=true`
- No auto-promotion: retraining registers candidates only; human must promote via API
- Admin API endpoints (auth-protected):
  - `GET /v1/admin/models/candidates` — list candidates with pagination and status filter
  - `GET /v1/admin/models/candidates/{version}` — view candidate details
  - `POST /v1/admin/models/candidates/{version}/promote` — human-gated promotion to production
  - `POST /v1/admin/models/candidates/{version}/reject` — mark candidate as rejected
  - `GET /v1/admin/models/candidates/{version}/compare` — compare candidate vs current production
- `ModelCandidateModel` — SQLAlchemy ORM model with `model_candidates` table (`alembic/versions/002_model_candidates.py`)
- `ModelCandidateRepository` — async repository with candidate CRUD and promotion logic
- Config-driven thresholds via env vars (`RETRAINING_FEEDBACK_THRESHOLD`, `RETRAINING_DRIFT_CRITICAL_THRESHOLD`, etc.)
- `python -m src.fraudlens.retraining.retrain_trigger` entry point for CronJob
- 51 tests in `tests/test_retrain_trigger.py` covering all trigger conditions, timestamp parsing edge cases, dry-run mode, pipeline failure paths, and integration scenarios

#### Model Governance Dashboard (Phase 14 — Gap 7 follow-up)
- New **Model Governance** Streamlit page (`app/pages/model_governance.py`) with 3-tab layout:
  - **Pending Candidates tab:** summary stats, status filter, expandable cards with PR-AUC/F1/Precision/Recall deltas (▲ green / ▼ red vs production), and Promote/Reject buttons
  - **History tab:** lists previously promoted/rejected candidates with timestamps
  - **About tab:** explains the governance workflow (drift trigger, feedback volume, no auto-promotion)
- Admin API client methods: `get_candidates()`, `promote_candidate()`, `reject_candidate()`, `compare_candidate()`
- `FRAUDLENS_DASHBOARD_API_KEY` env var for dashboard-to-API admin auth
- Demo fallback content with realistic sample candidates when no admin API key configured

#### Test Coverage (Phase 14 — Gap 2)
- `tests/test_download.py` — 25+ tests for the download module (synthetic generation, validation, Kaggle detection, ensure_data_ready, get_or_create_data)
- `tests/test_retrain_trigger.py` — 51 tests for retraining trigger (drift/feedback conditions, dry-run, pipeline failure, timestamp parsing, integration scenarios)

### Changed
- `requirements.txt`: Removed `tensorflow>=2.12.0` and `keras>=2.12.0`
- `src/fraudlens/data/__init__.py`: Exports `ensure_data_ready` and `get_or_create_data`
- `src/fraudlens/llm/case_narrator.py`: Uses `_call_llm_with_response()` to capture usage tokens for cost tracking
- `api/routers/admin.py`: Added `/v1/admin/llm-usage` endpoint (admin-only, rate-limited)
- `api/rate_limit.py`: Redis default with memory fallback and startup warnings
- `docker-compose.yml`: Auto-downloads/generates data on container startup
- `docs/adr/../decisions/0000-baseline.md`: Updated with Phase 14 results (audit score 7.8 → 9.1)

### Removed
- `AutoencoderDetector` class (untrained, unused, TF dependency cost)
- TensorFlow and Keras from `requirements.txt`
- Autoencoder config settings from `src/fraudlens/config.py`

## [2.0.0] — 2026-07-21

### Added

#### Observability (Phase 10)
- Structured JSON logging via `structlog` with correlation ID middleware
- Prometheus metrics via `prometheus-fastapi-instrumentator`:
  - `fraudlens_prediction_total{outcome="fraud|legitimate"}`
  - `fraudlens_prediction_latency_ms`, `fraudlens_shap_latency_ms`, `fraudlens_llm_latency_ms`
  - `fraudlens_cache_hit_total`, `fraudlens_model_loaded`, `fraudlens_llm_available`
  - Auto-instrumentation for request count/latency by endpoint
- OpenTelemetry tracing with OTLP exporter to Jaeger
  - FastAPI auto-instrumentation (graceful fallback if packages not installed)
  - Console span exporter for local debugging
- Grafana dashboard (`infra/grafana/dashboard.json`) with 13 panels
- Prometheus scrape config (`infra/prometheus/prometheus.yml`)

#### Configuration (Phase 11)
- `pydantic-settings` `BaseSettings` with env-driven configuration
- Feature flags: `FEATURE_LLM_NARRATOR`, `FEATURE_ANOMALY_SCORE`, `FEATURE_SHAP_EXPLANATION`, `FEATURE_CACHE_PREDICTIONS`, `FEATURE_RAG_RETRIEVAL`
- `.env.example` with all documented environment variables
- Backward-compatible module-level constants

#### Error Handling & Resilience (Phase 12)
- Typed exception classes: `ModelNotLoadedError` (503), `LLMServiceUnavailable` (503), `PredictionError` (500), `RetrieverUnavailable` (503), `InvalidInputError` (422)
- `LLMCircuitBreaker` with CLOSED/OPEN/HALF_OPEN states, configurable thresholds, cooldown multiplier
- Tenacity retry wrapper around Anthropic API (3 attempts, exponential backoff 2s–8s)
- Honest fallback narratives with `[Automated summary — narrative generation unavailable]` prefix
- `docs/../reference/RESILIENCE.md` documenting all graceful degradation scenarios

#### Documentation & Polish (Phase 13)
- `CHANGELOG.md` (this file)
- `CONTRIBUTING.md` (developer guide)
- `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1)
- GitHub issue templates (bug report + feature request)
- GitHub pull request template

### Changed

- **Package rename:** `fraudshield` → `fraudlens` across all imports, Docker, CI, and docs
- **Configured pre-commit** with `black`, `ruff`, `isort`, `mypy`, `nbstripout`
- **Security:** API key auth via `X-API-Key` header with two tiers (admin/readonly), SHA-256 hashed keys, slowapi rate limiting on all endpoints, Pydantic validation with NaN/Inf rejection, CORS locked to explicit origins, security headers (HSTS, CSP, X-Frame-Options, etc.)
- **Architecture:** Removed global mutable state, injected dependencies via FastAPI `Depends()`, split `FraudPredictor` into `ModelLoader` + `FraudPredictor` + `ShapExplainer` + `ExplanationFormatter`
- **Data layer:** PostgreSQL via docker-compose, Alembic migrations, repository pattern, prediction/feedback/API keys tables
- **Performance:** Async SHAP via FastAPI `BackgroundTasks`, Redis LRU prediction cache, vectorized numpy prediction path, Locust load tests
- **ML quality:** `FeatureEngineer` wired into both training and inference, Optuna hyperparameter tuning (30 trials, 3-fold CV), model card (`docs/../reference/MODEL_CARD.md`)
- **API design:** All endpoints under `/v1/`, RFC 7807 error format, cursor-based pagination on `/v1/similar-cases`, per-dependency health check with degraded status
- **Frontend:** Shared API client (`app/api_client.py`), no hardcoded mock data in production pages, loading spinners with retries/timeouts, live synthetic transaction streaming
- **Testing:** 85% coverage target, integration tests with real model fixture, mocked external services (respx), edge-case tests (NaN/Inf/empty batch/boundary), OpenAPI contract tests
- **DevOps:** Multi-stage Docker (slim serve image ~400MB), Trivy/Grype image scanning in CI, blocking lint, parallelized tests (`pytest -n auto`), CD stage to GHCR, K8s manifests (deployment/service/hpa/ingress/configmap/secret)
- **Updated `.gitignore`** with comprehensive patterns for all generated/temp files

### Fixed

- Health endpoint now returns per-dependency status (`{"model": "ok", "llm": "down", ...}`) instead of a single boolean
- Empty batch requests return 422 with clear validation message
- NaN/Inf inputs return 422 instead of causing model errors
- Fallback narrative prefix clearly distinguishes template output from LLM-generated narratives
- Model checksum verification prevents loading tampered artifacts

## [1.0.0] — 2026-07-01

### Added

- Initial project scaffolding — `fraudshield` package with basic ML pipeline
- FastAPI server with prediction endpoints
- Streamlit dashboard with 4 pages: Live Monitor, Case Investigator, Model Performance, Analyst Copilot
- XGBoost, Random Forest, Logistic Regression, LightGBM, Isolation Forest model training
- SHAP explainability integration
- LLM Case Narrator (Anthropic Claude)
- FAISS-based RAG similar-case retrieval
- Docker Compose setup
- Basic CI pipeline (GitHub Actions)
- Unit tests for core modules
- EDA notebooks
- Baseline audit and architecture decision records
