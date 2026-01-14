"""Database session management.

Provides async database session factory and dependency for FastAPI.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL", "")

# Convert sync URL to async if needed
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


def create_engine():
    """Create async database engine.

    Returns:
        AsyncEngine: SQLAlchemy async engine.
    """
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL or DB_URL environment variable must be set"
        )

    return create_async_engine(
        DATABASE_URL,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


# Global engine (lazy initialized)
_engine = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


# Session factory
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get async session factory.

    Returns:
        async_sessionmaker: Factory for creating async sessions.
    """
    return async_sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions.

    Yields:
        AsyncSession: Database session.

    Example:
        async with get_db_session() as session:
            result = await session.execute(query)
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Yields:
        AsyncSession: Database session.

    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_session)):
            ...
    """
    async with get_db_session() as session:
        yield session
