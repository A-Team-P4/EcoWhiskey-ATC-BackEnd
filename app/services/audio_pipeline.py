"""Audio pipeline orchestration with structured LLM responses.

This module loads per-session context (scenario, phase, frequencies, weather),
constructs prompts tailored for the active controller role, invokes the Bedrock
client, and validates the JSON contract returned by the model.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from app.services.context_repository import get_context as get_session_context
from app.services.llm_client import BedrockLlmClient
from app.services.prompt_builder import PromptContext, build_prompt
from app.services.response_contract import (
    ResponseContractError,
    StructuredLlmResponse,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmRequest:
    """Information required to contact the conversational model."""

    transcript: str
    context: Mapping[str, Any]
    intent: str
    frequency: str
    frequency_group: str
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True)
class LlmOutcome:
    """Result of rendering a controller response via the LLM + template."""

    response: StructuredLlmResponse
    raw_response: str


_RESOURCE_ROOT = Path(__file__).resolve().parents[1] / "resources"
_SCENARIO_ROOT = _RESOURCE_ROOT / "scenarios"
_LLM_CLIENT = BedrockLlmClient()


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
    """Split a wind string formatted as `ddd/ss` into components if possible."""
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

    common_phase_payload: dict[str, Any] = {}
    if wind_direction is not None:
        common_phase_payload["wind_direction"] = wind_direction
    if wind_speed is not None:
        common_phase_payload["wind_speed"] = wind_speed
    if qnh_value:
        common_phase_payload["qnh"] = qnh_value
    if transponder_value:
        common_phase_payload["squawk"] = transponder_value

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
_DEFAULT_SCENARIO_ID = "mrpv_vfr_departure"


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

def _extract_controller_role(phase: Mapping[str, Any] | None) -> str | None:
    if not isinstance(phase, Mapping):
        return None
    llm_section = phase.get("llm")
    if isinstance(llm_section, Mapping):
        role = llm_section.get("role")
        if isinstance(role, str) and role.strip():
            return role.strip()
    controller = phase.get("controller")
    if isinstance(controller, Mapping):
        role = controller.get("role")
        if isinstance(role, str) and role.strip():
            return role.strip()
    return None

def _truncate(value: str, max_length: int = 240) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


async def fetch_session_context(session_id: UUID) -> Mapping[str, Any]:
    """Pull any relevant context for the session from the database."""

    context_state = await get_session_context(session_id)
    turns = context_state.get("turns", [])

    stored_context = {
        key: value for key, value in context_state.items() if key != "turns"
    }

    # Assemble a scenario snapshot that blends static JSON with per-session overrides.
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
        "objectives": stored_context.get("objectives"),
        "transponder": stored_context.get("transponder")
        or stored_context.get("squawk"),
        "frequencies": scenario_frequencies,
        "turn_history": turns,
        "recent_turns": turns[-8:],
    }


async def build_llm_request(
    transcript: str,
    context: Mapping[str, Any],
    *,
    phase: Mapping[str, Any] | None,
    intent: str,
    frequency: str,
    frequency_group: str,
) -> LlmRequest:
    """Assemble prompts and metadata for the LLM invocation."""

    prompt_context = PromptContext(
        frequency_group=frequency_group,
        airport=context.get("airport", "MRPV"),
        phase_id=phase.get("id") if isinstance(phase, Mapping) else None,
        phase_name=phase.get("name") if isinstance(phase, Mapping) else None,
        controller_role=_extract_controller_role(phase),
        recent_turns=context.get("recent_turns"),
    )

    # `build_prompt` stitches together scenario/phase details into the JSON-first prompt.
    prompt_bundle = build_prompt(
        intent=intent,
        context=prompt_context,
        transcript=transcript,
        scenario=context.get("scenario"),
        phase=phase,
        turn_history=context.get("turn_history"),
    )

    logger.info(
        "Prompts generados intent=%s freq_group=%s\nSYSTEM> %s\nUSER> %s",
        intent,
        frequency_group,
        _truncate(prompt_bundle.system_prompt, 500),
        _truncate(prompt_bundle.user_prompt, 500),
    )

    return LlmRequest(
        transcript=transcript,
        context=context,
        intent=intent,
        frequency=frequency,
        frequency_group=frequency_group,
        system_prompt=prompt_bundle.system_prompt,
        user_prompt=prompt_bundle.user_prompt,
    )


async def call_conversation_llm(request: LlmRequest) -> LlmOutcome:
    """Invoke the LLM, validate the response contract, and render the phrase."""

    # Single point where Bedrock is contacted; wraps transport with contract validation.
    raw_response = await _LLM_CLIENT.invoke(
        system_prompt=request.system_prompt,
        user_prompt=request.user_prompt,
    )
    if not raw_response:
        raise ResponseContractError("LLM devolvió una respuesta vacía.")

    logger.info(
        "Respuesta LLM cruda intent=%s: %s",
        request.intent,
        _truncate(raw_response, 500),
    )

    structured = StructuredLlmResponse.from_json(raw_response)
    if structured.intent and structured.intent != request.intent:
        logger.info(
            "Intent devuelto por el LLM (%s) difiere del esperado (%s)",
            structured.intent,
            request.intent,
        )
    return LlmOutcome(
        response=structured,
        raw_response=raw_response,
    )


__all__ = [
    "LlmRequest",
    "LlmOutcome",
    "fetch_session_context",
    "build_llm_request",
    "call_conversation_llm",
]
