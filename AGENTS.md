# AGENTS.md — AI Card Detection

> Canonical project instructions. Pointers like `CLAUDE.md` or
> `.github/copilot-instructions.md` should say "See AGENTS.md".

---

## Project overview

**Credit Card Fraud Detection** — a machine-learning pipeline that scans
transaction data for fraudulent card activity. Core components:

- **Data** — raw + processed transaction batches (CSV/parquet).
- **Preprocessing** — cleaning, feature engineering, scaling.
- **Models** — fraud classifiers (e.g., XGBoost, RandomForest) with
  train/validation/eval scripts.
- **Dashboard** — Streamlit app for reviewing flagged transactions.

Stack: Python 3.11+ · pandas · scikit-learn · XGBoost · Streamlit · DVC.

---

## Exact commands

```bash
# Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Data (DVC)
dvc pull

# Lint / typecheck / test
make lint
pre-commit run --all-files
python -m mypy . --ignore-missing-imports
python -m pytest tests/ -v --cov=. --cov-fail-under=70

# Run
streamlit run dashboard/app.py
```

---

## Folder map

| Path | Purpose |
|------|---------|
| `data/` | Data (DVC-tracked) |
| `notebooks/` | Exploration / evaluation |
| `src/` | Preprocessing + model code |
| `dashboard/` | Streamlit dashboard |
| `tests/` | pytest suite |
| `.github/workflows/` | CI (ruff, mypy, pytest, gitleaks, trivy) |

## Do / don't

- **Do** keep secrets out of notebooks and data files.
- **Do not** commit `.dvc/config` (it holds remote pointers).
- **Do not** commit trained model artifacts (DVC handles them).

## Security rules

- No secrets in the repository; `gitleaks` CI gate gates on hits.
- Card numbers / PANs must be masked or tokenized before any file
  leaves the sandbox.

## AI-assistance convention

Commits authored by AI must carry the trailer:

```text
AI-Assisted: yes | no | partial
```

See `.gitmessage` for the template. Do not rewrite historic commits
retroactively.
