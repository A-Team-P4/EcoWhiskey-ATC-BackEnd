"""Database configuration and session management for the MVC layout."""

from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from sqlalchemy import text
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

logger = logging.getLogger(__name__)

_SCHEMA_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _normalise_schema_name(raw_schema: str | None) -> str | None:
    """Return a sanitised schema name or None when invalid/empty."""

    if raw_schema is None:
        return None

    schema = raw_schema.strip()
    if not schema:
        return None

    if not _SCHEMA_NAME_PATTERN.fullmatch(schema):
        logger.warning(
            "Ignoring invalid schema name '%s'; falling back to default search_path.",
            raw_schema,
        )
        return None

    return schema


def _quote_identifier(identifier: str) -> str:
    """Return a double-quoted SQL identifier, escaping inner quotes."""

    return identifier.replace('"', '""')


_SCHEMA_NAME = _normalise_schema_name(getattr(settings.database, "schema", None))


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


async def _ensure_search_path(target: Any) -> None:
    """Set the search_path on the given session/connection when a schema is configured."""

    if not _SCHEMA_NAME:
        return

    quoted_schema = _quote_identifier(_SCHEMA_NAME)
    await target.execute(text(f'SET search_path TO "{quoted_schema}", public'))


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Async context manager that yields a configured SQLAlchemy session."""

    async with SessionFactory() as session:
        await _ensure_search_path(session)
        yield session


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency-compatible generator yielding a configured session."""

    async with session_scope() as session:
        yield session


async def init_models() -> None:
    """Create database tables if they do not exist."""

    async with engine.begin() as conn:
        if _SCHEMA_NAME:
            quoted_schema = _quote_identifier(_SCHEMA_NAME)
            await conn.execute(
                text(f'CREATE SCHEMA IF NOT EXISTS "{quoted_schema}"')
            )
        await _ensure_search_path(conn)
        await conn.run_sync(Base.metadata.create_all)

    if _SCHEMA_NAME:
        logger.info("Ensured database tables in schema '%s'.", _SCHEMA_NAME)
    else:
        logger.info("Ensured database tables in default schema.")


async def dispose_engine() -> None:
    """Dispose of the engine and release pooled connections."""

    await engine.dispose()
