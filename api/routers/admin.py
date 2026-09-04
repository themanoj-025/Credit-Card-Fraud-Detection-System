"""
FraudLens API — Admin Router

Administrative endpoints for API key management.
Accessible only with admin-level API keys.
"""

import hashlib
import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

try:
    from sqlalchemy.exc import SQLAlchemyError
except ImportError:
    SQLAlchemyError = Exception

from api.auth import require_admin_key
from api.rate_limit import limiter
from src.fraudlens.llm.cost_tracker import CostTracker, cost_tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["admin"])


class GenerateKeyRequest(BaseModel):
    """Request to generate a new API key."""

    role: str = "readonly"  # "admin" or "readonly"
    description: str = ""


class GeneratedKey(BaseModel):
    """Response containing a newly generated API key."""

    api_key: str
    role: str
    description: str
    sha256_hash: str


class KeyListResponse(BaseModel):
    """Response listing all configured API keys (hashes only)."""

    keys: list[dict[str, str]]
    count: int


@router.post("/keys", response_model=GeneratedKey)
@limiter.limit("10/hour")
async def generate_api_key(
    request: Request,
    key_request: GenerateKeyRequest,
    _admin_key: str = Depends(require_admin_key),
) -> GeneratedKey:
    """
    Generate a new API key.

    This endpoint returns the raw API key ONCE — it cannot be retrieved
    again. Store it securely. The key is hashed with SHA-256 before storage.

    Requires an admin-level API key in the X-API-Key header.
    """
    if key_request.role not in ("admin", "readonly"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role must be 'admin' or 'readonly'",
        )

    # Generate a cryptographically secure random key
    raw_key = f"fl_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    # In a production system, this would store the hash in a database.
    # For this dev-focused implementation, we output the config line
    # that should be added to the FRAUDLENS_API_KEYS environment variable.
    config_line = f"{key_hash}={key_request.role}"

    logger.info(
        "Generated new API key (role=%s). Add to FRAUDLENS_API_KEYS: %s",
        key_request.role,
        config_line,
    )

    return GeneratedKey(
        api_key=raw_key,
        role=key_request.role,
        description=key_request.description,
        sha256_hash=key_hash,
    )


@router.get("/keys", response_model=KeyListResponse)
@limiter.limit("30/minute")
async def list_api_keys(
    request: Request,
    _admin_key: str = Depends(require_admin_key),
) -> KeyListResponse:
    """
    List all configured API keys (shows hashes only, not raw keys).

    Requires an admin-level API key.
    """
    config = os.environ.get("FRAUDLENS_API_KEYS", "")
    keys = []

    for entry in config.split(";"):
        entry = entry.strip()
        if "=" in entry:
            hash_val, role = entry.split("=", 1)
            keys.append({"sha256_hash": hash_val, "role": role})

    return KeyListResponse(keys=keys, count=len(keys))


# LLM Usage Endpoint


class LLMUsageResponse(BaseModel):
    """LLM cost and usage summary."""

    date: str
    total_cost_usd: float
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    by_model: dict[str, float]
    by_endpoint: dict[str, float]


class LLMUsagePeriod(BaseModel):
    """Period selector for LLM usage."""

    period: str = "today"  # "today", "month", "total"


@router.get("/llm-usage", response_model=LLMUsageResponse)
@limiter.limit("30/minute")
async def get_llm_usage(
    request: Request,
    period: str = "today",
    _admin_key: str = Depends(require_admin_key),
) -> LLMUsageResponse:
    """
    Get LLM API cost and usage summary.

    Merges data from:
    - In-memory CostTracker (recent calls since server start)
    - Database llm_calls table (historical data that survives restarts)

    Query param `period`: today | month | total
    Requires an admin-level API key.
    """
    # Step 1: Get in-memory summary (recent, not yet persisted)
    memory_summary = cost_tracker.get_period_summary_dict(period)
    pending_records = cost_tracker.get_pending_records()

    # Step 2: Persist pending records to DB so they survive restarts
    db_summary = None
    try:
        from datetime import UTC, datetime

        from src.fraudlens.persistence import get_session
        from src.fraudlens.persistence.repositories import LlmCallRepository

        now = datetime.now(UTC)
        if period == "today":
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "month":
            since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            since = datetime(2020, 1, 1)  # far past for "total"

        async for session in get_session():
            repo = LlmCallRepository(session)

            # Flush pending in-memory records to DB
            for record in pending_records:
                try:
                    await repo.create_call(
                        model=record.model,
                        endpoint=record.endpoint,
                        input_tokens=record.input_tokens,
                        output_tokens=record.output_tokens,
                        cost_usd=record.cost_usd,
                        status=record.status,
                    )
                except (SQLAlchemyError, OSError) as e:
                    logger.warning("Failed to persist LLM call record: %s", e)

            await session.commit()

            # Now query DB for the requested period
            db_summary = await repo.get_period_summary(since)
            break

        # Clear in-memory records that were just persisted
        cost_tracker.clear_pending()

        # Re-read memory summary — now only has records created during/after flush
        memory_summary = cost_tracker.get_period_summary_dict(period)
    except (SQLAlchemyError, OSError) as e:
        logger.warning("DB cost query failed, using in-memory only: %s", e)

    # Step 3: Merge DB (historical) + in-memory (records created during flush)
    if db_summary:
        merged = CostTracker.merge_summaries(memory_summary, db_summary)
    else:
        merged = memory_summary

    return LLMUsageResponse(
        date=merged["date"],
        total_cost_usd=merged["total_cost_usd"],
        total_calls=merged["total_calls"],
        total_input_tokens=merged["total_input_tokens"],
        total_output_tokens=merged["total_output_tokens"],
        by_model=merged.get("by_model", {}),
        by_endpoint=merged.get("by_endpoint", {}),
    )
