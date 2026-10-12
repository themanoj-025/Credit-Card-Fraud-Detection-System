<p align="center">
  <img src="https://img.shields.io/badge/FraudLens-Fraud%20Detection-red?style=for-the-badge" alt="FraudLens Logo" />
</p>

<h1 align="center">FraudLens</h1>

<p align="center">
  <strong>Production-grade credit card fraud detection system with SHAP explainability, RAG case precedent, and LLM narratives.</strong>
</p>

<p align="center">
  <a href="https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/actions"><img src="https://img.shields.io/github/actions/workflow/status/themanoj-025/Credit-Card-Fraud-Detection-System/ci.yml?style=flat-square&label=CI" alt="CI Status" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License MIT" /></a>
  <a href="https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/stargazers"><img src="https://img.shields.io/github/stars/themanoj-025/Credit-Card-Fraud-Detection-System?style=social" alt="GitHub Stars" /></a>
  <a href="https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/issues"><img src="https://img.shields.io/github/issues/themanoj-025/Credit-Card-Fraud-Detection-System?style=flat-square" alt="GitHub Issues" /></a>
  <a href="https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square" alt="PRs Welcome" /></a>
</p>

---

## Overview

FraudLens classifies fraudulent payment card transactions while providing transparent rationale for every flagged event. Rather than emitting an opaque risk score, it provides a calibrated supervised probability (XGBoost / ensemble), per-feature SHAP value breakdowns, contextual RAG retrieval of historical fraud precedents, and plain-English narrative justifications.

The inference pipeline is modular: it can run purely offline at sub-second latency for immediate payment blocking, or chain into LLM narrative generation for comprehensive investigation alerts.

---

## Table of Contents

- [Key Features](#key-features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Testing & Quality](#testing--quality)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)
- [Support](#support)

---

## Key Features

- **Tuned Supervised Ensembles**: Employs XGBoost and calibrated ensemble models specialized for highly imbalanced fraud transaction distributions.
- **Strict Data-Leakage Guards**: Enforces rigid pipeline hygiene where scalers, encoders, and imbalanced resampling are fit strictly on training partitions.
- **SHAP Feature Attributions**: Generates local feature contributions explaining exactly which attributes triggered an anomaly.
- **RAG Case Retrieval**: Performs semantic vector searches over historical fraud records to cite similar precedent patterns.
- **Dual Interface Delivery**: Exposes a low-latency FastAPI REST API alongside an interactive Streamlit investigation dashboard.

---

## Architecture

```text
                  Incoming Transaction
                           │
                           ▼
              ┌──────────────────────────┐
              │ Feature Extraction Engine│
              │ (Strict Anti-Leakage)    │
              └────────────┬─────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │ XGBoost Risk Scoring     │
              └────────────┬─────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
  Fast Path: Risk Score       Deep Investigation Path
  (Offline, Sub-Second)       ├── 1. SHAP Feature Attribution
                              ├── 2. Vector Case Retrieval (RAG)
                              └── 3. LLM Natural-Language Narrative
                                         │
                                         ▼
                             FastAPI / Streamlit UI
```

---

## Project Structure

```text
Credit-Card-Fraud-Detection/
├── src/
│   ├── data/                 # Ingestion, validation, and resampling modules
│   ├── features/             # Feature engineering pipelines
│   ├── models/               # XGBoost, logistic regression, and ensemble trainers
│   ├── explain/              # Local and global SHAP attribution generators
│   ├── rag/                  # Case precedent retrieval and vector store
│   ├── dashboard/            # Streamlit interactive investigator interface
│   └── api/                  # FastAPI prediction and explanation routes
├── tests/                    # Unit, pipeline, and API test suites
├── reports/                  # Validation reports and benchmark evaluations
├── run_pipeline.py           # End-to-end data and training orchestration
├── train_and_compare.py      # Model comparison and metric evaluation script
├── Dockerfile                # Production container specification
├── docker-compose.yml        # Multi-container orchestration
├── pyproject.toml            # Build backend, Ruff linting, and Pytest configuration
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## Prerequisites

- **Python**: `>= 3.12`
- **SQLite / PostgreSQL**: For transaction logging (`fraudlens.db`)
- **OpenAI API Key / Hugging Face Token**: (Optional) Required only for RAG embeddings and LLM narrative explanations

---

## Installation & Setup

```bash
# 1. Clone repository
git clone https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System.git
cd Credit-Card-Fraud-Detection-System

# 2. Create and activate virtual environment
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
```

---

## Quick Start

### 1. Run Model Training & Evaluation

```bash
python run_pipeline.py
```

### 2. Launch the FastAPI Server

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Launch the Streamlit Monitoring Dashboard

```bash
streamlit run src/dashboard/app.py
```

---

## API Reference

| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/predict` | Computes fraud risk probability and top SHAP feature drivers |
| `POST` | `/api/v1/explain` | Generates detailed narrative explanation with RAG precedent cases |
| `GET` | `/health` | Liveness probe endpoint |

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1200.00,
    "card_country": "US",
    "merchant_category": "electronics",
    "hour_of_day": 3,
    "ip_risk_score": 0.91
  }'
```

---

## Configuration

| Environment Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///fraudlens.db` | Target database for transaction logs |
| `MODELS_PATH` | `models/` | Storage path for trained model artifacts |
| `EMBEDDINGS_PATH` | `embeddings/` | Case embedding vectors directory for RAG |
| `OPENAI_API_KEY` | `""` | Optional key for LLM narrative generation |
| `HF_TOKEN` | `""` | Optional token for Hugging Face transformer models |
| `CACHE_DIR` | `cache/` | Local cache directory |

---

## Testing & Quality

Test coverage is enforced in CI at `>= 75%`.

```bash
# Run pytest test suite
pytest tests/ -v

# Run with coverage report
pytest --cov=src tests/
```

---

## Roadmap

- [x] Imbalanced data ingestion and leakage-safe preprocessing
- [x] XGBoost model training and baseline benchmark comparisons
- [x] SHAP attribution calculation for real-time predictions
- [x] FastAPI REST inference service
- [x] Streamlit monitoring dashboard
- [ ] Synthetic data generation tooling for local testing <!-- TODO: Track in GitHub issue -->
- [ ] Real-time Kafka / event stream ingestion connector <!-- TODO: Track in GitHub issue -->

---

## Contributing

Please review [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines, branch conventions, and testing instructions.

---

## Security

Please report security issues confidentially according to [SECURITY.md](SECURITY.md).

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Support

- 🐛 **Issue Tracker**: [GitHub Issues](https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/issues)
- 💡 **Feature Requests & Code**: [GitHub Pull Requests](https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/pulls)
