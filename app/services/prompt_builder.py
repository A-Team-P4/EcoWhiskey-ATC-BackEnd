"""Helpers to construct system/user prompts for the audio pipeline LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping, Sequence

PROMPT_TEMPLATES = {
    "tower": (
        "Eres un controlador de torre en español (Costa Rica). "
        "Gestionas autorizaciones de despegue/aterrizaje, transferencias y avisos de pista."
    ),
    "ground": (
        "Eres un controlador de superficie en español (Costa Rica). "
        "Gestionas rodajes, puntos de espera y pistas activas."
    ),
    "approach": (
        "Eres un controlador radar de aproximación en español (Costa Rica). "
        "Gestionas vectores, niveles y transferencias de frecuencia."
    ),
    "radar": (
        "Eres un controlador radar en español (Costa Rica). "
        "Entrega instrucciones concisas de rumbo, altitud y transferencia."
    ),
}


@dataclass(frozen=True)
class PromptContext:
    frequency_group: str
    airport: str
    phase_id: str | None = None
    phase_name: str | None = None
    controller_role: str | None = None
    recent_turns: Sequence[Mapping[str, object]] | None = None


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str


def _format_turn_history(turn_history: Sequence[Mapping[str, object]] | None) -> str:
    if not turn_history:
        return ""

    formatted_turns: list[str] = []
    recent_slice = list(turn_history)[-6:]
    for idx, turn in enumerate(recent_slice):
        if not isinstance(turn, Mapping):
            formatted_turns.append(f"  {idx + 1}. {turn}")
            continue
        role = str(turn.get("role", "desconocido")).capitalize()
        text = str(turn.get("text", "")).strip()
        metadata_bits: list[str] = []
        frequency = turn.get("frequency")
        if frequency:
            metadata_bits.append(f"freq={frequency}")
        intent = turn.get("intent")
        if intent:
            metadata_bits.append(f"intent={intent}")
        if turn.get("allow_response") is False:
            metadata_bits.append("allowResponse=false")
        feedback = turn.get("feedback")
        if feedback and role != "Student":
            metadata_bits.append(f"feedback={feedback}")
        metadata = f" ({', '.join(metadata_bits)})" if metadata_bits else ""
        formatted_turns.append(f"  {idx + 1}. {role}: {text}{metadata}")

    return "Turnos previos:\n" + "\n".join(formatted_turns) + "\n\n"


def build_prompt(
    *,
    intent: str,
    context: PromptContext,
    transcript: str,
    scenario: Mapping[str, object] | None,
    phase: Mapping[str, object] | None,
    turn_history: Sequence[Mapping[str, object]] | None,
) -> PromptBundle:
    """Compose system/user prompts for the selected intent."""

    system_prompt = PROMPT_TEMPLATES.get(
        context.frequency_group,
        PROMPT_TEMPLATES["tower"],
    )

    llm_guidance = {}
    if isinstance(phase, Mapping):
        llm_guidance = phase.get("llm") if isinstance(phase.get("llm"), Mapping) else {}

    controller_role = (
        context.controller_role
        or (llm_guidance.get("role") if isinstance(llm_guidance, Mapping) else None)
    )
    if controller_role:
        system_prompt = controller_role
    else:
        system_prompt += (
            " Debes evaluar transmisiones de entrenamiento ATC y proporcionar retroalimentación."
        )

    system_prompt += (
        " Responde únicamente en formato JSON válido con la estructura exacta:"
        " {\n"
        "  \"intent\": string,\n"
        "  \"allowResponse\": boolean,\n"
        "  \"controllerText\": string | null,\n"
        "  \"feedback\": string,\n"
        "  \"confidence\": number | null,\n"
        "  \"metadata\": object\n"
        " }.\n"
        "Si necesitas proponer un cambio de fase, incluye en metadata la clave \"nextPhase\"."
        " No escribas texto adicional antes o después del JSON."
    )

    scenario_json = json.dumps(scenario or {}, ensure_ascii=False, indent=2)
    phase_json = json.dumps(phase or {}, ensure_ascii=False, indent=2)

    turns_snippet = _format_turn_history(turn_history)

    llm_sections: list[str] = []
    if isinstance(llm_guidance, Mapping):
        expectations = llm_guidance.get("studentChecklist")
        if expectations:
            if isinstance(expectations, str):
                llm_sections.append(f"Checklist alumno:\n- {expectations}")
            elif isinstance(expectations, Sequence):
                items = "\n".join(f"- {item}" for item in expectations)
                llm_sections.append(f"Checklist alumno:\n{items}")
        controller_steps = llm_guidance.get("controllerChecklist")
        if controller_steps:
            if isinstance(controller_steps, str):
                llm_sections.append(f"Checklist controlador:\n- {controller_steps}")
            elif isinstance(controller_steps, Sequence):
                items = "\n".join(f"- {item}" for item in controller_steps)
                llm_sections.append(f"Checklist controlador:\n{items}")
        allow_rules = llm_guidance.get("allowResponseRules")
        if allow_rules:
            if isinstance(allow_rules, str):
                llm_sections.append(f"Cuándo responder:\n- {allow_rules}")
            elif isinstance(allow_rules, Sequence):
                items = "\n".join(f"- {item}" for item in allow_rules)
                llm_sections.append(f"Cuándo responder:\n{items}")
        feedback_guidance = llm_guidance.get("feedbackGuidance")
        if feedback_guidance:
            if isinstance(feedback_guidance, str):
                llm_sections.append(f"Guía de feedback:\n- {feedback_guidance}")
            elif isinstance(feedback_guidance, Sequence):
                items = "\n".join(f"- {item}" for item in feedback_guidance)
                llm_sections.append(f"Guía de feedback:\n{items}")
        additional_notes = llm_guidance.get("notes")
        if additional_notes:
            llm_sections.append(f"Notas adicionales: {additional_notes}")

    llm_guidance_text = "\n\n".join(llm_sections)
    phase_name = context.phase_name or (phase.get("name") if isinstance(phase, Mapping) else None)
    phase_header = f"Fase actual: {phase_name or context.phase_id or 'desconocida'}"

    user_prompt = (
        f"{phase_header}\n"
        f"Intent esperado: {intent}\n"
        f"Transcripción textual del alumno:\n{transcript.strip()}\n\n"
        f"Contexto operativo:\n"
        f"- Aeropuerto: {context.airport}\n"
        f"- Grupo de frecuencia: {context.frequency_group}\n"
        f"- Fase ID: {context.phase_id or 'desconocido'}\n\n"
        f"{llm_guidance_text}\n\n"
        f"Escenario (JSON):\n{scenario_json}\n\n"
        f"Fase (JSON):\n{phase_json}\n\n"
        f"{turns_snippet}"
        "Evalúa la transmisión del alumno usando la información anterior. Decide si el controlador debe "
        "responder (allowResponse=true) y redacta tanto la respuesta del controlador como la retroalimentación.\n"
        "Reglas:\n"
        "- Si falta información crítica u observas errores serios, establece allowResponse=false, "
        "  deja controllerText en null y explica la razón en feedback.\n"
        "- Cuando allowResponse sea true, escribe controllerText con fraseología ATC costarricense adecuada "
        "  para la frecuencia indicada.\n"
        "- Usa metadata para detallar elementos faltantes, próximos pasos o \"nextPhase\" si corresponde.\n"
        "- Respeta estrictamente el formato JSON solicitado; no incluyas texto fuera de la estructura."
    )

    return PromptBundle(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


__all__ = ["PromptContext", "PromptBundle", "build_prompt"]
