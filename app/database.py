"""Database configuration and session management for the MVC layout."""

from typing import Any, AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config.settings import settings

# Import models so they are attached to Base.metadata before table creation
from app.models import Base  # noqa: F401 - ensures metadata is registered
from app.models import hello  # noqa: F401
from app.models import log  # noqa: F401
from app.models import user  # noqa: F401


def _create_engine() -> AsyncEngine:
    """Create an async engine with environment-appropriate pooling."""

    engine_options: dict[str, Any] = {
        "echo": settings.debug,
        "future": True,
        "pool_pre_ping": True,
    }

    if settings.database.serverless or settings.debug:
        # Disable pooling when working with serverless databases (or in debug).
        engine_options["poolclass"] = NullPool

    return create_async_engine(settings.database.url, **engine_options)


engine: AsyncEngine = _create_engine()

SessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a single async SQLAlchemy session."""

    async with SessionFactory() as session:
        yield session


async def init_models() -> None:
    """Create database tables if they do not exist."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Dispose of the engine and release pooled connections."""

    await engine.dispose()
