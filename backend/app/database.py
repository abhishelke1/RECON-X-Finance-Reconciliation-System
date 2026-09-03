"""Database configuration and session management.

Uses lazy engine creation so the application can work with
SQLite (local/testing) or PostgreSQL (production/Docker).
"""
import logging
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_async_engine():
    """Lazily create the async database engine."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )


@lru_cache
def get_session_maker():
    """Lazily create the async session factory."""
    return async_sessionmaker(
        get_async_engine(), class_=AsyncSession, expire_on_commit=False, autoflush=False
    )


@lru_cache
def get_sync_engine():
    """Lazily create the sync engine for Alembic migrations."""
    settings = get_settings()
    return create_engine(
        settings.database_url_sync,
        echo=settings.debug,
        pool_pre_ping=True,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting an async DB session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()
