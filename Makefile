# ════════════════════════════════════════════════════════════════
# FraudLens — Makefile
# Common development commands
# ════════════════════════════════════════════════════════════════

.PHONY: help install install-dev train api dashboard test test-cov test-integration \
        lint format clean docker-build docker-up docker-down docker-down-v \
        mlflow-ui migrate load-test pre-commit baseline

SHELL := /bin/bash

help:  ## Show this help message
	@echo "FraudLens — Development Makefile"
	@echo ""
	@echo "Usage:"
	@echo ""
	@echo "  📦 Setup"
	@echo "    make install          Install Python dependencies"
	@echo "    make install-dev      Install dev extras (pre-commit, etc.)"
	@echo "    make setup-data       Download or generate dataset"
	@echo ""
	@echo "  🚀 Run"
	@echo "    make train            Run full training pipeline"
	@echo "    make api              Start FastAPI server on :8000"
	@echo "    make dashboard        Start Streamlit dashboard on :8501"
	@echo "    make migrate          Run Alembic database migrations"
	@echo ""
	@echo "  🧪 Test"
	@echo "    make test             Run all tests (unit)"
	@echo "    make test-cov         Run tests with coverage report"
	@echo "    make test-integration Run integration tests"
	@echo "    make load-test        Run locust load tests"
	@echo ""
	@echo "  🧹 Lint"
	@echo "    make lint             Run linters (blocking)"
	@echo "    make format           Auto-format code (black + isort)"
	@echo "    make pre-commit       Run pre-commit on all files"
	@echo ""
	@echo "  🐳 Docker"
	@echo "    make docker-build     Build Docker images"
	@echo "    make docker-up        Start all Docker services"
	@echo "    make docker-down      Stop all Docker services"
	@echo "    make docker-down-v    Stop and clean volumes"
	@echo ""
	@echo "  📊 MLflow"
	@echo "    make mlflow-ui        Start MLflow tracking UI on :5000"
	@echo ""
	@echo "  🧹 Clean"
	@echo "    make clean            Remove cache and build artifacts"
	@echo "    make baseline         Record current test baseline to docs/adr/"

# ─── Setup ────────────────────────────────────────────────────

install:  ## Install Python dependencies
	pip install -r requirements.txt
	pre-commit install || echo "pre-commit not installed, skipping"

install-dev:  ## Install dev extras
	pip install -r requirements.txt
	pip install pre-commit ruff pytest-cov mypy types-requests locust
	pre-commit install

# ─── Run ──────────────────────────────────────────────────────

setup-data:  ## Download or generate dataset (Kaggle or synthetic fallback)
	python -c "from src.fraudlens.data.download import ensure_data_ready; ensure_data_ready()"

train:  ## Run full training pipeline
	python run_pipeline.py

api:  ## Start FastAPI server
	uvicorn api.main:app --reload --port 8000

dashboard:  ## Start Streamlit dashboard
	streamlit run app/streamlit_app.py --server.port 8501

# ─── Test ─────────────────────────────────────────────────────

test:  ## Run all unit tests
	pytest tests/ -v --tb=short -x

test-cov:  ## Run tests with coverage (current 78%, target 85%)
	pytest tests/ -v --cov=src/fraudlens --cov-report=term-missing --cov-fail-under=78 --tb=short -n auto

test-integration:  ## Run integration tests
	pytest tests/ -v --tb=short -n auto tests/test_integration.py tests/test_edge_cases.py

test-contract:  ## Run OpenAPI contract tests
	pytest tests/ -v --tb=short tests/test_contract.py

load-test:  ## Run locust load tests
	@echo "Starting locust. Point browser to http://localhost:8089"
	locust -f tests/load/locustfile.py --host http://localhost:8000

TRIVY_IMAGE ?= fraudlens:serve

trivy-scan:  ## Run Trivy vulnerability scan on the serve image
	trivy image --severity CRITICAL,HIGH --exit-code 1 --ignore-unfixed $(TRIVY_IMAGE)

# ─── Lint ─────────────────────────────────────────────────────

lint:  ## Run all linters (blocking — fails on issues)
	@echo "=== black ==="
	black --check src/ api/ app/ tests/
	@echo "=== isort ==="
	isort --check-only --profile=black src/ api/ app/ tests/
	@echo "=== ruff ==="
	ruff check src/ api/ app/ tests/
	@echo "✅ All linters passed"

format:  ## Auto-format code
	black src/ api/ app/ tests/
	isort --profile=black src/ api/ app/ tests/

pre-commit:  ## Run pre-commit on all files
	pre-commit run --all-files

# ─── Docker ───────────────────────────────────────────────────

docker-build:  ## Build Docker images
	docker compose build

docker-up:  ## Start all Docker services
	docker compose up

docker-down:  ## Stop all Docker services
	docker compose down

docker-down-v:  ## Stop and clean volumes
	docker compose down -v

# ─── Database ─────────────────────────────────────────────────

migrate:  ## Run Alembic migrations
	alembic upgrade head

# ─── MLflow ───────────────────────────────────────────────────

mlflow-ui:  ## Start MLflow UI
	@echo "Starting MLflow UI on port 5000..."
	mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:///mlflow/mlflow.db --default-artifact-root ./mlruns

# ─── Clean ────────────────────────────────────────────────────

clean:  ## Remove cache and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache
	rm -rf build/ dist/ *.egg-info
	rm -rf .mypy_cache .dmypy.json

# ─── K8s ──────────────────────────────────────────────────────

k8s-apply:  ## Apply Kustomize manifests to current cluster
	kubectl apply -k infra/k8s/

k8s-dry-run:  ## Dry-run Kustomize manifests
	kubectl kustomize infra/k8s/

# ─── Baseline ─────────────────────────────────────────────────

baseline:  ## Record current test baseline snapshot
	@echo "Recording baseline..."
	pytest tests/ -v --cov=src/fraudlens --cov-report=term-missing --tb=short 2>&1 | tee .baseline_test_output.txt
	@echo "Baseline saved to .baseline_test_output.txt"
