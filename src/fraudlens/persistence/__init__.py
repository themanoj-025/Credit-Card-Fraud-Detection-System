"""
FraudLens — Data Persistence Layer

SQLAlchemy models, database session management, and repository pattern
for the PostgreSQL-backed system of record.

Provides:
- `get_session()` — async session generator for FastAPI Depends()
- `Base` — declarative base for all ORM models
- `engine` — the SQLAlchemy engine (lazy-initialized)
"""

from .database import Base, engine, get_session, init_db

__all__ = ["Base", "engine", "get_session", "init_db"]
