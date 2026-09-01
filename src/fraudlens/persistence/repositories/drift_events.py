"""
FraudLens — Drift Event Repository
"""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DriftEventModel
from .base import BaseRepository


class DriftEventRepository(BaseRepository[DriftEventModel]):
    """Repository for drift event records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DriftEventModel)

    async def create_event(
        self,
        feature_name: str,
        drift_score: float,
        p_value: float | None = None,
        alert_type: str = "drift",
        window_size: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> DriftEventModel:
        """Create a new drift event record."""
        return await self.create(
            feature_name=feature_name,
            drift_score=drift_score,
            p_value=p_value,
            alert_type=alert_type,
            window_size=window_size,
            details=details,
        )

    async def get_recent_events(
        self,
        limit: int = 50,
        alert_type: str | None = None,
    ) -> list[DriftEventModel]:
        """Get recent drift events, optionally filtered by type."""
        stmt = select(DriftEventModel).order_by(DriftEventModel.created_at.desc())
        if alert_type:
            stmt = stmt.where(DriftEventModel.alert_type == alert_type)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_events_since(
        self,
        since: datetime,
        feature_name: str | None = None,
    ) -> list[DriftEventModel]:
        """Get events since a timestamp, optionally for a specific feature."""
        stmt = (
            select(DriftEventModel)
            .where(DriftEventModel.created_at >= since)
            .order_by(DriftEventModel.created_at.desc())
        )
        if feature_name:
            stmt = stmt.where(DriftEventModel.feature_name == feature_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_statistics(self) -> dict[str, Any]:
        """Get drift event statistics."""
        stmt = select(func.count(DriftEventModel.id).label("total"))
        result = await self.session.execute(stmt)
        total = result.scalar() or 0
        return {
            "total_events": total,
        }
