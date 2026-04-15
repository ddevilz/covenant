from __future__ import annotations

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.tables import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "sqlite+aiosqlite:///./covenant_registry.db"
)

# For SQLite (tests): use StaticPool so in-memory DB is shared across connections
_engine_kwargs: dict = {}
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy.pool import StaticPool
    _engine_kwargs = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

engine = create_async_engine(DATABASE_URL, echo=False, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session per request."""
    async with async_session_factory() as session:
        yield session


async def create_tables() -> None:
    """Create all tables. Called at startup in non-production environments."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all tables. Used in tests for teardown."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
