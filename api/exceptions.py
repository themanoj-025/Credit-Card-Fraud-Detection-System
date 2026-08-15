"""
FraudLens — Typed Exceptions & Circuit Breaker

Domain-specific exceptions for clean error handling and a simple
circuit breaker for LLM calls to prevent cascading failures.

All exceptions inherit from FastAPI's HTTPException so that they
automatically produce the correct HTTP status codes without needing
custom exception handlers.

Usage:
    from api.exceptions import (
        ModelNotLoadedError, LLMServiceUnavailable,
        LLMCircuitBreaker, circuit_breaker
    )

    if predictor is None:
        raise ModelNotLoadedError()

    if circuit_breaker.is_open():
        raise LLMServiceUnavailable("LLM temporarily unavailable")
"""

import logging
import time

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


# Domain-Specific Exceptions (inherit from HTTPException for correct status)


class ModelNotLoadedError(HTTPException):
    """Raised when the ML model is not loaded in the current app state.

    Automatically produces HTTP 503 Service Unavailable.
    """

    def __init__(self, detail: str = "Fraud detection model not loaded"):
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


class LLMServiceUnavailable(HTTPException):
    """Raised when the LLM (Anthropic) is unreachable or not configured.

    Automatically produces HTTP 503. Callers should fall back to
    template-based narratives rather than failing the entire request.
    """

    def __init__(self, detail: str = "LLM service unavailable"):
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


class PredictionError(HTTPException):
    """Raised when a prediction fails.

    Automatically produces HTTP 500 Internal Server Error.
    """

    def __init__(
        self,
        detail: str = "Model prediction failed",
        original: Exception | None = None,
    ):
        self.original = original
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )


class RetrieverUnavailable(HTTPException):
    """Raised when the RAG retriever is not initialized.

    Automatically produces HTTP 503.
    """

    def __init__(self, detail: str = "Case retriever not initialized"):
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


class InvalidInputError(HTTPException):
    """Raised when input validation fails beyond Pydantic's checks.

    Automatically produces HTTP 422.
    """

    def __init__(self, detail: str = "Invalid input", errors: list | None = None):
        self.errors = errors or []
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
        )


# Circuit Breaker for LLM Calls


class LLMCircuitBreaker:
    """Simple circuit breaker for LLM API calls.

    Prevents cascading failures by temporarily disabling LLM calls
    after a configurable number of consecutive failures.

    States:
        CLOSED: Normal operation — LLM calls proceed
        OPEN: LLM calls are blocked (fail fast)
        HALF_OPEN: Trial request to check if LLM recovered
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        cooldown_multiplier: float = 2.0,
        name: str = "llm",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.cooldown_multiplier = cooldown_multiplier
        self.name = name

        self._failure_count = 0
        self._state = "CLOSED"
        self._last_open_time = 0.0
        self._current_timeout = recovery_timeout

    def is_open(self) -> bool:
        """Check if the circuit breaker is open (LLM calls blocked)."""
        if self._state == "CLOSED":
            return False

        if self._state == "OPEN":
            if time.monotonic() - self._last_open_time >= self._current_timeout:
                self._state = "HALF_OPEN"
                logger.info(
                    "Circuit breaker '%s' half-open — allowing trial request",
                    self.name,
                )
                return False
            return True

        return False  # HALF_OPEN — allow trial request

    def record_success(self) -> None:
        """Record a successful LLM call. Resets the circuit breaker."""
        self._failure_count = 0
        self._state = "CLOSED"
        self._current_timeout = self.recovery_timeout
        logger.info("Circuit breaker '%s' closed — LLM available", self.name)

    def record_failure(self) -> None:
        """Record a failed LLM call. May open the circuit breaker."""
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._state = "OPEN"
            self._last_open_time = time.monotonic()
            self._current_timeout *= self.cooldown_multiplier
            logger.warning(
                "Circuit breaker '%s' OPEN after %d failures (timeout=%.1fs)",
                self.name,
                self._failure_count,
                self._current_timeout,
            )

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._failure_count = 0
        self._state = "CLOSED"
        self._current_timeout = self.recovery_timeout
        logger.info("Circuit breaker '%s' manually reset", self.name)


# Global circuit breaker instance for LLM calls
circuit_breaker = LLMCircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30.0,
    cooldown_multiplier=2.0,
    name="llm",
)
