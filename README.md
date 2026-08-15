<p align="center">
  <img src="https://img.shields.io/badge/FraudLens-Fraud%20Detection-red?style=for-the-badge" alt="FraudLens Logo" />
</p>

<h1 align="center">🔍 FraudLens</h1>

<p align="center">
  <strong>Production-Grade Credit Card Fraud Detection with Explainability</strong>
</p>

<p align="center">
  <a href="https://github.com/themanoj-025/Credit-Card-Fraud-Detection/actions"><img src="https://img.shields.io/github/actions/workflow/status/themanoj-025/Credit-Card-Fraud-Detection/ci.yml?style=flat-square&label=CI" alt="CI Status" /></a>
  <a href="https://github.com/themanoj-025/Credit-Card-Fraud-Detection/blob/main/LICENSE"><img src="https://img.shields.io/github/license/themanoj-025/Credit-Card-Fraud-Detection?style=flat-square" alt="License" /></a>
  <a href="https://github.com/themanoj-025/Credit-Card-Fraud-Detection/stargazers"><img src="https://img.shields.io/github/stars/themanoj-025/Credit-Card-Fraud-Detection?style=social" alt="Stars" /></a>
  <a href="#"><img src="https://img.shields.io/badge/coverage-78%25-yellowgreen?style=flat-square" alt="Coverage" /></a>
</p>

---

<p align="center">
  <strong>Every prediction explained. Every fraud caught.</strong>
  <br />
  XGBoost, SHAP explainability, LLM narratives, and RAG-based case retrieval — all in one production-ready system.
</p>

---

## 📋 Table of Contents

- [✨ Features](#-features)
- [🚀 Quick Start](#-quick-start)
- [📊 Model Performance](#-model-performance)
- [🏗️ Architecture](#️-architecture)
- [📋 Environment Variables](#-environment-variables)
- [📁 Project Structure](#-project-structure)
- [🧪 Testing](#-testing)
- [📡 API Endpoints](#-api-endpoints)
- [🗺️ Roadmap](#️-roadmap)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)
- [🙏 Acknowledgements](#-acknowledgements)

---

> 📸 **Screenshot placeholder:** Add a screenshot of the Streamlit dashboard's live-monitor page.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **6 ML Models** | XGBoost, LightGBM, Random Forest, Logistic Regression, CatBoost, Isolation Forest |
| 🔍 **SHAP Explainability** | Feature importance for every prediction |
| 📝 **LLM Narration** | Plain-English case summaries via Claude |
| 🔎 **RAG Similar Cases** | FAISS-powered historical fraud retrieval |
| 📊 **Real-time Dashboard** | 5-page Streamlit UI with live monitoring |
| 🏛️ **Model Governance** | Human-in-the-loop model promotion |
| 🔄 **Auto Retraining** | Drift detection + MLflow tracking |
| 🐳 **Production Ready** | FastAPI + Docker + Kubernetes |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (recommended)
- Kaggle account (for real dataset)

### Option 1: Docker (Recommended)

```bash
# Clone and start
git clone https://github.com/themanoj-025/Credit-Card-Fraud-Detection.git
cd "Credit Card Fraud Detection"
docker compose up -d

# Access services
# Dashboard: http://localhost:8501
# API: http://localhost:8000
```

> 💡 **Tip:** First run auto-generates a synthetic dataset (5,000 transactions) so the demo works immediately!

### Option 2: Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Setup dataset
make setup-data

# Train models
make train

# Start API
make api

# Start Dashboard
make dashboard
```

---

## 📊 Model Performance

Fraud detection is evaluated with the rare-positive metrics that matter: precision, recall, and PR-AUC.

<!-- TODO: add the real fraud-detection metrics from the trained models (precision / recall / PR-AUC / F1 per model) -->

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Dashboard                         │
│  Live Monitor │ Case Investigator │ Model Performance │ ...     │
└───────────────┬─────────────────────────────────────────────────┘
                │ HTTP
┌───────────────▼─────────────────────────────────────────────────┐
│                  FastAPI Server (:8000)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ /predict │ │ /explain │ │  /chat   │ │ /similar │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       │            │            │            │                  │
│  ┌────▼─────┐ ┌────▼─────┐ ┌────▼─────┐ ┌────▼─────┐          │
│  │ XGBoost  │ │   SHAP   │ │  Claude  │ │  FAISS   │          │
│  │  Model   │ │Explainer │ │   LLM    │ │  Index   │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└───────────────────────┬─────────────────────────────────────────┘
                        │
              ┌─────────▼─────────┐
              │  PostgreSQL + Redis│
              └───────────────────┘
```

---

## 📋 Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ANTHROPIC_API_KEY` | Claude API key for LLM features | — | For LLM |
| `DATABASE_URL` | PostgreSQL connection | SQLite fallback | ❌ |
| `REDIS_URL` | Redis connection | In-memory fallback | ❌ |
| `KAGGLE_USERNAME` | Kaggle username | — | For real data |
| `KAGGLE_KEY` | Kaggle API key | — | For real data |
| `API_KEY` | API authentication key | — | For API |

---

## 📁 Project Structure

```
Credit Card Fraud Detection/
├── api/
│   ├── main.py              # FastAPI application
│   ├── routers/             # API endpoints
│   └── schemas.py           # Pydantic models
├── src/fraudlens/
│   ├── config.py            # Centralized configuration
│   ├── data/
│   │   ├── loaders.py       # Dataset loading
│   │   └── preprocessing.py # Feature engineering
│   ├── models/
│   │   ├── train.py         # Model training
│   │   ├── anomaly.py       # Isolation Forest
│   │   └── hpo.py           # Hyperparameter optimization
│   ├── evaluation/
│   │   ├── metrics.py       # Model evaluation
│   │   └── business_cost.py # Threshold optimization
│   ├── inference/
│   │   ├── predictor.py     # Prediction service
│   │   ├── explainer.py     # SHAP explanations
│   │   └── llm_narrator.py  # LLM case narration
│   └── rag/
│       ├── embeddings.py    # Feature embeddings
│       └── retriever.py     # Similar case retrieval
├── dashboard/               # Streamlit pages
├── tests/                   # Test suite
├── models/                  # Saved artifacts
├── requirements.txt
├── Makefile
└── Dockerfile
```

---

## 🧪 Testing

```bash
# Run all tests
make test

# With coverage
make test-cov

# Integration tests only
make test-integration
```

---

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/predict` | Score transaction for fraud |
| `POST` | `/api/v1/explain` | Get SHAP explanation |
| `POST` | `/api/v1/chat` | LLM case narration |
| `POST` | `/api/v1/similar` | Find similar cases |
| `POST` | `/api/v1/feedback` | Submit feedback |
| `GET` | `/api/v1/drift` | Drift detection report |
| `GET` | `/api/v1/health` | Health check |

---

## 🗺️ Roadmap

- [x] 6 supervised + 1 unsupervised models
- [x] SHAP explainability
- [x] LLM case narration
- [x] RAG similar cases
- [x] Streamlit dashboard
- [x] FastAPI production API
- [x] Docker deployment
- [ ] Webhook integrations
- [ ] Real-time streaming pipeline
- [ ] A/B testing framework
- [ ] Multi-tenant support

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [XGBoost](https://xgboost.readthedocs.io/) - Gradient boosting
- [SHAP](https://shap.readthedocs.io/) - Model explainability
- [Anthropic](https://www.anthropic.com/) - Claude API
- [FAISS](https://faiss.ai/) - Vector similarity search
- [MLflow](https://mlflow.org/) - Experiment tracking
- [Streamlit](https://streamlit.io/) - Dashboard framework

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/themanoj-025">themanoj-025</a>
</p>

<p align="center">
  If you find this project useful, please give it a ⭐ star!
</p>
