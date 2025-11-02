"""In-memory fallback store for session conversation turns."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence
from uuid import UUID

_MAX_TURNS = 40
_turns_store: dict[str, list[dict[str, Any]]] = {}


def get_turns(session_id: UUID) -> list[dict[str, Any]]:
    """Return a list of stored turns for the session (copy)."""

    return list(_turns_store.get(str(session_id), []))


def set_turns(session_id: UUID, turns: Sequence[Mapping[str, Any]]) -> None:
    """Replace the stored turns for the session (truncate to limit)."""

    key = str(session_id)
    _turns_store[key] = [dict(turn) for turn in turns][-_MAX_TURNS :]


def append_turn(session_id: UUID, turn: Mapping[str, Any]) -> None:
    """Append a single turn to the in-memory store."""

    key = str(session_id)
    entry = _turns_store.setdefault(key, [])
    entry.append(dict(turn))
    if len(entry) > _MAX_TURNS:
        del entry[:-_MAX_TURNS]


__all__ = ["get_turns", "set_turns", "append_turn"]
