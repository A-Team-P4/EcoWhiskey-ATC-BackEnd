"""Persistence helpers for Stage 07 of the audio pipeline."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


_CONTEXT_FIELDS = (
    "scenario_id",
    "scenario",
    "meteo",
    "route",
    "objectives",
    "default_frequency_group",
    "frequencies",
    "transponder",
    "squawk",
    "taxi_route",
    "phase_id",
    "session_completed",
)


def context_base(ctx: Mapping[str, Any], history: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build the payload persisted alongside each turn for audit/debug purposes."""

    base = {k: ctx[k] for k in _CONTEXT_FIELDS if ctx.get(k) is not None}
    scenario = base.get("scenario")
    if isinstance(scenario, Mapping):
        base["scenario"] = {k: v for k, v in scenario.items() if k != "_phase_map"}
    base["turns"] = [dict(t) for t in history]
    return base


__all__ = ["context_base"]
