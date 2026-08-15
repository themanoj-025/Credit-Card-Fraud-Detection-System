"""
FraudLens API — RFC 7807 Problem Details Error Format

All API errors now conform to RFC 7807 (Problem Details for HTTP APIs),
providing consistent, machine-readable error responses.

Usage:
    from api.errors import ProblemDetail, problem_detail_handler

    # In routers:
    raise ProblemDetail(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Model not loaded",
    )

    # Register in app:
    app.add_exception_handler(ProblemDetail, problem_detail_handler)
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ProblemDetail(Exception):
    """
    RFC 7807 Problem Details for HTTP APIs.

    Attributes:
        status_code: HTTP status code
        type: URI reference identifying the problem type
        title: Short, human-readable summary
        detail: Human-readable explanation specific to this occurrence
        instance: URI reference identifying the specific occurrence
        errors: Optional list of field-level validation errors
    """

    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        type: str = "about:blank",
        title: str | None = None,
        detail: str = "An unexpected error occurred.",
        instance: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.type = type
        self.title = title or _DEFAULT_TITLES.get(status_code, "Unknown Error")
        self.detail = detail
        self.instance = instance
        self.errors = errors
        super().__init__(detail)


# Default titles per HTTP status code
_DEFAULT_TITLES: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    503: "Service Unavailable",
}


class ProblemDetailResponse(BaseModel):
    """RFC 7807 response schema for OpenAPI documentation."""

    type: str = Field(
        "about:blank",
        description="URI reference identifying the problem type",
    )
    title: str = Field(..., description="Short, human-readable problem summary")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Human-readable explanation")
    instance: str | None = Field(
        None, description="URI reference to the specific occurrence"
    )
    errors: list[dict[str, Any]] | None = Field(
        None, description="Field-level validation errors"
    )


def problem_detail_handler(request: Request, exc: ProblemDetail) -> JSONResponse:
    """Exception handler for ProblemDetail exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": exc.type,
            "title": exc.title,
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": exc.instance or str(request.url.path),
            "errors": exc.errors,
        },
    )


def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert Pydantic validation errors to RFC 7807 format."""
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": " -> ".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "type": "https://docs.fraudlens.dev/errors/validation-error",
            "title": "Validation Error",
            "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "detail": "Request validation failed. See errors for details.",
            "instance": str(request.url.path),
            "errors": errors,
        },
    )


def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert standard HTTPException to RFC 7807 format."""
    from fastapi import HTTPException

    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": "about:blank",
                "title": _DEFAULT_TITLES.get(exc.status_code, "Error"),
                "status": exc.status_code,
                "detail": exc.detail,
                "instance": str(request.url.path),
                "errors": None,
            },
            headers=exc.headers,
        )

    # Fallback for unhandled exceptions
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "type": "about:blank",
            "title": "Internal Server Error",
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "detail": "An unexpected error occurred.",
            "instance": str(request.url.path),
            "errors": None,
        },
    )


def register_error_handlers(app: "FastAPI") -> None:
    """Register all RFC 7807 error handlers on a FastAPI app."""
    from fastapi import HTTPException

    app.add_exception_handler(ProblemDetail, problem_detail_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Generic 500 fallback
    app.add_exception_handler(Exception, http_exception_handler)
