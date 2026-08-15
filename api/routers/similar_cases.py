"""
Similar Cases Router — /similar-cases endpoint.

Retrieves similar historical flagged transactions using FAISS-based RAG.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.auth import require_api_key
from api.providers import get_case_retriever
from api.rate_limit import limiter
from api.schemas import (
    CursorPagination,
    SimilarCase,
    SimilarCasesResponse,
    TransactionInput,
)
from src.fraudlens.config import RAG_TOP_K

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["rag"])


@router.post("/similar-cases", response_model=SimilarCasesResponse)
@limiter.limit("60/minute")
async def get_similar_cases(
    request: Request,
    transaction: TransactionInput,
    top_k: int = Query(default=RAG_TOP_K, ge=1, le=20),
    cursor: str | None = Query(
        None,
        description="Pagination cursor from previous response. "
        "Omit or null for the first page.",
    ),
    limit: int = Query(
        default=RAG_TOP_K,
        ge=1,
        le=50,
        description="Maximum number of similar cases to return",
    ),
    api_key: str = Depends(require_api_key),
) -> SimilarCasesResponse:
    """
    Retrieve similar historical cases for a flagged transaction.

    Supports cursor-based pagination via the `cursor` parameter.
    First page: omit cursor. Subsequent pages: pass the `next_cursor`
    value from the previous response.
    """
    case_retriever = get_case_retriever()
    if case_retriever is None:
        raise HTTPException(
            status_code=503,
            detail="Case retriever not initialized. Build a RAG index first.",
        )

    try:
        # Retrieve more than needed for pagination
        retrieve_k = min(limit + 1, 50)
        similar = case_retriever.retrieve(transaction.dict(), top_k=retrieve_k)

        # Apply cursor-based offset if cursor is provided
        offset = 0
        if cursor is not None:
            try:
                offset = int(cursor)
            except (ValueError, TypeError):
                offset = 0

        # Slice for pagination
        page = similar[offset : offset + limit]
        has_more = len(similar) > offset + limit
        next_cursor = str(offset + limit) if has_more else None

        cases = [
            SimilarCase(
                similarity_score=c["similarity_score"],
                actual_outcome=c["actual_outcome"],
                features=c["features"],
            )
            for c in page
        ]

        return SimilarCasesResponse(
            transaction_id=f"tx_{hash(str(transaction)) & 0xFFFFFFFF}",
            similar_cases=cases,
            pagination=CursorPagination(
                next_cursor=next_cursor,
                has_more=has_more,
                limit=limit,
                total=len(similar),
            ),
        )
    except Exception as e:
        logger.error("Similar cases retrieval failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
