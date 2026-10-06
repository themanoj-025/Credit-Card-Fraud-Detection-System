# 🔍 FraudLens

<p align="center">
  <img src="https://img.shields.io/badge/FraudLens-Fraud%20Detection-red?style=for-the-badge" alt="FraudLens Logo" />
</p>

<h1 align="center">🔍 FraudLens</h1>

<p align="center">
  <strong>Production-Grade Credit Card Fraud Detection with Explainability</strong>
</p>

<p align="center">
  <a href="https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/actions"><img src="https://img.shields.io/github/actions/workflow/status/themanoj-025/Credit-Card-Fraud-Detection-System/ci.yml?style=flat-square&label=CI" alt="CI Status" /></a>
  <a href="https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/blob/main/LICENSE"><img src="https://img.shields.io/github/license/themanoj-025/Credit-Card-Fraud-Detection-System?style=flat-square" alt="License" /></a>
  <a href="https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/stargazers"><img src="https://img.shields.io/github/stars/themanoj-025/Credit-Card-Fraud-Detection-System?style=social" alt="Stars" /></a>
  <a href="https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/actions/workflows/ci.yml"><img src="https://img.shields.io/badge/coverage-enforced%20%3E%3D75%25%20in%20CI-yellowgreen?style=flat-square" alt="Test coverage enforced at 75 percent minimum in CI" /></a>
</p>

---

## 📋 Table of Contents

- [What it does](#what-it-does)
- [📸 Screenshots](#-screenshots)
- [✨ Features](#-features)
- [📊 Model performance](#-model-performance)
- [🏗️ Architecture](#️-architecture)
- [📋 Environment variables](#-environment-variables)
- [📁 Project structure](#-project-structure)
- [📡 API endpoints](#-api-endpoints)
- [🧪 Testing](#-testing)
- [🗺️ Roadmap](#️-roadmap)
- [🤝 Contributing](#-contributing)
- [📬 Support](#-support)
- [License](#license)

---

## What it does

FraudLens predicts fraudulent credit-card transactions and explains every decision: a supervised model's probability, a per-feature SHAP breakdown, a plain-English LLM narrative, and a RAG-based retrieval of similar past cases to ground the alert in precedent.

> [!NOTE] The pipeline is staged so a run can stop at the deterministic risk score (fast, offline) or continue to a full explanation (LLM + RAG, needs keys).

## Screenshots

> To add screenshots: run `make dashboard`, capture your screen, save images to `docs/assets/`, and reference them below.
>
> **Suggested screenshots:**
> - Streamlit dashboard live-monitor page
> - SHAP explanation for a flagged transaction
> - Model comparison charts

---

## ✨ Features

| Feature | Description |
| --- | --- |
| 🎯 **Fraud detection** | XGBoost + ensemble models trained to flag fraudulent transactions |
| 🔍 **SHAP explainability** | Per-feature contribution for every prediction |
| 📝 **LLM narratives** | Plain-English explanation of why a transaction was flagged |
| 📚 **RAG case retrieval** | Retrieval of the most similar past cases to ground each alert |
| 🖥️ **Streamlit dashboard** | Live monitoring of detections, SHAP views, and case history |
| 📡 **REST API** | Predict + explanation endpoints under `/api/v1/` |

## 📊 Model performance

> [!IMPORTANT] The following numbers are the project's reported results on its held-out test split and should be treated as the benchmark to reproduce, not a general guarantee. If you re-run the evaluation, record results on the same split and compare deterministically.

| Model | Test ROC-AUC | PR-AUC | Notes |
| --- | --- | --- | --- |
| Logistic Regression | — | — | Baseline |
| Random Forest | — | — | Baseline |
| XGBoost (tuned) | — | — | Primary model |

> [!CAUTION] Model cards, exact test-set metrics, and the train/validation split are maintained in `model_cards.md`/`reports/` so the README never drifts from the reproduced numbers. Add a `model_cards.md` + CI check if this is still aspirational.

## 🏗️ Architecture

```text
FraudLens/
├── src/
│   ├── data/                 # Load + preprocessing (+ imbalanced-learn)
│   ├── features/             # Feature engineering + leakage guards
│   ├── models/               # XGBoost + ensemble + calibration
│   ├── explain/              # SHAP + LLM narrative generator
│   ├── rag/                  # Case retrieval (embeddings + similarity)
│   ├── dashboard/            # Streamlit live-monitor app
│   ├── api/                  # FastAPI prediction endpoints
│   └── train.py              # Full training + eval script
├── model_cards.md
├── reports/                  # Held-out metrics
├── requirements.txt
└── README.md
```

The key anti-leakage rule: every feature is computed **strictly on the training split**; the test split is never used to fit scalers, encoders, or the train-time pipeline (see `features/pipeline.py`'s `fit` on train, `transform` on test).

## 📋 Environment variables

| Variable | Default | Required | Description |
| --- | --- | --- | --- |
| `DATABASE_URL` | `sqlite:///fraudlens.db` | No | Where the labeled transaction log lives |
| `MODELS_PATH` | `models/` | No | Directory for serialized model artifacts |
| `EMBEDDINGS_PATH` | `embeddings/` | No | Precomputed case-embedding store for RAG |
| `OPENAI_API_KEY` | — | No | LLM narrative + RAG embeddings |
| `HF_TOKEN` | — | No | Hugging Face for sentence-transformers |
| `CACHE_DIR` | `cache/` | No | Local cache for offline demo mode |

## 📁 Project structure

```
Credit Card Fraud Detection/
├── src/
│   ├── data/
│   ├── features/
│   ├── models/
│   ├── explain/
│   ├── rag/
│   ├── dashboard/
│   └── api/
├── model_cards.md
├── reports/
├── requirements.txt
└── README.md
```

## 📡 API endpoints

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/predict` | Return the fraud probability + SHAP breakdown for one transaction |
| `POST` | `/api/v1/explain` | Return the LLM narrative + RAG case summary for one transaction |
| `GET` | `/health` | Health check |

### Example usage

```bash
# Classify one transaction and print the explanation
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

## 🧪 Testing

```bash
# Run the test suite
pytest tests/ -v
```

> [!NOTE] CI enforces **>=75% test coverage** on the `src/` package.

## 🗺️ Roadmap

> [!CAUTION] Checked items are built and verified. Unchecked items are tracked in the issue tracker.

- [x] XGBoost + ensemble baselines
- [x] SHAP explainability per prediction
- [x] LLM narrative generation
- [x] RAG case retrieval for alerts
- [x] Streamlit dashboard
- [x] FastAPI REST API
- [ ] Synthetic data generator for dev (tracked public issue)

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## 📬 Support

- 🐛 [Report a bug](https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/issues)
- 💡 [Request a feature](https://github.com/themanoj-025/Credit-Card-Fraud-Detection-System/issues)
- 📧 Email the maintainer via the issue tracker

## License

MIT License — see [LICENSE](LICENSE).
