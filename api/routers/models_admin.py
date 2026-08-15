"""
FraudLens API — Models Admin Router

Administrative endpoints for model lifecycle management:
- List candidate models pending review
- View detailed candidate metrics
- Promote a candidate to production
- Reject a candidate
- Compare candidate vs production metrics

All endpoints require admin-level API keys.
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from api.auth import require_admin_key
from api.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin/models", tags=["admin-models"])


# Pydantic Schemas


class ModelCandidateOut(BaseModel):
    """Detailed model candidate response."""

    model_version: str
    trigger: str
    trigger_detail: str | None = None
    pr_auc: float | None = None
    f1_score: float | None = None
    precision: float | None = None
    recall: float | None = None
    threshold: float | None = None
    mlflow_run_id: str | None = None
    status: str
    created_at: str
    promoted_at: str | None = None


class ModelCandidateListResponse(BaseModel):
    """Paginated list of model candidates."""

    candidates: list[ModelCandidateOut]
    total: int
    pending: int
    promoted: int
    rejected: int


class PromoteResponse(BaseModel):
    """Response after promoting a candidate."""

    success: bool
    model_version: str
    message: str
    candidate: ModelCandidateOut | None = None


class CompareResponse(BaseModel):
    """Comparison between candidate and production model."""

    current_production: ModelCandidateOut | None = None
    candidate: ModelCandidateOut | None = None
    metrics_delta: dict[str, float] | None = None


# Helper: Convert ORM to Pydantic


def _candidate_to_out(candidate: Any) -> ModelCandidateOut:
    """Convert a ModelCandidateModel instance to a Pydantic response."""
    return ModelCandidateOut(
        model_version=candidate.model_version,
        trigger=candidate.trigger,
        trigger_detail=candidate.trigger_detail,
        pr_auc=candidate.pr_auc,
        f1_score=candidate.f1_score,
        precision=candidate.precision,
        recall=candidate.recall,
        threshold=candidate.threshold,
        mlflow_run_id=candidate.mlflow_run_id,
        status=candidate.status,
        created_at=(
            candidate.created_at.isoformat()
            if hasattr(candidate.created_at, "isoformat")
            else str(candidate.created_at)
        ),
        promoted_at=(
            candidate.promoted_at.isoformat()
            if candidate.promoted_at and hasattr(candidate.promoted_at, "isoformat")
            else (str(candidate.promoted_at) if candidate.promoted_at else None)
        ),
    )


# Endpoints


@router.get("/candidates", response_model=ModelCandidateListResponse)
@limiter.limit("30/minute")
async def list_candidates(
    request: Request,
    status_filter: str | None = Query(
        None, description="Filter by status: candidate, promoted, rejected"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin_key: str = Depends(require_admin_key),
) -> ModelCandidateListResponse:
    """
    List model candidates awaiting review or previously promoted/rejected.

    Optionally filter by status. Returns up to `limit` results with pagination.
    Requires an admin-level API key.
    """
    try:
        from src.fraudlens.persistence import get_session
        from src.fraudlens.persistence.repositories import (
            ModelCandidateRepository,
        )

        async for session in get_session():
            repo = ModelCandidateRepository(session)
            candidates = await repo.get_candidates(
                status=status_filter, limit=limit, offset=offset
            )
            stats = await repo.get_statistics()
            break

        return ModelCandidateListResponse(
            candidates=[_candidate_to_out(c) for c in candidates],
            total=stats.get("total_candidates", len(candidates)),
            pending=stats.get("candidate", 0),
            promoted=stats.get("promoted", 0),
            rejected=stats.get("rejected", 0),
        )
    except Exception as e:
        logger.warning("Failed to list candidates: %s", e)
        # Fallback: return empty list if DB unavailable
        return ModelCandidateListResponse(
            candidates=[],
            total=0,
            pending=0,
            promoted=0,
            rejected=0,
        )


@router.get("/candidates/{model_version}", response_model=ModelCandidateOut)
@limiter.limit("30/minute")
async def get_candidate(
    request: Request,
    model_version: str,
    _admin_key: str = Depends(require_admin_key),
) -> ModelCandidateOut:
    """
    Get detailed information about a specific model candidate.

    Requires an admin-level API key.
    """
    try:
        from src.fraudlens.persistence import get_session
        from src.fraudlens.persistence.repositories import (
            ModelCandidateRepository,
        )

        candidate = None
        async for session in get_session():
            repo = ModelCandidateRepository(session)
            candidate = await repo.get_by_version(model_version)
            break

        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model candidate '{model_version}' not found",
            )

        return _candidate_to_out(candidate)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {e}",
        )


@router.post("/candidates/{model_version}/promote", response_model=PromoteResponse)
@limiter.limit("10/hour")
async def promote_candidate(
    request: Request,
    model_version: str,
    _admin_key: str = Depends(require_admin_key),
) -> PromoteResponse:
    """
    Promote a model candidate to production.

    This is the human-gated promotion step — the automated retraining
    pipeline NEVER auto-promotes. A fraud analyst (or ops engineer)
    must explicitly call this endpoint after reviewing candidate metrics.

    Effects:
    1. Copies the candidate model to models/best_fraud_model.pkl
    2. Marks the candidate as "promoted" in the database
    3. Logs the promotion event

    Requires an admin-level API key.
    """
    try:
        from src.fraudlens.config import MODELS_DIR
        from src.fraudlens.persistence import get_session
        from src.fraudlens.persistence.repositories import (
            ModelCandidateRepository,
        )

        promoted = None
        candidate = None
        async for session in get_session():
            repo = ModelCandidateRepository(session)
            candidate = await repo.get_by_version(model_version)

            if candidate is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Model candidate '{model_version}' not found",
                )

            if candidate.status != "candidate":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Candidate '{model_version}' has status "
                        f"'{candidate.status}' — only 'candidate' status "
                        f"can be promoted"
                    ),
                )

            # Promote in database
            promoted = await repo.promote(model_version)
            break

        # Copy the model artifact to the production path
        try:
            import shutil

            # Find the model artifact
            candidate_model_path = candidate.model_path
            if candidate_model_path and Path(candidate_model_path).exists():
                production_path = MODELS_DIR / "best_fraud_model.pkl"
                shutil.copy2(candidate_model_path, production_path)
                logger.info(
                    "Promoted model %s copied to %s",
                    model_version,
                    production_path,
                )
        except Exception as e:
            logger.warning("Model file copy failed during promotion: %s", e)

        logger.info(
            "Model %s promoted to production (trigger=%s, pr_auc=%s)",
            model_version,
            candidate.trigger,
            candidate.pr_auc,
        )

        return PromoteResponse(
            success=True,
            model_version=model_version,
            message=f"Model '{model_version}' promoted to production. Restart API to load the new model.",
            candidate=_candidate_to_out(promoted),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {e}",
        )


@router.post("/candidates/{model_version}/reject", response_model=PromoteResponse)
@limiter.limit("10/hour")
async def reject_candidate(
    request: Request,
    model_version: str,
    _admin_key: str = Depends(require_admin_key),
) -> PromoteResponse:
    """
    Reject a model candidate (mark as rejected — not promoted).

    Useful when a candidate has worse metrics than the current production model.
    Rejected candidates are kept for audit trail but are excluded from promotion.

    Requires an admin-level API key.
    """
    try:
        from src.fraudlens.persistence import get_session
        from src.fraudlens.persistence.repositories import (
            ModelCandidateRepository,
        )

        async for session in get_session():
            repo = ModelCandidateRepository(session)
            rejected = await repo.reject(model_version)

            if rejected is None:
                candidate = await repo.get_by_version(model_version)
                if candidate is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Model candidate '{model_version}' not found",
                    )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Candidate '{model_version}' has status "
                        f"'{candidate.status}' — only 'candidate' "
                        f"status can be rejected"
                    ),
                )
            break

        logger.info("Model %s rejected by admin", model_version)

        return PromoteResponse(
            success=True,
            model_version=model_version,
            message=f"Model '{model_version}' rejected.",
            candidate=_candidate_to_out(rejected),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {e}",
        )


@router.get("/candidates/{model_version}/compare", response_model=CompareResponse)
@limiter.limit("30/minute")
async def compare_candidate(
    request: Request,
    model_version: str,
    _admin_key: str = Depends(require_admin_key),
) -> CompareResponse:
    """
    Compare a candidate model against the current production model.

    Shows metrics delta between candidate and the most recently promoted model.
    Useful for deciding whether to promote this candidate.

    Requires an admin-level API key.
    """
    try:
        from src.fraudlens.persistence import get_session
        from src.fraudlens.persistence.repositories import (
            ModelCandidateRepository,
        )

        candidate = None
        production = None
        async for session in get_session():
            repo = ModelCandidateRepository(session)
            candidate = await repo.get_by_version(model_version)
            production = await repo.get_latest_promoted()
            break

        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model candidate '{model_version}' not found",
            )

        # Compute metrics delta
        metrics_delta = None
        if (
            production
            and candidate.pr_auc is not None
            and production.pr_auc is not None
        ):
            metrics_delta = {
                "pr_auc": round((candidate.pr_auc or 0) - (production.pr_auc or 0), 6),
                "f1_score": round(
                    (candidate.f1_score or 0) - (production.f1_score or 0),
                    6,
                ),
                "precision": round(
                    (candidate.precision or 0) - (production.precision or 0),
                    6,
                ),
                "recall": round((candidate.recall or 0) - (production.recall or 0), 6),
            }

        return CompareResponse(
            current_production=(_candidate_to_out(production) if production else None),
            candidate=_candidate_to_out(candidate),
            metrics_delta=metrics_delta,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {e}",
        )
