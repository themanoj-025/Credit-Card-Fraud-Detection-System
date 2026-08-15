"""
FraudLens — API Key Repository
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ApiKeyModel
from .base import BaseRepository


class ApiKeyRepository(BaseRepository[ApiKeyModel]):
    """Repository for API key records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ApiKeyModel)

    async def get_by_key_hash(self, key_hash: str) -> ApiKeyModel | None:
        """Get an API key by its hash."""
        result = await self.session.execute(
            select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def create_key(
        self,
        key_hash: str,
        role: str = "readonly",
        description: str | None = None,
    ) -> ApiKeyModel:
        """Create a new API key record."""
        return await self.create(
            key_hash=key_hash,
            role=role,
            description=description,
        )

    async def update_last_used(self, key_id: str) -> None:
        """Update the last_used_at timestamp for a key."""
        key = await self.get(key_id)
        if key:
            key.last_used_at = datetime.utcnow()
            await self.session.flush()

    async def deactivate(self, key_id: str) -> bool:
        """Deactivate an API key."""
        key = await self.get(key_id)
        if key is None:
            return False
        key.is_active = False
        await self.session.flush()
        return True
