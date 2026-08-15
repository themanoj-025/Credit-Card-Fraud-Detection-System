"""
FraudLens — Prometheus Metrics Configuration

Exposes metrics at /metrics endpoint for Prometheus scraping.
Uses prometheus-fastapi-instrumentator for automatic request metrics
and adds custom FraudLens-specific metrics.

Custom metrics:
- fraudlens_prediction_total{outcome="fraud|legitimate"}
- fraudlens_prediction_latency_ms
- fraudlens_shap_latency_ms
- fraudlens_llm_latency_ms
- fraudlens_cache_hit_total
- fraudlens_model_loaded{gauge}

Usage:
    from api.metrics import setup_metrics, PREDICTION_COUNTER
    PREDICTION_COUNTER.labels(outcome="fraud").inc()
"""

from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

# Custom FraudLens Metrics

# Prediction outcomes
PREDICTION_COUNTER = Counter(
    "fraudlens_prediction_total",
    "Total number of predictions by outcome",
    labelnames=["outcome"],
)

# Prediction latency (ms)
PREDICTION_LATENCY = Histogram(
    "fraudlens_prediction_latency_ms",
    "Prediction latency in milliseconds",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000],
)

# SHAP computation latency (ms)
SHAP_LATENCY = Histogram(
    "fraudlens_shap_latency_ms",
    "SHAP computation latency in milliseconds",
    buckets=[10, 50, 100, 250, 500, 1000, 2000, 5000],
)

# LLM call latency (ms)
LLM_LATENCY = Histogram(
    "fraudlens_llm_latency_ms",
    "LLM call latency in milliseconds",
    buckets=[100, 250, 500, 1000, 2000, 5000, 10000],
)

# Cache hits (should be rare — fraud models rarely see duplicate txns)
CACHE_HIT_COUNTER = Counter(
    "fraudlens_cache_hit_total",
    "Total number of prediction cache hits",
)

# Model loaded gauge (1 = loaded, 0 = not loaded)
MODEL_LOADED_GAUGE = Gauge(
    "fraudlens_model_loaded",
    "Whether the ML model is currently loaded (1 = yes, 0 = no)",
)

# Anomaly detector gauge
ANOMALY_LOADED_GAUGE = Gauge(
    "fraudlens_anomaly_loaded",
    "Whether the anomaly detector is currently loaded (1 = yes, 0 = no)",
)

# LLM available gauge
LLM_AVAILABLE_GAUGE = Gauge(
    "fraudlens_llm_available",
    "Whether the LLM is available (1 = yes, 0 = no)",
)

# LLM Cost Tracking

LLM_COST_TOTAL = Counter(
    "fraudlens_llm_cost_usd_total",
    "Total LLM API cost in USD",
    labelnames=["model", "endpoint"],
)

LLM_TOKENS_TOTAL = Counter(
    "fraudlens_llm_tokens_total",
    "Total LLM tokens consumed",
    labelnames=["model", "endpoint", "type"],
)

LLM_CALLS_TOTAL = Counter(
    "fraudlens_llm_calls_total",
    "Total LLM API calls",
    labelnames=["model", "endpoint", "status"],
)


def setup_metrics(app: object) -> None:
    """Configure and attach Prometheus metrics to the FastAPI app.

    Adds the /metrics endpoint and configures automatic instrumentation
    for request count, latency histograms, and per-endpoint breakdowns.

    Args:
        app: The FastAPI application instance

    Returns:
        The configured Instrumentator instance
    """
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        env_var_name="DISABLE_METRICS",
    )

    instrumentator.instrument(app).expose(app, endpoint="/metrics")
