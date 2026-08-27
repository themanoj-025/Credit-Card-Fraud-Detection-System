"""
FraudLens — Database Engine & Session Management

Provides async SQLAlchemy session management for PostgreSQL,
with a fallback to SQLite for local development.

Usage:
    from src.fraudlens.persistence import get_session

    async def get_db() -> AsyncSession:
        async with get_session() as session:
            yield session
"""

import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# Engine & Session

# Determine database URL from environment, with sensible default for dev
_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{Path(__file__).resolve().parent.parent.parent.parent / 'fraudlens.db'}",
)

# For SQLite, we need aiosqlite; for Postgres, we need asyncpg
_USE_SQLITE = "sqlite" in _DATABASE_URL

# SQLite needs connect_args for concurrency
_connect_args = {"check_same_thread": False} if _USE_SQLITE else {}

engine = create_async_engine(
    _DATABASE_URL,
    echo=False,
    connect_args=_connect_args,
    pool_size=5 if not _USE_SQLITE else 1,
    max_overflow=10 if not _USE_SQLITE else 0,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session.

    Yields:
        An async SQLAlchemy session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except (OSError, ConnectionError):
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database by creating all tables.

    Should be called on application startup.
    """
    from src.fraudlens.persistence.models import (  # noqa: F401  — register models
        ApiKeyModel,
        DriftEventModel,
        FeedbackModel,
        PredictionModel,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info(
        "Database tables created/verified (engine=%s)", _DATABASE_URL.split("://")[0]
    )
