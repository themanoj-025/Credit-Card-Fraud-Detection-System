"""
FraudLens — Base Repository Tests

Tests for BaseRepository CRUD operations (create, get, list, count, update, delete).
Uses mocked async session to avoid requiring a real database.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.fraudlens.persistence.models import PredictionModel
from src.fraudlens.persistence.repositories.base import BaseRepository


@pytest.fixture
def mock_session():
    """Create a mocked async session."""
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    return session


class TestBaseRepository:
    """Tests for BaseRepository generic CRUD operations."""

    def test_init(self, mock_session):
        """Test repository initialization stores session and model class."""
        repo = BaseRepository(mock_session, PredictionModel)
        assert repo.session == mock_session
        assert repo.model_class == PredictionModel

    @pytest.mark.asyncio
    async def test_create(self, mock_session):
        """Test create adds instance and flushes."""
        repo = BaseRepository(mock_session, PredictionModel)
        result = await repo.create(
            fraud_probability=0.95,
            decision="FRAUD",
            threshold_used=0.5,
            is_fraud=True,
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert result.fraud_probability == 0.95
        assert result.decision == "FRAUD"

    @pytest.mark.asyncio
    async def test_get_found(self, mock_session):
        """Test get returns instance when found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = PredictionModel(decision="FRAUD")
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        result = await repo.get(1)

        assert result is not None
        assert result.decision == "FRAUD"

    @pytest.mark.asyncio
    async def test_get_not_found(self, mock_session):
        """Test get returns None when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        result = await repo.get(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_defaults(self, mock_session):
        """Test list with default parameters uses descending order."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            PredictionModel(decision="FRAUD"),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        results = await repo.list()

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, mock_session):
        """Test list respects skip/limit."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        results = await repo.list(skip=10, limit=20)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_list_ascending_order(self, mock_session):
        """Test list with ascending order."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        results = await repo.list(order_by="created_at", descending=False)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_count_no_filters(self, mock_session):
        """Test count returns total without filters."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        count = await repo.count()

        assert count == 42

    @pytest.mark.asyncio
    async def test_count_with_filters(self, mock_session):
        """Test count with filter arguments."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 15
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        count = await repo.count(decision="FRAUD")

        assert count == 15

    @pytest.mark.asyncio
    async def test_count_zero_when_no_rows(self, mock_session):
        """Test count returns 0 when no matching records."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        count = await repo.count()

        assert count == 0

    @pytest.mark.asyncio
    async def test_update_success(self, mock_session):
        """Test update modifies attributes and flushes."""
        instance = PredictionModel(decision="LEGITIMATE")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = instance
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        result = await repo.update(1, decision="FRAUD", threshold_used=0.3)

        assert result is not None
        assert result.decision == "FRAUD"
        assert result.threshold_used == 0.3
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_not_found(self, mock_session):
        """Test update returns None when instance not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        result = await repo.update(999, decision="FRAUD")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_ignores_unknown_attrs(self, mock_session):
        """Test update silently ignores attributes that don't exist on the model."""
        instance = PredictionModel(decision="LEGITIMATE")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = instance
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        result = await repo.update(1, decision="FRAUD", nonexistent_field="value")

        assert result is not None
        assert result.decision == "FRAUD"

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_session):
        """Test delete returns True when instance exists."""
        instance = PredictionModel(decision="FRAUD")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = instance
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        result = await repo.delete(1)

        assert result is True
        mock_session.delete.assert_called_once_with(instance)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_session):
        """Test delete returns False when instance not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = BaseRepository(mock_session, PredictionModel)
        result = await repo.delete(999)

        assert result is False
        mock_session.delete.assert_not_called()
