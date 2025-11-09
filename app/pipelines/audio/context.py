"""Session context loading stage for the audio analysis pipeline.

This module encapsulates everything related to retrieving and shaping the
per-session state that the downstream stages (prompt building, LLM) rely on.
It maps to **Stage 02** of the overall flow documented in ``flow.py``.
"""

from __future__ import annotations

import copy
import json
import logging
import random
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping
from uuid import UUID

from app.services.context_repository import get_context as get_session_context

logger = logging.getLogger("app.services.audio_pipeline")

_RESOURCE_ROOT = Path(__file__).resolve().parents[2] / "resources"
_SCENARIO_ROOT = _RESOURCE_ROOT / "scenarios"


def _load_resource_json(relative_path: str) -> Mapping[str, Any]:
    """Safely load optional JSON helpers (scenarios, airports) from disk."""

    resource_path = _RESOURCE_ROOT / relative_path
    if not resource_path.exists():
        return {}
    with resource_path.open("r", encoding="utf-8") as resource_file:
        return json.load(resource_file)


def _coerce_int(value: Any) -> int | None:
    """Best-effort integer conversion that tolerates strings and None."""

    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _parse_wind_components(value: Any) -> tuple[int | None, int | None]:
    """Split a wind string formatted as ``ddd/ss`` into components if possible."""

    direction = None
    speed = None
    if isinstance(value, str) and "/" in value:
        first, second = value.split("/", 1)
        direction = _coerce_int(first)
        speed = _coerce_int(second)
    return direction, speed


def _apply_context_overrides(
    scenario: dict[str, Any],
    stored_context: Mapping[str, Any],
) -> None:
    """Project live session data (METAR, squawk overrides, etc.) into the scenario copy."""

    if not isinstance(scenario, dict):
        return

    meteo = stored_context.get("meteo")
    wind_direction = None
    wind_speed = None
    qnh_value = None
    if isinstance(meteo, Mapping):
        wind_direction = (
            _coerce_int(meteo.get("windDirection"))
            or _parse_wind_components(meteo.get("wind"))[0]
        )
        wind_speed = (
            _coerce_int(meteo.get("windSpeed"))
            or _parse_wind_components(meteo.get("wind"))[1]
        )
        qnh_value = meteo.get("qnh")

    transponder_value = (
        stored_context.get("transponder")
        or stored_context.get("squawk")
        or (meteo.get("transponder") if isinstance(meteo, Mapping) else None)
    )

    shared = scenario.get("shared")
    if not isinstance(shared, dict):
        shared = {}
        scenario["shared"] = shared
    if wind_direction is not None:
        shared["wind_direction"] = wind_direction
    if wind_speed is not None:
        shared["wind_speed"] = wind_speed
    if qnh_value:
        shared["qnh"] = qnh_value
    if transponder_value:
        shared["squawk"] = transponder_value
    taxi_route_value = stored_context.get("taxi_route")
    if taxi_route_value:
        shared["taxi_route"] = taxi_route_value
    stored_student = stored_context.get("student")
    if isinstance(stored_student, Mapping) and stored_student:
        student_section = shared.get("student")
        if not isinstance(student_section, dict):
            student_section = {}
            shared["student"] = student_section
        for key, value in stored_student.items():
            student_section[key] = value

    common_phase_payload: dict[str, Any] = {}
    if wind_direction is not None:
        common_phase_payload["wind_direction"] = wind_direction
    if wind_speed is not None:
        common_phase_payload["wind_speed"] = wind_speed
    if qnh_value:
        common_phase_payload["qnh"] = qnh_value
    if transponder_value:
        common_phase_payload["squawk"] = transponder_value
    if taxi_route_value:
        common_phase_payload["taxi_route"] = taxi_route_value

    phases = scenario.get("phases")
    if isinstance(phases, list) and common_phase_payload:
        for phase in phases:
            if not isinstance(phase, dict):
                continue
            data_section = phase.get("data")
            if not isinstance(data_section, dict):
                data_section = {}
                phase["data"] = data_section
            for key, value in common_phase_payload.items():
                data_section[key] = value

    stored_frequencies = stored_context.get("frequencies")
    if isinstance(stored_frequencies, Mapping) and stored_frequencies:
        scenario["frequencies"] = dict(stored_frequencies)

    stored_scenario = stored_context.get("scenario_overrides")
    if isinstance(stored_scenario, Mapping):
        for key, value in stored_scenario.items():
            scenario[key] = value


_AIRPORT_PROFILE = _load_resource_json("airports/mrpv.json")

# TODO: ESTO ESTA QUEMADO ACA
_DEFAULT_SCENARIO_ID = "mrpv_full_flight" 
# TODO: ESTO ESTA QUEMADO ACA


def _load_scenarios() -> Mapping[str, Mapping[str, Any]]:
    """Disk-backed cache of available training scenarios."""

    scenarios: dict[str, Mapping[str, Any]] = {}
    if not _SCENARIO_ROOT.exists():
        return scenarios
    for scenario_path in _SCENARIO_ROOT.glob("*.json"):
        try:
            with scenario_path.open("r", encoding="utf-8") as scenario_file:
                data = json.load(scenario_file)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Escenario inválido %s: %s", scenario_path, exc)
            continue
        scenario_id = data.get("id") or scenario_path.stem
        scenarios[scenario_id] = data
    return scenarios


_SCENARIOS = _load_scenarios()
_TAXI_ROUTES: tuple[str, ...] = (
    "Alfa 2, Alfa",
    "Alfa 3, Alfa",
    "Alfa, Bravo",
    "Alfa, Charlie",
)


def _remember_assignment(
    store: MutableMapping[str, Any],
    assignments: MutableMapping[str, Any],
    key: str,
    factory: Callable[[], Any],
) -> Any:
    value = store.get(key) or assignments.get(key)
    if value is None:
        value = factory()
    assignments[key] = value
    store[key] = value
    return value


def _ensure_session_randomization(stored_context: MutableMapping[str, Any]) -> None:
    """Generate dynamic ATC parameters (squawk, viento, QNH) when missing."""

    assignments = stored_context.get("dynamic_assignments")
    if not isinstance(assignments, MutableMapping):
        assignments = {}
        stored_context["dynamic_assignments"] = assignments

    def squawk_factory() -> str:
        # Costa Rican tower typically assigns 05xx codes for local VFR departures.
        return f"{random.randint(500, 599):04d}"

    squawk = _remember_assignment(stored_context, assignments, "squawk", squawk_factory)
    stored_context.setdefault("transponder", squawk)

    def taxi_route_factory() -> str:
        return random.choice(_TAXI_ROUTES)

    _remember_assignment(stored_context, assignments, "taxi_route", taxi_route_factory)

    meteo_raw = stored_context.get("meteo")
    meteo: MutableMapping[str, Any]
    if isinstance(meteo_raw, MutableMapping):
        meteo = dict(meteo_raw)
    else:
        meteo = {}

    def wind_dir_factory() -> int:
        return random.choice((50, 60, 70, 80, 90, 100))

    def wind_speed_factory() -> int:
        return random.randint(6, 16)

    def qnh_factory() -> str:
        return str(random.randint(3000, 3012))

    wind_direction = _remember_assignment(meteo, assignments, "windDirection", wind_dir_factory)
    wind_speed = _remember_assignment(meteo, assignments, "windSpeed", wind_speed_factory)
    qnh_value = _remember_assignment(meteo, assignments, "qnh", qnh_factory)

    meteo.setdefault("wind", f"{int(wind_direction):03d}/{int(wind_speed):02d}")
    stored_context["meteo"] = meteo


async def fetch_session_context(session_id: UUID) -> Mapping[str, Any]:
    """Pull any relevant context for the session from the database."""

    context_state = await get_session_context(session_id)
    turns = context_state.get("turns", [])

    stored_context = {
        key: value for key, value in context_state.items() if key != "turns"
    }

    if isinstance(stored_context, MutableMapping):
        _ensure_session_randomization(stored_context)

    scenario_id = (
        stored_context.get("scenario_id")
        or (stored_context.get("scenario") or {}).get("id")
        or _DEFAULT_SCENARIO_ID
    )
    base_scenario = _SCENARIOS.get(scenario_id) or _SCENARIOS.get(_DEFAULT_SCENARIO_ID, {})
    scenario = copy.deepcopy(base_scenario) if base_scenario else {}

    stored_scenario = stored_context.get("scenario")
    if isinstance(stored_scenario, Mapping):
        scenario = copy.deepcopy(stored_scenario)

    phases = scenario.get("phases") or []
    phase_map = {phase["id"]: phase for phase in phases if phase.get("id")}
    scenario["_phase_map"] = phase_map

    if scenario:
        _apply_context_overrides(scenario, stored_context)
    else:
        scenario = {"phases": []}
        _apply_context_overrides(scenario, stored_context)
    scenario.setdefault("id", scenario_id)

    default_phase_id = (
        stored_context.get("phase_id")
        or scenario.get("default_phase")
        or (phases[0]["id"] if phases else None)
    )
    current_phase = phase_map.get(default_phase_id)
    if current_phase is None and phases:
        current_phase = phases[0]
        default_phase_id = current_phase.get("id")

    scenario_frequencies = (
        scenario.get("frequencies", {})
        or stored_context.get("frequencies", {})
        or {}
    )

    stored_frequency_map = stored_context.get("frequency_map")
    if isinstance(stored_frequency_map, Mapping) and stored_frequency_map:
        frequency_map = {
            str(key): str(value) for key, value in stored_frequency_map.items()
        }
    else:
        frequency_map = {
            str(key): str(value) for key, value in scenario_frequencies.items()
        }

    default_frequency_group = (
        stored_context.get("default_frequency_group")
        or scenario.get("default_frequency_group")
    )
    if not default_frequency_group and current_phase:
        default_frequency_group = current_phase.get("frequency")

    context_base = dict(stored_context)
    context_base["scenario"] = copy.deepcopy(scenario)
    context_base["scenario_id"] = scenario_id
    context_base["frequencies"] = scenario_frequencies
    if default_phase_id:
        context_base["phase_id"] = default_phase_id

    # The controller endpoint clones + mutates this structure when calling the LLM.
    return {
        "airport": "MRPV",
        "session_id": str(session_id),
        "scenario_id": scenario.get("id") if scenario else None,
        "scenario": scenario,
        "phase_id": default_phase_id,
        "phase": current_phase,
        "phase_map": phase_map,
        "default_runway": (
            (current_phase or {}).get("runway_human")
            or _AIRPORT_PROFILE.get("default_runway", "uno cero")
        ),
        "alternate_runway": _AIRPORT_PROFILE.get("alternate_runway"),
        "frequency_map": frequency_map,
        "default_frequency_group": default_frequency_group,
        "context_base": context_base,
        "meteo": stored_context.get("meteo"),
        "route": stored_context.get("route"),
        "taxi_route": stored_context.get("taxi_route"),
        "objectives": stored_context.get("objectives"),
        "transponder": stored_context.get("transponder")
        or stored_context.get("squawk"),
        "squawk": stored_context.get("squawk"),
        "frequencies": scenario_frequencies,
        "turn_history": turns,
        "recent_turns": turns[-8:],
    }


__all__ = ["fetch_session_context"]
