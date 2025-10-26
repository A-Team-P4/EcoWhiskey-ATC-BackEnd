"""Audio pipeline orchestration with structured LLM responses."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID

from pydantic import ValidationError

from app.services.context_repository import get_context as get_session_context
from app.services.intent_detector import IntentDetector
from app.services.llm_client import BedrockLlmClient, LlmInvocationError
from app.services.prompt_builder import PromptContext, build_prompt
from app.services.response_contract import (
    IntentClassificationResponse,
    ResponseContractError,
    StructuredLlmResponse,
)
from app.services.template_renderer import (
    RenderedPhrase,
    TemplateRenderError,
    TemplateRenderer,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrequencyValidationResult:
    """Outcome of checking whether the transcript matches the target frequency."""

    is_valid: bool
    intent: str | None
    frequency_group: str | None
    reason: str | None = None
    confidence: float | None = None
    matched_tokens: Sequence[str] | None = None


@dataclass(frozen=True)
class LlmRequest:
    """Information required to contact the conversational model."""

    transcript: str
    context: Mapping[str, Any]
    intent: str
    frequency: str
    frequency_group: str
    template_id: str
    system_prompt: str
    user_prompt: str
    required_slots: Sequence[str]
    optional_slots: Sequence[str]


@dataclass(frozen=True)
class LlmOutcome:
    """Result of rendering a controller response via the LLM + template."""

    rendered: RenderedPhrase
    raw_response: str | None
    structured: StructuredLlmResponse | None
    used_fallback: bool
    warnings: Sequence[str]
    fallback_reason: str | None = None


_RESOURCE_ROOT = Path(__file__).resolve().parents[1] / "resources"
_TEMPLATE_ROOT = _RESOURCE_ROOT / "templates"
_SCENARIO_ROOT = _RESOURCE_ROOT / "scenarios"
_INTENT_DETECTOR = IntentDetector.from_directory(_RESOURCE_ROOT / "intents")
_TEMPLATE_RENDERER = TemplateRenderer(_TEMPLATE_ROOT)
_LLM_CLIENT = BedrockLlmClient()


def _load_resource_json(relative_path: str) -> Mapping[str, Any]:
    resource_path = _RESOURCE_ROOT / relative_path
    if not resource_path.exists():
        return {}
    with resource_path.open("r", encoding="utf-8") as resource_file:
        return json.load(resource_file)


def _normalize_frequency_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _generate_frequency_variants(value: Any) -> set[str]:
    variants: set[str] = set()
    normalized = _normalize_frequency_value(value)
    if not normalized:
        return variants
    variants.add(normalized)
    try:
        freq_float = float(normalized)
    except (TypeError, ValueError):
        return variants
    for decimals in (1, 2, 3):
        variants.add(f"{freq_float:.{decimals}f}")
    return variants


_TOWER_FREQ_DATA = _load_resource_json("frequencies/mrpv_tower.json")
_EXPECTED_TOWER_FREQUENCIES = {
    str(value).strip() for value in _TOWER_FREQ_DATA.get("frequencies", [])
} or {"118.3", "118.30", "118.300"}

_GROUND_FREQ_DATA = _load_resource_json("frequencies/mrpv_ground.json")
_EXPECTED_GROUND_FREQUENCIES = {
    str(value).strip() for value in _GROUND_FREQ_DATA.get("frequencies", [])
} or {"121.7"}

_FREQUENCY_GROUPS: Mapping[str, set[str]] = {
    "tower": set(_EXPECTED_TOWER_FREQUENCIES),
    "ground": set(_EXPECTED_GROUND_FREQUENCIES),
}

_AIRPORT_PROFILE = _load_resource_json("airports/mrpv.json")
_DEFAULT_SCENARIO_ID = "mrpv_vfr_departure"


def _load_scenarios() -> Mapping[str, Mapping[str, Any]]:
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

_NATO_WORD_TO_LETTER = {
    key.lower(): value
    for key, value in _load_resource_json("reference/nato_alphabet.json").items()
}
_LETTER_TO_NATO_WORD = {}
for word, letter in _NATO_WORD_TO_LETTER.items():
    _LETTER_TO_NATO_WORD.setdefault(letter.upper(), word.capitalize())

_DIGIT_TO_WORD = {
    "0": "cero",
    "1": "uno",
    "2": "dos",
    "3": "tres",
    "4": "cuatro",
    "5": "cinco",
    "6": "seis",
    "7": "siete",
    "8": "ocho",
    "9": "nueve",
}
_WORD_TO_DIGIT = {value: key for key, value in _DIGIT_TO_WORD.items()}


def _truncate(value: str, max_length: int = 240) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


async def _classify_intent_via_llm(transcript: str) -> IntentClassificationResponse | None:
    if not transcript or _LLM_CLIENT is None:
        return None

    intents_catalog = [
        {
            "id": definition.id,
            "frequency_group": definition.frequency_group or ""
        }
        for definition in _INTENT_DETECTOR.definitions
    ]

    system_prompt = (
        "Actúas como un clasificador de intenciones ATC en español. "
        "Solo debes responder con JSON válido que indique el intent más probable, "
        "su confianza (0-1) y el grupo de frecuencia asociado. Si ninguna opción aplica, "
        "responde con intent \"unknown\", confidence 0.0 y frequencyGroup vacía."
    )

    options_lines = "\n".join(
        f"- {item['id']} (frequency_group={item['frequency_group'] or 'n/a'})"
        for item in intents_catalog
    )

    user_prompt = (
        "Transcripción del alumno:\n"
        f"{transcript.strip()}\n\n"
        "Intents disponibles:\n"
        f"{options_lines}\n\n"
        "Responde SOLO con JSON como en el ejemplo:\n"
        '{"intent": "tower_takeoff_clearance", "confidence": 0.8, "frequencyGroup": "tower"}'
    )

    logger.info(
        "Clasificador LLM opciones=%s transcript='%s'",
        intents_catalog,
        _truncate(transcript, 300),
    )

    try:
        raw = await _LLM_CLIENT.invoke(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if raw:
            logger.info("Clasificación LLM cruda: %s", _truncate(raw, 400))
    except LlmInvocationError as exc:
        logger.warning("Clasificación LLM falló: %s", exc)
        return None

    if not raw:
        return None

    try:
        result = IntentClassificationResponse.from_json(raw)
    except ValidationError as exc:
        logger.warning("Respuesta LLM clasificación inválida: %s", exc)
        return None

    if result.intent.lower() in {"", "unknown"}:
        return None

    return result


async def fetch_session_context(session_id: UUID) -> Mapping[str, Any]:
    """Pull any relevant context for the session from the database."""

    context_state = await get_session_context(session_id)
    turns = context_state.get("turns", [])

    scenario_id = (
        context_state.get("scenario_id")
        or (context_state.get("scenario") or {}).get("id")
        or _DEFAULT_SCENARIO_ID
    )
    scenario = _SCENARIOS.get(scenario_id) or _SCENARIOS.get(_DEFAULT_SCENARIO_ID, {})
    if not scenario:
        logger.debug("No se encontró escenario para session_id=%s id=%s", session_id, scenario_id)

    frequency_map: dict[str, str] = {}
    frequency_intents: dict[str, str] = {}
    scenario_frequencies = scenario.get("frequencies", {}) or {}
    for group, value in scenario_frequencies.items():
        for variant in _generate_frequency_variants(value):
            if variant:
                frequency_map[variant] = group

    for group in ("ground", "tower", "approach", "radar"):
        section = scenario.get(group)
        if isinstance(section, Mapping):
            intent_id = section.get("intent")
            if isinstance(intent_id, str) and intent_id:
                frequency_intents[group] = intent_id

    default_frequency_group = scenario.get("default_frequency_group")
    if not default_frequency_group:
        if "ground" in frequency_intents:
            default_frequency_group = "ground"
        elif "tower" in frequency_intents:
            default_frequency_group = "tower"

    return {
        "airport": "MRPV",
        "session_id": str(session_id),
        "scenario_id": scenario.get("id") if scenario else None,
        "scenario": scenario,
        "default_runway": (
            (scenario.get("tower", {}) or {}).get("runway_human")
            or (scenario.get("ground", {}) or {}).get("runway_human")
            or _AIRPORT_PROFILE.get("default_runway", "uno cero")
        ),
        "alternate_runway": _AIRPORT_PROFILE.get("alternate_runway"),
        "frequency_map": frequency_map,
        "frequency_intents": frequency_intents,
        "default_frequency_group": default_frequency_group,
        "recent_turns": turns[-8:],
    }


async def validate_frequency_intent(
    transcript: str,
    frequency: str,
) -> FrequencyValidationResult:
    """Verify the caller is using the correct frequency based on intent."""

    normalized_frequency = frequency.strip()
    detected_intent = _INTENT_DETECTOR.detect(transcript)

    if not detected_intent:
        llm_intent = await _classify_intent_via_llm(transcript)
        if llm_intent:
            allowed = _FREQUENCY_GROUPS.get(llm_intent.frequency_group or "")
            if allowed and normalized_frequency not in allowed:
                expected = ", ".join(sorted(allowed))
                logger.info(
                    "Frecuencia fuera de rango (LLM) intent=%s freq=%s esperado=%s",
                    llm_intent.intent,
                    normalized_frequency,
                    expected,
                )
                return FrequencyValidationResult(
                    is_valid=False,
                    intent=llm_intent.intent,
                    frequency_group=llm_intent.frequency_group,
                    reason=f"La frecuencia esperada para esta solicitud es {expected}.",
                    confidence=llm_intent.confidence,
                )

            logger.info(
                "Intent determinado via LLM id=%s confianza=%.2f",
                llm_intent.intent,
                llm_intent.confidence or 0.0,
            )
            return FrequencyValidationResult(
                is_valid=True,
                intent=llm_intent.intent,
                frequency_group=llm_intent.frequency_group,
                confidence=llm_intent.confidence,
            )

        logger.info("Intent no detectado transcript='%s'", _truncate(transcript))
        return FrequencyValidationResult(
            is_valid=True,
            intent=None,
            frequency_group=None,
        )

    allowed_frequencies = _FREQUENCY_GROUPS.get(
        detected_intent.frequency_group or ""
    )
    if allowed_frequencies and normalized_frequency not in allowed_frequencies:
        expected = ", ".join(sorted(allowed_frequencies))
        logger.info(
            "Frecuencia fuera de rango intent=%s freq=%s esperado=%s",
            detected_intent.id,
            normalized_frequency,
            expected,
        )
        return FrequencyValidationResult(
            is_valid=False,
            intent=detected_intent.id,
            frequency_group=detected_intent.frequency_group,
            reason=f"La frecuencia esperada para esta solicitud es {expected}.",
            confidence=detected_intent.confidence,
            matched_tokens=detected_intent.matched_tokens,
        )

    logger.info(
        "Intent detectado id=%s confianza=%.2f tokens=%s",
        detected_intent.id,
        detected_intent.confidence or 0.0,
        detected_intent.matched_tokens,
    )
    return FrequencyValidationResult(
        is_valid=True,
        intent=detected_intent.id,
        frequency_group=detected_intent.frequency_group,
        confidence=detected_intent.confidence,
        matched_tokens=detected_intent.matched_tokens,
    )


async def build_llm_request(
    transcript: str,
    context: Mapping[str, Any],
    *,
    intent: str,
    frequency: str,
    frequency_group: str,
) -> LlmRequest:
    """Assemble prompts and metadata for the LLM invocation."""

    template = _TEMPLATE_RENDERER.get(intent)
    if not template:
        raise TemplateRenderError(f"No existe plantilla para intent '{intent}'.")

    scenario = context.get("scenario") or {}
    scenario_defaults: Mapping[str, Any] = scenario.get(frequency_group, {}) or {}
    runway_conditions = None
    if scenario_defaults.get("runway_human"):
        runway_conditions = f"Pista en uso {scenario_defaults['runway_human']}"
    elif scenario_defaults.get("runway"):
        runway_conditions = f"Pista en uso {scenario_defaults['runway']}"

    weather_bits: list[str] = []
    wind_report = _format_wind_report(
        scenario_defaults.get("wind_direction"),
        scenario_defaults.get("wind_speed"),
    )
    if wind_report:
        weather_bits.append(f"Viento {wind_report}")
    qnh_value = scenario_defaults.get("qnh")
    if qnh_value:
        weather_bits.append(f"QNH {qnh_value}")
    weather_snippet = ", ".join(weather_bits) if weather_bits else None

    prompt_context = PromptContext(
        frequency_group=frequency_group,
        airport=context.get("airport", "MRPV"),
        runway_conditions=runway_conditions,
        weather_snippet=weather_snippet,
        recent_turns=context.get("recent_turns"),
    )

    prompt_bundle = build_prompt(
        intent=intent,
        context=prompt_context,
        transcript=transcript,
        required_slots=template.required_slots,
        optional_slots=template.optional_slots,
        template_example={
            "intent": intent,
            "confidence": 0.8,
            "slots": {slot: f"<{slot}>" for slot in template.required_slots},
            "notes": {"observations": []},
        },
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
        template_id=template.template_id,
        system_prompt=prompt_bundle.system_prompt,
        user_prompt=prompt_bundle.user_prompt,
        required_slots=template.required_slots,
        optional_slots=template.optional_slots,
    )


async def call_conversation_llm(request: LlmRequest) -> LlmOutcome:
    """Invoke the LLM, validate the response contract, and render the phrase."""

    raw_response: str | None = None
    structured: StructuredLlmResponse | None = None
    fallback_reason: str | None = None

    try:
        raw_response = await _LLM_CLIENT.invoke(
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
        )
        if not raw_response:
            fallback_reason = "empty_response"
            raise LlmInvocationError("Respuesta vacía del modelo.")

        logger.info(
            "Respuesta LLM cruda intent=%s: %s",
            request.intent,
            _truncate(raw_response, 500),
        )

        structured = StructuredLlmResponse.from_json(raw_response)
        logger.info(
            "Respuesta LLM estructurada intent=%s slots=%s",
            request.intent,
            structured.slots.model_dump(),
        )
        if structured.intent != request.intent:
            fallback_reason = f"intent_mismatch:{structured.intent}"
            raise ResponseContractError(
                f"LLM devolvió intent '{structured.intent}' diferente al esperado "
                f"'{request.intent}'."
            )

        normalized_slots, warnings = _normalize_slots(
            structured=structured,
            transcript=request.transcript,
            context=request.context,
        )
        template_render = _TEMPLATE_RENDERER.render(
            request.template_id,
            slots=normalized_slots,
        )
        logger.info(
            "Plantilla renderizada intent=%s texto='%s'",
            request.intent,
            template_render.text,
        )
        if warnings:
            logger.info(
                "Normalización de slots con advertencias (%s): %s",
                request.intent,
                warnings,
            )
        return LlmOutcome(
            rendered=template_render,
            raw_response=raw_response,
            structured=structured,
            used_fallback=False,
            warnings=warnings,
        )

    except (LlmInvocationError, ValidationError, ResponseContractError, TemplateRenderError) as exc:
        fallback_reason = fallback_reason or exc.__class__.__name__
        logger.warning(
            "Fallback activado para intent=%s (motivo=%s)",
            request.intent,
            fallback_reason,
        )
        fallback_slots, fallback_warnings = _normalize_slots(
            structured=None,
            transcript=request.transcript,
            context=request.context,
        )
        try:
            rendered = _TEMPLATE_RENDERER.render(
                request.template_id,
                slots=fallback_slots,
            )
            logger.info(
                "Plantilla fallback intent=%s texto='%s'",
                request.intent,
                rendered.text,
            )
        except TemplateRenderError:
            # Último recurso: frase genérica.
            text = _build_default_phrase(fallback_slots)
            rendered = RenderedPhrase(
                text=text,
                template_id=request.template_id,
                slots=fallback_slots,
                metadata={"fallback": True},
            )
        return LlmOutcome(
            rendered=rendered,
            raw_response=raw_response,
            structured=structured,
            used_fallback=True,
            warnings=fallback_warnings,
            fallback_reason=fallback_reason,
        )


async def render_response_text(
    outcome: LlmOutcome,
    *,
    fallback_transcript: str,
) -> str:
    """Return the rendered phrase or fall back to the transcript."""

    return outcome.rendered.text or fallback_transcript


def _normalize_slots(
    *,
    structured: StructuredLlmResponse | None,
    transcript: str,
    context: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []

    scenario: Mapping[str, Any] = context.get("scenario") or {}
    scenario_student: Mapping[str, Any] = scenario.get("student") or {}
    active_frequency_group: str | None = context.get("active_frequency_group")
    scenario_defaults: Mapping[str, Any] = {}
    if active_frequency_group:
        scenario_defaults = scenario.get(active_frequency_group, {}) or {}

    fallback_callsign = _extract_callsign(transcript)
    fallback_callsign_spelled = (
        _spell_callsign(fallback_callsign) if fallback_callsign else None
    )
    fallback_runway_human = _extract_runway(transcript)
    default_runway = context.get("default_runway")

    slots_payload = structured.slots if structured else None

    callsign = (
        (slots_payload.callsign if slots_payload else None)
        or fallback_callsign
        or scenario_student.get("callsign")
    )
    if callsign:
        callsign = callsign.upper()
    else:
        callsign = "TRAFICO"
        warnings.append("missing_callsign")

    callsign_spelled = (
        (slots_payload.callsign_spelled if slots_payload else None)
        or fallback_callsign_spelled
        or scenario_student.get("callsign_spelled")
        or _spell_callsign(callsign)
    )
    if callsign_spelled and "no callsign" in callsign_spelled.lower():
        warnings.append("invalid_callsign_spelled")
        callsign_spelled = _spell_callsign(callsign)

    runway, runway_human = _normalize_runway_values(
        runway=slots_payload.runway if slots_payload else None,
        runway_human=slots_payload.runway_human if slots_payload else None,
        fallback_human=fallback_runway_human,
        default_human=default_runway,
    )
    if not runway or not runway_human:
        warnings.append("missing_runway")

    normalized: dict[str, Any] = {
        "callsign": callsign,
        "callsign_spelled": callsign_spelled,
        "runway": runway,
        "runway_human": runway_human,
    }

    if slots_payload:
        if slots_payload.instruction_code:
            normalized["instruction_code"] = slots_payload.instruction_code
        if slots_payload.instruction:
            normalized["instruction"] = slots_payload.instruction
        if slots_payload.heading is not None:
            normalized["heading"] = slots_payload.heading
        if slots_payload.altitude_ft is not None:
            normalized["altitude_ft"] = slots_payload.altitude_ft
        if slots_payload.souls_on_board is not None:
            normalized["souls_on_board"] = slots_payload.souls_on_board
        if slots_payload.fuel_endurance_minutes is not None:
            normalized["fuel_endurance_minutes"] = slots_payload.fuel_endurance_minutes

    instruction_codes: list[str] = []
    default_instruction_codes: list[str] = []
    defaults_seq = scenario_defaults.get("instruction_codes")
    if isinstance(defaults_seq, Sequence):
        default_instruction_codes = [
            str(code) for code in defaults_seq if str(code)
        ]

    if slots_payload:
        if slots_payload.instruction_codes:
            instruction_codes.extend(slots_payload.instruction_codes)
        if slots_payload.instruction_code:
            instruction_codes.append(slots_payload.instruction_code)
    if not instruction_codes:
        instruction_codes.extend(default_instruction_codes)

    readback_cfg = scenario_defaults.get("readback")
    if readback_cfg and active_frequency_group == "ground":
        readback_complete, missing_items = _evaluate_readback(transcript, readback_cfg)
        if readback_complete:
            instruction_codes = ["acknowledge"]
            warnings.append("readback_confirmed")
        else:
            joined_missing = ", ".join(missing_items)
            normalized["missing_readback_items"] = joined_missing
            reissue_codes = default_instruction_codes or instruction_codes
            instruction_codes = ["readback_correction"] + reissue_codes
            warnings.append("readback_incomplete")

    if instruction_codes:
        unique_codes: list[str] = []
        seen_codes: set[str] = set()
        for code in instruction_codes:
            code_str = str(code)
            if code_str and code_str not in seen_codes:
                seen_codes.add(code_str)
                unique_codes.append(code_str)
        if unique_codes:
            normalized["instruction_codes"] = unique_codes

    wind_direction = (
        (slots_payload.wind_direction if slots_payload else None)
        or scenario_defaults.get("wind_direction")
    )
    wind_speed = (
        (slots_payload.wind_speed if slots_payload else None)
        or scenario_defaults.get("wind_speed")
    )
    wind_report = (
        (slots_payload.wind_report if slots_payload else None)
        or scenario_defaults.get("wind_report")
        or _format_wind_report(wind_direction, wind_speed)
    )
    if wind_direction is not None:
        normalized["wind_direction"] = wind_direction
    if wind_speed is not None:
        normalized["wind_speed"] = wind_speed
    if wind_report:
        normalized["wind_report"] = wind_report

    qnh_value = (
        (slots_payload.qnh_value if slots_payload else None)
        or scenario_defaults.get("qnh")
    )
    if qnh_value:
        normalized["qnh_value"] = qnh_value

    squawk_code = (
        (slots_payload.squawk_code if slots_payload else None)
        or scenario_defaults.get("squawk")
    )
    if squawk_code:
        normalized["squawk_code"] = squawk_code

    taxi_route = (
        (slots_payload.taxi_route if slots_payload else None)
        or scenario_defaults.get("taxi_route")
    )
    if taxi_route:
        normalized["taxi_route"] = taxi_route

    advisory_text = (
        (slots_payload.advisory_text if slots_payload else None)
        or scenario_defaults.get("advisory")
    )
    if advisory_text:
        normalized["advisory_text"] = advisory_text

    climb_instruction = (
        (slots_payload.climb_instruction if slots_payload else None)
        or scenario_defaults.get("climb_instruction")
    )
    if climb_instruction:
        normalized["climb_instruction"] = climb_instruction

    report_altitude_ft = (
        (slots_payload.report_altitude_ft if slots_payload else None)
        or scenario_defaults.get("report_altitude_ft")
    )
    report_altitude_phrase = None
    if report_altitude_ft:
        report_altitude_phrase = _format_altitude_phrase(report_altitude_ft)
        normalized["report_altitude_ft"] = report_altitude_ft
    if report_altitude_phrase:
        normalized["report_altitude_phrase"] = report_altitude_phrase

    next_frequency_phrase = (
        (slots_payload.next_frequency_phrase if slots_payload else None)
        or scenario_defaults.get("next_frequency")
    )
    if next_frequency_phrase:
        normalized["next_frequency_phrase"] = next_frequency_phrase

    default_instruction = scenario_defaults.get("default_instruction_code")
    normalized.setdefault(
        "instruction_code",
        default_instruction if isinstance(default_instruction, str) else "takeoff_clearance",
    )

    logger.info("Slots normalizados: %s", normalized)

    return normalized, warnings


def _spell_callsign(callsign: str | None) -> str:
    if not callsign:
        return "Tráfico"
    words = []
    for char in callsign.upper():
        if char.isalpha():
            words.append(_LETTER_TO_NATO_WORD.get(char, char))
        elif char.isdigit():
            words.append(_DIGIT_TO_WORD.get(char, char))
        else:
            words.append(char)
    return " ".join(words)


def _normalize_runway_values(
    *,
    runway: str | None,
    runway_human: str | None,
    fallback_human: str | None,
    default_human: str | None,
) -> tuple[str | None, str | None]:
    numeric = _clean_runway_numeric(runway)
    human = _clean_runway_human(runway_human)

    if not numeric and human:
        numeric = _human_to_numeric(human)
    if not human and numeric:
        human = _numeric_to_human(numeric)

    if not numeric and fallback_human:
        numeric = _human_to_numeric(fallback_human)
    if not human and fallback_human:
        human = _clean_runway_human(fallback_human)

    if not numeric and default_human:
        numeric = _human_to_numeric(default_human)
    if not human and default_human:
        human = _clean_runway_human(default_human)

    return numeric, human


def _clean_runway_numeric(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) == 0:
        return None
    if len(digits) == 1:
        digits = digits.zfill(2)
    elif len(digits) > 2:
        digits = digits[:2]
    return digits


def _clean_runway_human(value: str | None) -> str | None:
    if not value:
        return None
    words = [word.lower() for word in re.findall(r"[a-záéíóúñ]+|\d+", value)]
    mapped: list[str] = []
    for word in words:
        if word.isdigit() and len(word) <= 2:
            mapped.extend(_DIGIT_TO_WORD[digit] for digit in word)
        elif word in _WORD_TO_DIGIT:
            mapped.append(word)
    if not mapped:
        return None
    return " ".join(mapped)


def _human_to_numeric(value: str | None) -> str | None:
    if not value:
        return None
    digits = []
    for word in value.split():
        digit = _WORD_TO_DIGIT.get(word.lower())
        if digit is None:
            return None
        digits.append(digit)
    if not digits:
        return None
    return "".join(digits)


def _numeric_to_human(value: str | None) -> str | None:
    if not value:
        return None
    digits = _clean_runway_numeric(value)
    if not digits:
        return None
    return " ".join(_DIGIT_TO_WORD[d] for d in digits)


def _build_default_phrase(slots: Mapping[str, Any]) -> str:
    callsign_spelled = slots.get("callsign_spelled") or _spell_callsign(
        slots.get("callsign")
    )
    runway_human = slots.get("runway_human") or "uno cero"
    return f"{callsign_spelled}, autorizado a despegar pista {runway_human}"


def _evaluate_readback(
    transcript: str,
    config: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    required_sets = config.get("required") or []
    if not required_sets:
        return True, []

    text_lower = transcript.lower()
    text_compact = re.sub(r"\s+", "", text_lower)
    missing: list[str] = []

    for requirement in required_sets:
        if isinstance(requirement, str):
            options = [requirement]
        else:
            options = [
                str(option) for option in requirement if option is not None
            ]
        if not options:
            continue

        matched = False
        for option in options:
            option_norm = option.lower().strip()
            if not option_norm:
                continue
            if option_norm in text_lower:
                matched = True
                break
            option_compact = re.sub(r"\s+", "", option_norm)
            if option_compact and option_compact in text_compact:
                matched = True
                break
        if not matched:
            missing.append(options[0])

    return len(missing) == 0, missing


def _format_wind_report(direction: int | str | None, speed: int | str | None) -> str | None:
    if direction is None and speed is None:
        return None
    direction_str: str | None
    speed_str: str | None
    if isinstance(direction, int):
        direction_str = f"{direction:03d}"
    else:
        direction_str = str(direction).strip() if direction is not None else None
    if isinstance(speed, int):
        speed_str = f"{speed:02d}"
    else:
        speed_str = str(speed).strip() if speed is not None else None
    if not direction_str and not speed_str:
        return None
    if direction_str and speed_str:
        return f"{direction_str}/{speed_str}"
    return direction_str or speed_str


def _format_altitude_phrase(value: int | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value_str = value.strip()
        if value_str:
            return value_str
        return None
    return f"{value} pies"


def _extract_callsign(transcript: str) -> str | None:
    words_raw = re.findall(r"[A-Za-zÁÉÍÓÚÑ0-9]+", transcript)
    letters: list[str] = []
    for word in words_raw:
        normalized = word.lower()
        if normalized in _NATO_WORD_TO_LETTER:
            letters.append(_NATO_WORD_TO_LETTER[normalized])
    if letters:
        return "".join(letters).upper()

    for candidate in words_raw:
        cleaned = re.sub(r"[^A-Za-z0-9]", "", candidate).upper()
        if re.fullmatch(r"[A-Z0-9]{2,6}", cleaned):
            return cleaned
    return None


def _extract_runway(transcript: str) -> str | None:
    lower = transcript.lower()
    match_digits = re.search(r"pista\s*(\d{2})", lower)
    if match_digits:
        digits = match_digits.group(1)
        return " ".join(_DIGIT_TO_WORD[d] for d in digits)

    tokens = re.findall(r"[a-záéíóúñ]+", lower)
    for idx, token in enumerate(tokens):
        if token != "pista":
            continue
        sequence: list[str] = []
        for next_token in tokens[idx + 1 : idx + 4]:
            if next_token in _WORD_TO_DIGIT:
                sequence.append(next_token)
            else:
                break
        if sequence:
            return " ".join(sequence)
    return None


__all__ = [
    "FrequencyValidationResult",
    "LlmRequest",
    "LlmOutcome",
    "fetch_session_context",
    "validate_frequency_intent",
    "build_llm_request",
    "call_conversation_llm",
    "render_response_text",
]
