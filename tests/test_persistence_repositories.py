"""
FraudLens — Persistence Repository Tests

Tests for all four repositories:
- PredictionRepository
- FeedbackRepository
- DriftEventRepository
- ApiKeyRepository

Uses mocked AsyncSession to avoid requiring a real database.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.fraudlens.persistence.models import (
    ApiKeyModel,
    DriftEventModel,
    FeedbackModel,
    PredictionModel,
)

pytestmark = pytest.mark.slow
from src.fraudlens.persistence.repositories.api_keys import ApiKeyRepository
from src.fraudlens.persistence.repositories.drift_events import DriftEventRepository
from src.fraudlens.persistence.repositories.feedback import FeedbackRepository
from src.fraudlens.persistence.repositories.predictions import PredictionRepository


@pytest.fixture
def mock_session():
    """Create a mocked async session."""
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    return session


# PredictionRepository Tests


class TestPredictionRepository:
    """Tests for PredictionRepository."""

    def test_init(self, mock_session):
        """Test repository initialization."""
        repo = PredictionRepository(mock_session)
        assert repo.session == mock_session
        assert repo.model_class == PredictionModel

    @pytest.mark.asyncio
    async def test_create_prediction(self, mock_session):
        """Test creating a prediction record."""
        repo = PredictionRepository(mock_session)

        result = await repo.create_prediction(
            fraud_probability=0.95,
            decision="FRAUD",
            threshold_used=0.5,
            is_fraud=True,
            transaction_id="tx-001",
            model_version="xgboost_v1",
            latency_ms=12.5,
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert isinstance(result, PredictionModel)

    @pytest.mark.asyncio
    async def test_create_prediction_minimal(self, mock_session):
        """Test creating a prediction with only required fields."""
        repo = PredictionRepository(mock_session)

        result = await repo.create_prediction(
            fraud_probability=0.1,
            decision="LEGITIMATE",
            threshold_used=0.5,
            is_fraud=False,
        )

        mock_session.add.assert_called_once()
        assert result.fraud_probability == 0.1
        assert result.decision == "LEGITIMATE"

    @pytest.mark.asyncio
    async def test_get_recent_without_filter(self, mock_session):
        """Test get_recent with no decision filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            PredictionModel(id=uuid.uuid4(), decision="FRAUD")
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = PredictionRepository(mock_session)
        results = await repo.get_recent(limit=10)

        assert len(results) == 1
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_recent_with_filter(self, mock_session):
        """Test get_recent filtered by decision."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            PredictionModel(id=uuid.uuid4(), decision="FRAUD")
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = PredictionRepository(mock_session)
        results = await repo.get_recent(limit=5, decision="FRAUD")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_statistics(self, mock_session):
        """Test get_statistics returns expected shape."""
        mock_row = MagicMock()
        mock_row.total = 100
        mock_row.total_fraud = 10
        mock_row.avg_probability = 0.05
        mock_row.avg_latency_ms = 15.0
        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = PredictionRepository(mock_session)
        stats = await repo.get_statistics()

        assert stats["total_predictions"] == 100
        assert stats["total_fraud"] == 10
        assert stats["fraud_rate"] == 0.1
        assert stats["avg_probability"] == 0.05
        assert stats["avg_latency_ms"] == 15.0

    @pytest.mark.asyncio
    async def test_get_statistics_empty(self, mock_session):
        """Test get_statistics with no data returns zeros."""
        mock_row = MagicMock()
        mock_row.total = 0
        mock_row.total_fraud = 0
        mock_row.avg_probability = None
        mock_row.avg_latency_ms = None
        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = PredictionRepository(mock_session)
        stats = await repo.get_statistics()

        assert stats["total_predictions"] == 0
        assert stats["fraud_rate"] == 0.0
        assert stats["avg_probability"] == 0.0
        assert stats["avg_latency_ms"] == 0.0

    @pytest.mark.asyncio
    async def test_get_statistics_with_since(self, mock_session):
        """Test get_statistics with a since filter."""
        mock_row = MagicMock()
        mock_row.total = 50
        mock_row.total_fraud = 5
        mock_row.avg_probability = 0.03
        mock_row.avg_latency_ms = 10.0
        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = PredictionRepository(mock_session)
        stats = await repo.get_statistics(since=datetime(2026, 1, 1))

        assert stats["total_predictions"] == 50


# FeedbackRepository Tests


class TestFeedbackRepository:
    """Tests for FeedbackRepository."""

    def test_init(self, mock_session):
        """Test repository initialization."""
        repo = FeedbackRepository(mock_session)
        assert repo.model_class == FeedbackModel

    @pytest.mark.asyncio
    async def test_create_feedback(self, mock_session):
        """Test creating a feedback record."""
        repo = FeedbackRepository(mock_session)
        pred_id = uuid.uuid4()

        result = await repo.create_feedback(
            prediction_id=pred_id,
            confirmed_fraud=True,
            analyst_notes="Confirmed fraud",
            reviewed_by="analyst@example.com",
        )

        mock_session.add.assert_called_once()
        assert result.confirmed_fraud is True

    @pytest.mark.asyncio
    async def test_get_by_prediction_found(self, mock_session):
        """Test get_by_prediction when feedback exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = FeedbackModel(
            id=uuid.uuid4(), confirmed_fraud=True
        )
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = FeedbackRepository(mock_session)
        result = await repo.get_by_prediction(uuid.uuid4())

        assert result is not None
        assert result.confirmed_fraud is True

    @pytest.mark.asyncio
    async def test_get_by_prediction_not_found(self, mock_session):
        """Test get_by_prediction when no feedback exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = FeedbackRepository(mock_session)
        result = await repo.get_by_prediction(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_recent_feedback(self, mock_session):
        """Test get_recent_feedback without filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            FeedbackModel(id=uuid.uuid4(), confirmed_fraud=True)
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = FeedbackRepository(mock_session)
        results = await repo.get_recent_feedback()

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_recent_feedback_confirmed_only(self, mock_session):
        """Test get_recent_feedback with confirmed_only filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = FeedbackRepository(mock_session)
        results = await repo.get_recent_feedback(confirmed_only=True)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_statistics(self, mock_session):
        """Test get_statistics returns expected values."""
        mock_row = MagicMock()
        mock_row.total = 50
        mock_row.confirmed_fraud = 30
        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = FeedbackRepository(mock_session)
        stats = await repo.get_statistics()

        assert stats["total_feedback"] == 50
        assert stats["confirmed_fraud"] == 30
        assert stats["confirmed_legitimate"] == 20


# DriftEventRepository Tests


class TestDriftEventRepository:
    """Tests for DriftEventRepository."""

    def test_init(self, mock_session):
        """Test repository initialization."""
        repo = DriftEventRepository(mock_session)
        assert repo.model_class == DriftEventModel

    @pytest.mark.asyncio
    async def test_create_event(self, mock_session):
        """Test creating a drift event."""
        repo = DriftEventRepository(mock_session)

        result = await repo.create_event(
            feature_name="V14",
            drift_score=0.85,
            p_value=0.001,
            alert_type="CRITICAL",
            window_size=1000,
            details={"mean_shift": 2.5},
        )

        mock_session.add.assert_called_once()
        assert result.feature_name == "V14"
        assert result.alert_type == "CRITICAL"

    @pytest.mark.asyncio
    async def test_get_recent_events(self, mock_session):
        """Test get_recent_events without filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            DriftEventModel(id=uuid.uuid4(), feature_name="V14")
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = DriftEventRepository(mock_session)
        results = await repo.get_recent_events()

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_recent_events_filtered(self, mock_session):
        """Test get_recent_events filtered by alert_type."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            DriftEventModel(id=uuid.uuid4(), alert_type="WARNING")
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = DriftEventRepository(mock_session)
        results = await repo.get_recent_events(alert_type="WARNING")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_events_since(self, mock_session):
        """Test get_events_since returns events after timestamp."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            DriftEventModel(id=uuid.uuid4(), feature_name="V14", drift_score=0.75)
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = DriftEventRepository(mock_session)
        results = await repo.get_events_since(
            since=datetime(2026, 6, 1), feature_name="V14"
        )

        assert len(results) == 1
        assert results[0].drift_score == 0.75

    @pytest.mark.asyncio
    async def test_get_statistics(self, mock_session):
        """Test get_statistics returns event count."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 25
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = DriftEventRepository(mock_session)
        stats = await repo.get_statistics()

        assert stats["total_events"] == 25


# ApiKeyRepository Tests


class TestApiKeyRepository:
    """Tests for ApiKeyRepository."""

    def test_init(self, mock_session):
        """Test repository initialization."""
        repo = ApiKeyRepository(mock_session)
        assert repo.model_class == ApiKeyModel

    @pytest.mark.asyncio
    async def test_get_by_key_hash_found(self, mock_session):
        """Test get_by_key_hash when key exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = ApiKeyModel(
            id=uuid.uuid4(), key_hash="abc123", role="admin"
        )
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = ApiKeyRepository(mock_session)
        result = await repo.get_by_key_hash("abc123")

        assert result is not None
        assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_get_by_key_hash_not_found(self, mock_session):
        """Test get_by_key_hash when key doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = ApiKeyRepository(mock_session)
        result = await repo.get_by_key_hash("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_key(self, mock_session):
        """Test creating an API key."""
        repo = ApiKeyRepository(mock_session)

        result = await repo.create_key(
            key_hash="def456",
            role="readonly",
            description="Test key",
        )

        mock_session.add.assert_called_once()
        assert result.key_hash == "def456"
        assert result.role == "readonly"

    @pytest.mark.asyncio
    async def test_update_last_used(self, mock_session):
        """Test updating last_used_at timestamp."""
        key = ApiKeyModel(id=uuid.uuid4(), key_hash="abc123")
        repo = ApiKeyRepository(mock_session)

        with patch.object(repo, "get", AsyncMock(return_value=key)):
            await repo.update_last_used(str(key.id))
            assert key.last_used_at is not None
            mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_key_success(self, mock_session):
        """Test deactivating an existing key."""
        key = ApiKeyModel(id=uuid.uuid4(), key_hash="abc123", is_active=True)
        repo = ApiKeyRepository(mock_session)

        with patch.object(repo, "get", AsyncMock(return_value=key)):
            result = await repo.deactivate(str(key.id))
            assert result is True
            assert key.is_active is False

    @pytest.mark.asyncio
    async def test_deactivate_key_not_found(self, mock_session):
        """Test deactivating a non-existent key returns False."""
        repo = ApiKeyRepository(mock_session)

        with patch.object(repo, "get", AsyncMock(return_value=None)):
            result = await repo.deactivate("nonexistent")
            assert result is False
