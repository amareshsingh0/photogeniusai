"""
Database connection helper for PhotoGenius AI (PostgreSQL 14+).
Uses SQLAlchemy 2.0 with async (asyncpg) and optional sync (psycopg2) engines.
Reads DATABASE_URL from env / app.core.config.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine  # type: ignore[reportMissingImports]
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # type: ignore[reportMissingImports]
from sqlalchemy.orm import Session, declarative_base, sessionmaker  # type: ignore[reportMissingImports]

from app.core.config import settings  # type: ignore[reportAttributeAccessIssue]

_DEFAULT_URL = "postgresql://localhost:5432/postgres"


def _database_url() -> str:
    return (settings.database_url or _DEFAULT_URL).strip() or _DEFAULT_URL


def _async_url() -> str:
    u = _database_url()
    if u.startswith("postgresql://"):
        return u.replace("postgresql://", "postgresql+asyncpg://", 1)
    if u.startswith("postgresql+asyncpg"):
        return u
    return "postgresql+asyncpg://localhost:5432/postgres"


def _sync_url() -> str:
    u = _database_url()
    if u.startswith("postgresql+asyncpg"):
        return u.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if u.startswith("postgresql://"):
        return u
    return "postgresql://localhost:5432/postgres"


# Async engine and session (primary for FastAPI)
async_engine = create_async_engine(
    _async_url(),
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Sync engine and session (scripts, migrations, background jobs)
sync_engine = create_engine(
    _sync_url(),
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SyncSessionLocal = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base: Any = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for async DB session (non-FastAPI use)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@contextmanager
def sync_session() -> Generator[Session, None, None]:
    """Sync session context. Use as `with sync_session() as s: ...`."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
