"""
FraudLens — Feedback Repository
"""

from uuid import UUID

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import FeedbackModel
from .base import BaseRepository


class FeedbackRepository(BaseRepository[FeedbackModel]):
    """Repository for analyst feedback records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FeedbackModel)

    async def create_feedback(
        self,
        prediction_id: UUID,
        confirmed_fraud: bool,
        analyst_notes: str | None = None,
        reviewed_by: str | None = None,
    ) -> FeedbackModel:
        """Create a new feedback record."""
        return await self.create(
            prediction_id=prediction_id,
            confirmed_fraud=confirmed_fraud,
            analyst_notes=analyst_notes,
            reviewed_by=reviewed_by,
        )

    async def get_by_prediction(self, prediction_id: UUID) -> FeedbackModel | None:
        """Get feedback for a specific prediction."""
        result = await self.session.execute(
            select(FeedbackModel).where(FeedbackModel.prediction_id == prediction_id)
        )
        return result.scalar_one_or_none()

    async def get_recent_feedback(
        self,
        limit: int = 100,
        confirmed_only: bool = False,
    ) -> list[FeedbackModel]:
        """Get recent feedback entries."""
        stmt = select(FeedbackModel).order_by(FeedbackModel.created_at.desc())
        if confirmed_only:
            stmt = stmt.where(FeedbackModel.confirmed_fraud == True)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_statistics(self) -> dict:
        """Get feedback statistics."""
        stmt = select(
            func.count(FeedbackModel.id).label("total"),
            func.sum(func.cast(FeedbackModel.confirmed_fraud, Integer())).label(
                "confirmed_fraud"
            ),
        )
        result = await self.session.execute(stmt)
        row = result.one()
        total = row.total or 0
        return {
            "total_feedback": total,
            "confirmed_fraud": row.confirmed_fraud or 0,
            "confirmed_legitimate": total - (row.confirmed_fraud or 0),
        }
