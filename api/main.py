"""
FraudLens API — FastAPI Application

Production-grade REST API for credit card fraud detection with:
- Single & batch prediction
- SHAP explainability
- LLM case narration
- RAG similar-case retrieval
- Analyst copilot chat

Security:
- API key authentication via X-API-Key header
- Rate limiting (slowapi + Redis)
- CORS restricted to known origins
- Security headers on all responses

Observability:
- Structured JSON logging (structlog) with correlation IDs
- Prometheus metrics at /metrics
- OpenTelemetry tracing exported to Jaeger
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Observability — initialize structlog before anything else
from api.logging_config import get_logger, setup_structlog

setup_structlog()
logger = get_logger(__name__)

from api.auth import is_auth_enabled
from api.metrics import setup_metrics
from api.providers import (
    FraudPredictor,
    get_predictor,
)
from api.rate_limit import limiter
from api.routers import (
    admin,
    chat,
    explain,
    models_admin,
    predict,
    similar_cases,
)
from src.fraudlens.config import AVG_FRAUD_LOSS, MODELS_DIR, REVIEW_COST
from src.fraudlens.explainability.shap_explainer import ShapExplainer
from src.fraudlens.llm.case_narrator import CaseNarrator
from src.fraudlens.llm.rag_similar_cases import SimilarCaseRetriever
from src.fraudlens.persistence import init_db
from src.fraudlens.prediction.model_loader import ModelLoader

# Attempt to load optional dependencies


def _try_load_copilot(app: FastAPI) -> Any:
    """Try to load Anthropic client for copilot features."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        try:
            from anthropic import Anthropic

            app.state.copilot_client = Anthropic(api_key=api_key)
            logger.info("Analyst Copilot initialized")
        except ImportError:
            logger.warning("anthropic package not installed. Copilot unavailable.")
    else:
        logger.info("ANTHROPIC_API_KEY not set. Copilot unavailable.")


def _try_load_case_narrator(app: FastAPI) -> Any:
    """Try to load the case narrator."""
    try:
        app.state.case_narrator = CaseNarrator()
        logger.info("Case Narrator initialized")
    except (OSError, ValueError, ImportError) as e:
        logger.warning("Case Narrator unavailable: %s", e)


def _try_load_rag_retriever(app: FastAPI) -> Any:
    """Try to load the RAG-based similar case retriever."""
    index_path = MODELS_DIR / "rag_index"
    if index_path.exists():
        try:
            retriever = SimilarCaseRetriever()
            retriever.load(str(index_path))
            app.state.case_retriever = retriever
            logger.info("RAG retriever loaded from %s", index_path)
        except (OSError, ValueError, ImportError) as e:
            logger.warning("RAG retriever unavailable: %s", e)
    else:
        logger.info("No RAG index found at %s", index_path)


# Lifecycle


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Load models and dependencies on startup into app.state."""
    logger.info("Starting FraudLens API v2.0.0...")

    if is_auth_enabled():
        logger.info("API key authentication enabled")
    else:
        logger.warning(
            "API key authentication DISABLED — set FRAUDLENS_API_KEYS to enable"
        )

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except (OSError, ImportError) as e:
        logger.warning("Database initialization failed: %s", e)

    # Load supervised model via new DI-friendly architecture
    try:
        model_loader = ModelLoader(verify_checksum=True)
        model_loader.load_all()
        shap_explainer = ShapExplainer()
        predictor = FraudPredictor(
            model_loader=model_loader, shap_explainer=shap_explainer
        )
        app.state.predictor = predictor
        logger.info(
            "Model loaded successfully (threshold=%.4f)", model_loader.threshold
        )
    except (OSError, ValueError, ImportError) as e:
        logger.warning("Failed to load model: %s", e)
        app.state.predictor = None

    # Load anomaly detector
    try:
        anomaly_path = MODELS_DIR / "anomaly_detector.pkl"
        if anomaly_path.exists():
            import joblib

            app.state.anomaly_detector = joblib.load(anomaly_path)
            logger.info("Anomaly detector loaded")
        else:
            app.state.anomaly_detector = None
    except (OSError, ValueError, ImportError) as e:
        logger.warning("Failed to load anomaly detector: %s", e)
        app.state.anomaly_detector = None

    # Load optional features into app.state
    app.state.case_narrator = None
    app.state.case_retriever = None
    app.state.copilot_client = None
    _try_load_case_narrator(app)
    _try_load_rag_retriever(app)
    _try_load_copilot(app)

    # Wire circuit breaker into case narrator
    from api.exceptions import circuit_breaker

    app.state.llm_circuit_breaker = circuit_breaker
    case_narrator = getattr(app.state, "case_narrator", None)
    if case_narrator is not None:
        case_narrator.set_circuit_breaker(circuit_breaker)

    # Update Prometheus gauges with current state
    from api.metrics import (
        ANOMALY_LOADED_GAUGE,
        LLM_AVAILABLE_GAUGE,
        MODEL_LOADED_GAUGE,
    )

    MODEL_LOADED_GAUGE.set(
        1 if getattr(app.state, "predictor", None) is not None else 0
    )
    ANOMALY_LOADED_GAUGE.set(
        1 if getattr(app.state, "anomaly_detector", None) is not None else 0
    )
    LLM_AVAILABLE_GAUGE.set(
        1 if getattr(app.state, "copilot_client", None) is not None else 0
    )

    logger.info("FraudLens API ready")
    yield


# App Creation (must be before any @app decorators)

app = FastAPI(
    title="FraudLens API",
    description="Production-grade credit card fraud detection with SHAP explainability, "
    "LLM case narration, and RAG-based similar case retrieval.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "admin",
            "description": "Admin authentication and API key management",
        },
        {
            "name": "predictions",
            "description": "Single and batch fraud prediction with probability scores",
        },
        {
            "name": "explainability",
            "description": "SHAP-based feature importance and prediction explanations",
        },
        {
            "name": "rag",
            "description": "RAG-based similar case retrieval for fraud investigation",
        },
        {
            "name": "copilot",
            "description": "LLM-powered analyst copilot chat for fraud case analysis",
        },
        {
            "name": "admin-models",
            "description": "Model registry management (list, compare, promote models)",
        },
    ],
)

# --- OpenTelemetry distributed tracing (OTEL_ENABLED=true) ---
try:
    from fraudlens.tracing import setup_tracing
    _otel_ok = setup_tracing("ccfd-api")
    if _otel_ok:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
except ImportError:
    pass

# Register rate limit error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Correlation ID Middleware


@app.middleware("http")
async def add_correlation_id(request, call_next) -> Any:
    """Inject X-Request-ID correlation ID into every request.

    Reads from request header or generates a new one. Sets it in structlog
    context vars and returns it in the response header.
    """
    from api.logging_config import generate_correlation_id, set_correlation_id

    cid = request.headers.get("X-Request-ID", generate_correlation_id())
    set_correlation_id(cid)

    response = await call_next(request)
    response.headers["X-Request-ID"] = cid
    return response


# Register RFC 7807 error handlers
from api.errors import register_error_handlers

register_error_handlers(app)

# CORS (locked to explicit origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type", "Authorization"],
)

# Rate Limiting Middleware

app.add_middleware(SlowAPIMiddleware)


# Security Headers


@app.middleware("http")
async def add_security_headers(request, call_next) -> Any:
    """Add security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none';"
    )
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


# Routes (with optional auth)

app.include_router(admin.router)
app.include_router(predict.router)
app.include_router(explain.router)
app.include_router(similar_cases.router)
app.include_router(chat.router)
app.include_router(models_admin.router)

# Observability: Metrics & Tracing (AFTER all routes are registered)

# Setup Prometheus metrics
setup_metrics(app)
logger.info("Prometheus metrics enabled at /metrics")

# Setup OpenTelemetry tracing (must be after routes for auto-instrumentation)
from api.tracing import setup_tracing

setup_tracing(app)


@app.get("/health")
@app.get("/v1/health")
async def health() -> Any:
    """Health check endpoint. No auth required.

    Returns per-dependency status breakdown for monitoring and orchestration.
    Each dependency reports its own status: ok, degraded, or error.
    """
    pred = get_predictor()
    llm_available = getattr(app.state, "copilot_client", None) is not None
    case_narrator = getattr(app.state, "case_narrator", None) is not None
    case_retriever = getattr(app.state, "case_retriever", None) is not None
    anomaly_det = getattr(app.state, "anomaly_detector", None) is not None
    db_initialized = True  # Assume ok — init failures logged at startup

    # Build per-dependency breakdown
    model_ok = pred is not None and hasattr(pred, "model") and pred.model is not None
    dependencies = {
        "model": {
            "status": "ok" if model_ok else "degraded",
            "detail": (
                f"{type(pred.model).__name__} (threshold={pred.threshold:.4f})"
                if model_ok
                else "not loaded"
            ),
        },
        "database": {
            "status": "ok" if db_initialized else "error",
            "detail": "connected" if db_initialized else "disconnected",
        },
        "anomaly_detector": {
            "status": "ok" if anomaly_det else "degraded",
            "detail": "loaded" if anomaly_det else "not loaded",
        },
        "llm": {
            "status": "ok" if llm_available else "degraded",
            "detail": "connected" if llm_available else "API key not set",
        },
        "case_narrator": {
            "status": "ok" if case_narrator else "degraded",
            "detail": "loaded" if case_narrator else "not loaded",
        },
        "rag_retriever": {
            "status": "ok" if case_retriever else "degraded",
            "detail": "loaded" if case_retriever else "no index found",
        },
    }

    # Overall status: ok if all dependencies are ok, degraded otherwise
    all_ok = all(d["status"] == "ok" for d in dependencies.values())
    overall = "healthy" if all_ok else "degraded"

    return {
        "status": overall,
        "version": "2.0.0",
        "auth_enabled": is_auth_enabled(),
        "dependencies": dependencies,
    }


@app.get("/model-info")
async def model_info() -> Any:
    """Get model metadata and configuration."""
    pred = get_predictor()
    if pred is None:
        return {"status": "model not loaded"}

    return {
        "model_type": type(pred.model).__name__ if pred.model else None,
        "threshold": pred.threshold,
        "n_features": len(pred.feature_names or []),
        "features": pred.feature_names,
        "avg_fraud_loss": AVG_FRAUD_LOSS,
        "review_cost": REVIEW_COST,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
