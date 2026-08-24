"""
FraudLens — OpenTelemetry Tracing Configuration

Provides distributed tracing across API → predictor → DB → LLM calls.
Exports traces to Jaeger (or any OTLP-compatible backend) via OTLP.

Usage:
    from api.tracing import setup_tracing, get_tracer

    tracer = get_tracer("fraudlens.prediction")
    with tracer.start_as_current_span("predict_single") as span:
        span.set_attribute("fraud_probability", 0.92)
        result = predictor.predict_single(transaction)
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# OTLP exporter is optional — gracefully degrade if not installed
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    _HAS_OTLP = True
except ImportError:
    OTLPSpanExporter = None  # type: ignore
    _HAS_OTLP = False

# FastAPI instrumentation is optional
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    _HAS_FASTAPI_INSTR = True
except ImportError:
    FastAPIInstrumentor = None  # type: ignore
    _HAS_FASTAPI_INSTR = False

logger = logging.getLogger(__name__)

# Configuration

OTLP_ENDPOINT = os.environ.get("OTLP_ENDPOINT", "http://jaeger:4317")
SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "fraudlens-api")
TRACE_ENABLED = os.environ.get("ENABLE_TRACING", "true").lower() == "true"
TRACE_CONSOLE = os.environ.get("TRACE_CONSOLE", "false").lower() == "true"


def setup_tracing(app: object) -> TracerProvider | None:
    """Configure OpenTelemetry tracing with Jaeger OTLP exporter.

    Sets up:
    - TracerProvider with service name and resource attributes
    - OTLP gRPC span exporter (to Jaeger)
    - Optional console span exporter (for debug)
    - FastAPI auto-instrumentation

    Args:
        app: The FastAPI application instance

    Returns:
        The TracerProvider instance, or None if tracing is disabled
    """
    if not TRACE_ENABLED:
        logger.info("OpenTelemetry tracing disabled (ENABLE_TRACING != true)")
        return None

    # Create resource with service metadata
    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": "2.0.0",
            "deployment.environment": os.environ.get("ENVIRONMENT", "development"),
        }
    )

    # Create tracer provider
    tracer_provider = TracerProvider(resource=resource)

    # Add OTLP gRPC exporter (to Jaeger) — optional dependency
    if _HAS_OTLP and OTLPSpanExporter is not None:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OTLP trace exporter configured: %s", OTLP_ENDPOINT)
        except (OSError, ConnectionError, ValueError) as e:
            logger.warning("Failed to configure OTLP exporter: %s", e)
    else:
        logger.info("OTLP exporter not available (install opentelemetry-exporter-otlp)")

    # Add console exporter for local debugging
    if TRACE_CONSOLE:
        tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("Console trace exporter enabled")

    # Set the global tracer provider
    trace.set_tracer_provider(tracer_provider)

    # Instrument FastAPI — optional dependency
    if _HAS_FASTAPI_INSTR and FastAPIInstrumentor is not None:
        try:
            FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
            logger.info("FastAPI auto-instrumentation enabled")
        except (OSError, ValueError, TypeError) as e:
            logger.warning("FastAPI instrumentation failed: %s", e)
    else:
        logger.info("FastAPI instrumentation not available")

    logger.info("OpenTelemetry tracing initialized (service=%s)", SERVICE_NAME)
    return tracer_provider


def get_tracer(name: str = "fraudlens") -> trace.Tracer:
    """Get a tracer for creating custom spans.

    Example:
        tracer = get_tracer("fraudlens.prediction")
        with tracer.start_as_current_span("predict_single") as span:
            span.set_attribute("feature_count", 30)
            result = predict(transaction)
    """
    return trace.get_tracer(name)
