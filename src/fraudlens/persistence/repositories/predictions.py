"""
FraudLens — Prediction Repository
"""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PredictionModel
from .base import BaseRepository


class PredictionRepository(BaseRepository[PredictionModel]):
    """Repository for prediction records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PredictionModel)

    async def create_prediction(
        self,
        fraud_probability: float,
        decision: str,
        threshold_used: float,
        is_fraud: bool,
        transaction_id: str | None = None,
        model_version: str | None = None,
        latency_ms: float | None = None,
        features: dict[str, float] | None = None,
        shap_values: dict[str, float] | None = None,
        anomaly_score: float | None = None,
    ) -> PredictionModel:
        """Create a new prediction record."""
        return await self.create(
            transaction_id=transaction_id,
            fraud_probability=fraud_probability,
            decision=decision,
            threshold_used=threshold_used,
            is_fraud=is_fraud,
            model_version=model_version,
            latency_ms=latency_ms,
            features=features,
            shap_values=shap_values,
            anomaly_score=anomaly_score,
        )

    async def get_recent(
        self,
        limit: int = 50,
        decision: str | None = None,
    ) -> list[PredictionModel] -> None:
        """Get recent predictions, optionally filtered by decision."""
        stmt = select(PredictionModel).order_by(PredictionModel.created_at.desc())
        if decision:
            stmt = stmt.where(PredictionModel.decision == decision)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_statistics(
        self,
        since: datetime | None = None,
    ) -> dict[str, Any] -> None:
        """Get prediction statistics for monitoring."""
        stmt = select(
            func.count(PredictionModel.id).label("total"),
            func.sum(sa.cast(PredictionModel.is_fraud, sa.Integer())).label(
                "total_fraud"
            ),
            func.avg(PredictionModel.fraud_probability).label("avg_probability"),
            func.avg(PredictionModel.latency_ms).label("avg_latency_ms"),
        )
        if since:
            stmt = stmt.where(PredictionModel.created_at >= since)

        result = await self.session.execute(stmt)
        row = result.one()
        total = row.total or 0
        return {
            "total_predictions": total,
            "total_fraud": row.total_fraud or 0,
            "fraud_rate": (
                round((row.total_fraud or 0) / total, 4) if total > 0 else 0.0
            ),
            "avg_probability": round(float(row.avg_probability or 0.0), 4),
            "avg_latency_ms": round(float(row.avg_latency_ms or 0.0), 2),
        }
