"""
FraudLens — Base Repository

Abstract base class with common CRUD operations for all repositories.
"""

import logging
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Base

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common database operations."""

    def __init__(self, session: AsyncSession, model_class: type[ModelType]) -> None:
        self.session = session
        self.model_class = model_class

    async def create(self, **kwargs: Any) -> ModelType:
        """Create a new record."""
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def get(self, id: Any) -> ModelType | None:
        """Get a record by primary key."""
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = "created_at",
        descending: bool = True,
    ) -> list[ModelType]:
        """List records with pagination."""
        stmt = select(self.model_class)

        if order_by is not None and hasattr(self.model_class, order_by):
            order_col = getattr(self.model_class, order_by)
            stmt = stmt.order_by(order_col.desc() if descending else order_col)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, **filters: Any) -> int:
        """Count records with optional filters."""
        stmt = select(func.count(self.model_class.id))
        for key, value in filters.items():
            if hasattr(self.model_class, key):
                stmt = stmt.where(getattr(self.model_class, key) == value)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def update(self, id: Any, **kwargs: Any) -> ModelType | None:
        """Update a record by primary key."""
        instance = await self.get(id)
        if instance is None:
            return None
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def delete(self, id: Any) -> bool:
        """Delete a record by primary key. Returns True if deleted."""
        instance = await self.get(id)
        if instance is None:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True
