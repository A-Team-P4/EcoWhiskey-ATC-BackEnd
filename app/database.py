"""Database configuration and session management for the MVC layout."""

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import settings

# Import models so they are attached to Base.metadata before table creation
from app.models import Base  # noqa: F401 - ensures metadata is registered
from app.models import hello  # noqa: F401
from app.models import user  # noqa: F401

engine: AsyncEngine = create_async_engine(
    settings.database.url,
    echo=settings.debug,
    future=True,
)

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
