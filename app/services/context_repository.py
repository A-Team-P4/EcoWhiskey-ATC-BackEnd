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
from app.services.session_memory import (
    append_turn as memory_append_turn,
    get_turns as memory_get_turns,
    set_turns as memory_set_turns,
)

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
            return {
                "turns": memory_get_turns(session_id),
            }

        stored = training_context.context or {}
        if not isinstance(stored, dict):
            logger.warning(
                "Contexto corrupto para session_id=%s; reseteando", session_id
            )
            return {
                "turns": memory_get_turns(session_id),
            }

        # Return a shallow copy so callers can mutate safely.
        context_copy: MutableMapping[str, Any] = dict(stored)
        turns = list(context_copy.get("turns", []))
        if turns:
            memory_set_turns(session_id, turns)
        else:
            turns = memory_get_turns(session_id)
        context_copy["turns"] = turns
        return context_copy


async def append_turn(
    session_id: UUID,
    turn: Mapping[str, Any],
    *,
    user_id: int | None = None,
    base_context: Mapping[str, Any] | None = None,
) -> None:
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
        memory_append_turn(session_id, enriched_turn)

        if not training_context:
            if user_id is None:
                logger.warning(
                    "No se puede registrar turno; TrainingContext inexistente session_id=%s",
                    session_id,
                )
                return
            context_data: dict[str, Any] = {}
            if base_context:
                context_data.update({k: v for k, v in base_context.items() if k != "turns"})
            base_turns = []
            if base_context and isinstance(base_context.get("turns"), list):
                base_turns = [
                    dict(item) if isinstance(item, Mapping) else item
                    for item in base_context["turns"]
                ]
            base_turns.append(enriched_turn)
            context_data["turns"] = base_turns[-MAX_TURNS_STORED:]
            training_context = TrainingContext(
                training_session_id=session_id,
                user_id=user_id,
                context=context_data,
            )
            session.add(training_context)
        else:
            raw_context = training_context.context or {}
            if not isinstance(raw_context, dict):
                raw_context = {}
            context_data: dict[str, Any] = dict(raw_context)
            base_turns = None
            if base_context:
                base_copy = dict(base_context)
                base_turns = base_copy.pop("turns", None)
                if base_copy:
                    context_data.update(base_copy)
            if isinstance(base_turns, list):
                turns = [
                    dict(item) if isinstance(item, Mapping) else item
                    for item in base_turns
                ]
            else:
                turns = list(context_data.get("turns", []))
            turns.append(enriched_turn)
            context_data["turns"] = turns[-MAX_TURNS_STORED:]
            training_context.context = context_data

        await session.commit()


__all__ = ["get_context", "append_turn", "MAX_TURNS_STORED"]
