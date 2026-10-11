# FLAGGED CANDIDATES: Credit Card Fraud Detection

These items require human review before any destructive action would be permissible.

| ID | Path / Candidate | Tier | Score | Category | Human Review Question |
|---|---|---|---|---|---|
| CAND-0001 | `alembic/versions/__init__.py` | T3 | 30 | Cat A | Retain due to Database Migration? |
| CAND-0003 | `models/.gitkeep` | T3 | 30 | Cat A | Retain due to Directory Preservation Marker? |
| CAND-0066 | `api/routers/models_admin.py` | T2 | 68 | Cat D | Is `api/routers/models_admin.py` loaded dynamically or needed externally? |
| CAND-0067 | `api/routers/similar_cases.py` | T2 | 68 | Cat D | Is `api/routers/similar_cases.py` loaded dynamically or needed externally? |
| CAND-0068 | `app/logging/structured_logging.py` | T2 | 68 | Cat D | Is `app/logging/structured_logging.py` loaded dynamically or needed externally? |
| CAND-0069 | `app/pages/analyst_copilot.py` | T2 | 68 | Cat D | Is `app/pages/analyst_copilot.py` loaded dynamically or needed externally? |
| CAND-0070 | `app/pages/case_investigator.py` | T2 | 68 | Cat D | Is `app/pages/case_investigator.py` loaded dynamically or needed externally? |
| CAND-0071 | `app/pages/governance_tabs.py` | T2 | 68 | Cat D | Is `app/pages/governance_tabs.py` loaded dynamically or needed externally? |
| CAND-0072 | `app/pages/live_monitor.py` | T2 | 68 | Cat D | Is `app/pages/live_monitor.py` loaded dynamically or needed externally? |
| CAND-0073 | `app/pages/model_performance.py` | T2 | 68 | Cat D | Is `app/pages/model_performance.py` loaded dynamically or needed externally? |
| CAND-0074 | `notebooks/01_eda.ipynb` | T2 | 68 | Cat D | Is `notebooks/01_eda.ipynb` loaded dynamically or needed externally? |
| CAND-0075 | `notebooks/02_preprocessing.ipynb` | T2 | 68 | Cat D | Is `notebooks/02_preprocessing.ipynb` loaded dynamically or needed externally? |
| CAND-0076 | `notebooks/03_modeling.ipynb` | T2 | 68 | Cat D | Is `notebooks/03_modeling.ipynb` loaded dynamically or needed externally? |
| CAND-0077 | `notebooks/04_explainability.ipynb` | T2 | 68 | Cat D | Is `notebooks/04_explainability.ipynb` loaded dynamically or needed externally? |
| CAND-0078 | `pipeline_charts.py` | T2 | 68 | Cat D | Is `pipeline_charts.py` loaded dynamically or needed externally? |
| CAND-0079 | `src/fraudlens/persistence/repositories/api_keys.py` | T2 | 68 | Cat D | Is `src/fraudlens/persistence/repositories/api_keys.py` loaded dynamically or needed externally? |
| CAND-0080 | `src/fraudlens/persistence/repositories/llm_calls.py` | T2 | 68 | Cat D | Is `src/fraudlens/persistence/repositories/llm_calls.py` loaded dynamically or needed externally? |
| CAND-0081 | `src/fraudlens/persistence/repositories/model_candidates.py` | T2 | 68 | Cat D | Is `src/fraudlens/persistence/repositories/model_candidates.py` loaded dynamically or needed externally? |
| CAND-0082 | `src/fraudlens/persistence/repositories/predictions.py` | T2 | 68 | Cat D | Is `src/fraudlens/persistence/repositories/predictions.py` loaded dynamically or needed externally? |
| CAND-0083 | `src/fraudlens/retraining/retrain_models.py` | T2 | 68 | Cat D | Is `src/fraudlens/retraining/retrain_models.py` loaded dynamically or needed externally? |
| CAND-0084 | `tests/test_anomaly.py` | T2 | 68 | Cat D | Is `tests/test_anomaly.py` loaded dynamically or needed externally? |
| CAND-0085 | `tests/test_api.py` | T2 | 68 | Cat D | Is `tests/test_api.py` loaded dynamically or needed externally? |
| CAND-0086 | `tests/test_base_repository.py` | T2 | 68 | Cat D | Is `tests/test_base_repository.py` loaded dynamically or needed externally? |
| CAND-0087 | `tests/test_business_cost.py` | T2 | 68 | Cat D | Is `tests/test_business_cost.py` loaded dynamically or needed externally? |
| CAND-0088 | `tests/test_database.py` | T2 | 68 | Cat D | Is `tests/test_database.py` loaded dynamically or needed externally? |
| CAND-0089 | `tests/test_dataloaders.py` | T2 | 68 | Cat D | Is `tests/test_dataloaders.py` loaded dynamically or needed externally? |
| CAND-0090 | `tests/test_drift.py` | T2 | 68 | Cat D | Is `tests/test_drift.py` loaded dynamically or needed externally? |
| CAND-0091 | `tests/test_eda.py` | T2 | 68 | Cat D | Is `tests/test_eda.py` loaded dynamically or needed externally? |
| CAND-0092 | `tests/test_engineering.py` | T2 | 68 | Cat D | Is `tests/test_engineering.py` loaded dynamically or needed externally? |
| CAND-0093 | `tests/test_hpo.py` | T2 | 68 | Cat D | Is `tests/test_hpo.py` loaded dynamically or needed externally? |
| CAND-0094 | `tests/test_llm_case_narrator.py` | T2 | 68 | Cat D | Is `tests/test_llm_case_narrator.py` loaded dynamically or needed externally? |
| CAND-0095 | `tests/test_llm_case_narrator_part2.py` | T2 | 68 | Cat D | Is `tests/test_llm_case_narrator_part2.py` loaded dynamically or needed externally? |
| CAND-0096 | `tests/test_metrics.py` | T2 | 68 | Cat D | Is `tests/test_metrics.py` loaded dynamically or needed externally? |
| CAND-0097 | `tests/test_model_selection.py` | T2 | 68 | Cat D | Is `tests/test_model_selection.py` loaded dynamically or needed externally? |
| CAND-0098 | `tests/test_persistence_repositories.py` | T2 | 68 | Cat D | Is `tests/test_persistence_repositories.py` loaded dynamically or needed externally? |
| CAND-0099 | `tests/test_preprocessing.py` | T2 | 68 | Cat D | Is `tests/test_preprocessing.py` loaded dynamically or needed externally? |
| CAND-0100 | `tests/test_rag_similar_cases.py` | T2 | 68 | Cat D | Is `tests/test_rag_similar_cases.py` loaded dynamically or needed externally? |
| CAND-0101 | `tests/test_retrain_trigger_part2.py` | T2 | 68 | Cat D | Is `tests/test_retrain_trigger_part2.py` loaded dynamically or needed externally? |
| CAND-0102 | `tests/test_shap_utils.py` | T2 | 68 | Cat D | Is `tests/test_shap_utils.py` loaded dynamically or needed externally? |
| CAND-0103 | `tests/test_train.py` | T2 | 68 | Cat D | Is `tests/test_train.py` loaded dynamically or needed externally? |
