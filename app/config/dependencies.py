from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from .settings import settings
from app.infrastructure.persistence.repositories_sqlalchemy import init_models

# Database setup
engine = create_async_engine(
    settings.database.url,
    echo=settings.debug,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_database_session() -> AsyncSession:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_database_models() -> None:
    """Ensure database tables are created"""

    await init_models(engine)
