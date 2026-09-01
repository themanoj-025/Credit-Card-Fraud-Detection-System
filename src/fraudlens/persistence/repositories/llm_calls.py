"""
FraudLens — LLM Call Repository

Handles database operations for LLM API call records.
Used for historical cost analysis and dashboard queries.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import LlmCallModel
from .base import BaseRepository


class LlmCallRepository(BaseRepository[LlmCallModel]):
    """Repository for LLM API call records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LlmCallModel)

    async def create_call(
        self,
        model: str,
        endpoint: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        status: str = "success",
    ) -> LlmCallModel:
        """Create a new LLM call record."""
        return await self.create(
            model=model,
            endpoint=endpoint,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            status=status,
        )

    async def get_recent_calls(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LlmCallModel]:
        """Get recent LLM calls ordered by time (newest first)."""
        stmt = (
            select(LlmCallModel)
            .order_by(LlmCallModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_calls_since(
        self,
        since: datetime,
    ) -> list[LlmCallModel]:
        """Get all LLM calls since a specific timestamp."""
        stmt = (
            select(LlmCallModel)
            .where(LlmCallModel.created_at >= since)
            .order_by(LlmCallModel.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_period_summary(
        self,
        since: datetime,
    ) -> dict[str, Any]:
        """
        Get aggregated cost summary for a time period.

        Args:
            since: Start timestamp for the period

        Returns:
            Dict with total_cost_usd, total_calls, total_input_tokens,
            total_output_tokens, by_model, by_endpoint
        """
        stmt = select(
            func.count(LlmCallModel.id).label("total_calls"),
            func.sum(LlmCallModel.input_tokens).label("total_input_tokens"),
            func.sum(LlmCallModel.output_tokens).label("total_output_tokens"),
            func.sum(LlmCallModel.cost_usd).label("total_cost_usd"),
        ).where(LlmCallModel.created_at >= since)
        result = await self.session.execute(stmt)
        row = result.one()

        total_calls = row.total_calls or 0
        total_input = row.total_input_tokens or 0
        total_output = row.total_output_tokens or 0
        total_cost = float(row.total_cost_usd or 0.0)

        # Per-model breakdown
        model_stmt = (
            select(
                LlmCallModel.model,
                func.sum(LlmCallModel.cost_usd).label("cost"),
            )
            .where(LlmCallModel.created_at >= since)
            .group_by(LlmCallModel.model)
        )
        model_result = await self.session.execute(model_stmt)
        by_model = {row.model: float(row.cost) for row in model_result}

        # Per-endpoint breakdown
        endpoint_stmt = (
            select(
                LlmCallModel.endpoint,
                func.sum(LlmCallModel.cost_usd).label("cost"),
            )
            .where(LlmCallModel.created_at >= since)
            .group_by(LlmCallModel.endpoint)
        )
        endpoint_result = await self.session.execute(endpoint_stmt)
        by_endpoint = {row.endpoint: float(row.cost) for row in endpoint_result}

        return {
            "total_cost_usd": round(total_cost, 6),
            "total_calls": total_calls,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "by_model": by_model,
            "by_endpoint": by_endpoint,
        }

    async def get_statistics(self) -> dict[str, Any]:
        """Get overall LLM call statistics."""
        stmt = select(
            func.count(LlmCallModel.id).label("total_calls"),
            func.sum(LlmCallModel.cost_usd).label("total_cost_usd"),
        )
        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "total_calls": row.total_calls or 0,
            "total_cost_usd": float(row.total_cost_usd or 0.0),
        }
