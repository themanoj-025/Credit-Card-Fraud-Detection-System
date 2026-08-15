"""
FraudLens — Structured Logging Configuration

Replaces standard logging with structlog's JSON-formatted output.
Adds a correlation ID (X-Request-ID) threaded through every log line
for request tracing across services.

Usage:
    log = get_logger(__name__)
    log.info("model.loaded", model_type="xgboost", threshold=0.03)
"""

import json as json_lib
import logging
import os
import uuid
from typing import Any

import structlog

# Configuration

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.environ.get("LOG_FORMAT", "json")  # "json" or "console"


def setup_structlog() -> None:
    """Configure structlog as the logging backend.

    Call once at application startup. All loggers created with
    :func:`get_logger` will emit structured JSON lines.
    """
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    def _json_serializer(obj: Any, *args: Any, **kwargs: Any) -> str:
        """Safe JSON serializer that handles non-serializable types."""
        # Remove 'default' from kwargs if present to avoid duplicate kwarg error
        kwargs.pop("default", None)
        return json_lib.dumps(obj, default=str, *args, **kwargs)

    if LOG_FORMAT == "console":
        processors = shared_processors + [structlog.dev.ConsoleRenderer()]
    else:
        processors = shared_processors + [
            structlog.processors.JSONRenderer(serializer=_json_serializer),
        ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Set structlog as the root logger
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        force=True,
    )


def get_correlation_id() -> str:
    """Get the current correlation ID from structlog context vars."""
    ctx = structlog.contextvars.get_contextvars()
    return ctx.get("correlation_id", "")


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID in structlog context vars."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=cid)


def generate_correlation_id() -> str:
    """Generate a new correlation ID (short UUID)."""
    return uuid.uuid4().hex[:12]


def get_logger(name: str) -> Any:
    """Get a structlog logger for the given module name.

    Example:
        log = get_logger(__name__)
        log.info("prediction.computed", fraud_probability=0.92, latency_ms=1.2)
    """
    return structlog.get_logger(name)
