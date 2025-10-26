"""Repository helpers for reading/writing training session context."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, MutableMapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from app.database import SessionFactory
from app.models.training_context import TrainingContext

logger = logging.getLogger(__name__)

MAX_TURNS_STORED = 40


async def get_context(session_id: UUID) -> MutableMapping[str, Any]:
    """Return the stored context for the training session (mutable copy)."""

    async with SessionFactory() as session:
        result = await session.execute(
            select(TrainingContext).where(
                TrainingContext.training_session_id == session_id
            )
        )
        training_context = result.scalar_one_or_none()
        if not training_context:
            logger.debug(
                "No TrainingContext encontrado para session_id=%s", session_id
            )
            return {"turns": []}

        stored = training_context.context or {}
        if not isinstance(stored, dict):
            logger.warning(
                "Contexto corrupto para session_id=%s; reseteando", session_id
            )
            return {"turns": []}

        # Return a shallow copy so callers can mutate safely.
        context_copy: MutableMapping[str, Any] = dict(stored)
        turns = list(context_copy.get("turns", []))
        context_copy["turns"] = turns
        return context_copy


async def append_turn(session_id: UUID, turn: Mapping[str, Any]) -> None:
    """Append a turn to the training session context."""

    enriched_turn = dict(turn)
    enriched_turn.setdefault(
        "timestamp",
        datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )

    async with SessionFactory() as session:
        result = await session.execute(
            select(TrainingContext).where(
                TrainingContext.training_session_id == session_id
            )
        )
        training_context = result.scalar_one_or_none()
        if not training_context:
            logger.warning(
                "No se puede registrar turno; TrainingContext inexistente session_id=%s",
                session_id,
            )
            return

        context_data = training_context.context or {}
        if not isinstance(context_data, dict):
            context_data = {}

        turns = list(context_data.get("turns", []))
        turns.append(enriched_turn)
        context_data["turns"] = turns[-MAX_TURNS_STORED:]

        training_context.context = context_data
        await session.commit()


__all__ = ["get_context", "append_turn"]
