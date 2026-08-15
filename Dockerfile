# ════════════════════════════════════════════════════════════════
# FraudLens — Multi-stage Docker Build
#
# Targets:
#   serve       (default) — Slim production image for API (~400MB)
#   train       — Full image with training dependencies (TF, Optuna, etc.)
#   deps-serve  — Intermediate layer for dependency caching
#
# Build:
#   docker build --target serve -t fraudlens:latest .
#   docker build --target train -t fraudlens:train .
# ════════════════════════════════════════════════════════════════

# ─── Stage 1: Python Base ─────────────────────────────────────────────
FROM python:3.10-slim as base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies (minimal set for all stages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Stage 2: Training Dependencies (includes everything) ───────────
FROM base as deps-train

COPY requirements.txt .

# Split install — core deps first, then heavy training-only deps
RUN pip install --no-cache-dir \
    pandas numpy scikit-learn xgboost lightgbm imbalanced-learn \
    shap faiss-cpu \
    anthropic \
    sqlalchemy[asyncio] alembic asyncpg aiosqlite psycopg2-binary \
    matplotlib seaborn plotly \
    umap-learn scipy \
    fastapi uvicorn 'pydantic>=2.0.0' pydantic-settings httpx slowapi \
    streamlit \
    mlflow \
    joblib \
    evidently \
    redis optuna \
    python-dotenv tqdm && \
    # Install heavy training deps separately (graceful if they fail)
    pip install --no-cache-dir tensorflow keras catboost 2>/dev/null || true

# ─── Stage 3: Serve-only Dependencies (slim — no TF/CatBoost/Optuna) ─
FROM base as deps-serve

COPY requirements.txt .

# Only install what's needed for serving predictions
RUN pip install --no-cache-dir \
    pandas numpy scikit-learn xgboost lightgbm \
    shap faiss-cpu \
    anthropic \
    sqlalchemy[asyncio] alembic asyncpg aiosqlite psycopg2-binary \
    matplotlib seaborn plotly \
    umap-learn scipy \
    fastapi uvicorn 'pydantic>=2.0.0' pydantic-settings httpx slowapi \
    structlog tenacity \
    prometheus-fastapi-instrumentator \
    opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi \
    imbalanced-learn \
    streamlit \
    mlflow \
    joblib \
    evidently \
    redis \
    python-dotenv tqdm && \
    # Remove heavy packages that are only needed for training
    pip uninstall -y tensorflow keras catboost optuna 2>/dev/null || true

# ─── Stage 4: Training Image (full) ──────────────────────────────────
FROM deps-train as train

# Copy source code
COPY src/ ./src/
COPY api/ ./api/
COPY app/ ./app/
COPY tests/ ./tests/
COPY run_pipeline.py train_and_compare.py ./

# Create directories
RUN mkdir -p data/raw data/processed reports/figures logs models

# Default: run the training pipeline
CMD ["python", "run_pipeline.py"]

# ─── Stage 5: Serve Image (slim) ────────────────────────────────────
FROM deps-serve as serve

# Copy only the serving source code
COPY src/fraudlens/common/ ./src/fraudlens/common/
COPY src/fraudlens/config.py ./src/fraudlens/
COPY src/fraudlens/data/ ./src/fraudlens/data/
COPY src/fraudlens/features/ ./src/fraudlens/features/
COPY src/fraudlens/prediction/ ./src/fraudlens/prediction/
COPY src/fraudlens/explainability/ ./src/fraudlens/explainability/
COPY src/fraudlens/llm/ ./src/fraudlens/llm/
COPY src/fraudlens/monitoring/ ./src/fraudlens/monitoring/
COPY src/fraudlens/persistence/ ./src/fraudlens/persistence/
COPY src/fraudlens/evaluation/ ./src/fraudlens/evaluation/
COPY api/ ./api/
COPY app/ ./app/

# Copy trained models (if available)
COPY models/ ./models/

# Create directories
RUN mkdir -p data/raw data/processed reports/figures logs

# Expose ports: FastAPI on 8000, Streamlit on 8501
EXPOSE 8000 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default: run the API with uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
