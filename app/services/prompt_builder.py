"""Helpers to construct system/user prompts for the audio pipeline LLM.

Given a scenario phase, recent turns, and the student transcript, we emit:
* A system prompt describing the controller persona and strict JSON contract.
* A user prompt containing operational context, guardrails, and turn snippets.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping, Sequence

# Default personas for each tower/ground/etc. controller group.
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
    difficulty: int = 2


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str


def _format_turn_history(turn_history: Sequence[Mapping[str, object]] | None) -> str:
    """Flatten a handful of prior turns so the LLM can see short-term context."""
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
        # Pack lightweight hints so the LLM can reason about frequency/intent history.
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


import re

def _substitute_dynamic_values(text: str, data: Mapping[str, object]) -> str:
    """Replace [data.key] placeholders with values from the data dictionary."""
    if not text or not isinstance(text, str):
        return text
    
    def replacer(match):
        key = match.group(1)
        # Allow nested keys if needed, though currently we mostly use flat data
        val = data.get(key)
        if val is not None:
            return str(val)
        return match.group(0)  # Keep original if key not found

    return re.sub(r"\[data\.([\w_]+)\]", replacer, text)


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

    # Base system prompt depends on the active frequency (tower/ground/etc.).
    system_prompt = PROMPT_TEMPLATES.get(
        context.frequency_group,
        PROMPT_TEMPLATES["tower"],
    )

    llm_guidance = {}
    phase_data = {}
    if isinstance(phase, Mapping):
        llm_guidance = phase.get("llm") if isinstance(phase.get("llm"), Mapping) else {}
        phase_data = phase.get("data") if isinstance(phase.get("data"), Mapping) else {}

    # Controller overrides embedded in the scenario take precedence over defaults.
    controller_role = (
        context.controller_role
        or (llm_guidance.get("role") if isinstance(llm_guidance, Mapping) else None)
    )
    if controller_role:
        # Apply dynamic substitution to the role
        controller_role = _substitute_dynamic_values(controller_role, phase_data)
        system_prompt = controller_role
    else:
        system_prompt += (
            " Debes evaluar transmisiones de entrenamiento ATC y proporcionar retroalimentación."
        )

    # Inject difficulty-based instructions
    difficulty = context.difficulty if hasattr(context, "difficulty") else 5
    if difficulty <= 3:
        system_prompt += (
            " Modo relajado: Sé flexible con la fraseología. Acepta variaciones informales siempre que la intención sea clara y segura. "
            "No penalices errores menores."
        )
    elif difficulty <= 7:
        system_prompt += (
            " Modo normal: Balancea la precisión con la fluidez. Penaliza errores de seguridad o información crítica, "
            "pero permite ligeras variaciones."
        )
    else:
        system_prompt += (
            " Modo estricto: Exige fraseología estándar perfecta. Penaliza cualquier desviación o error menor."
        )

    system_prompt += (
        " Responde únicamente en formato JSON válido con la estructura exacta:"
        " {\n"
        "  \"intent\": string,\n"
        "  \"allowResponse\": boolean,\n"
        "  \"controllerText\": string | null,\n"
        "  \"feedback\": string,\n"
        "  \"confidence\": number | null,\n"
        "  \"score\": number | null,\n"
        "  \"metadata\": object\n"
        " }.\n"
        "El campo \"score\" debe ser un número de 0 a 100 que evalúe la calidad de la transmisión del alumno "
        "para la fase actual, considerando: fraseología correcta, información completa, orden lógico, "
        "y uso apropiado de la frecuencia. Un score de 100 es perfecto, 0 es completamente incorrecto.\n"
        "Si necesitas proponer un cambio de fase, incluye en metadata la clave \"nextPhase\"."
        " No escribas texto adicional antes o después del JSON."
    )

    scenario_json = json.dumps(scenario or {}, ensure_ascii=False, indent=2)
    phase_json = json.dumps(phase or {}, ensure_ascii=False, indent=2)

    turns_snippet = _format_turn_history(turn_history)

    llm_sections: list[str] = []
    if isinstance(llm_guidance, Mapping):
        # Copy over checklists and heuristics authored in scenario JSON for extra guidance.
        expectations = llm_guidance.get("studentChecklist")
        if expectations:
            if isinstance(expectations, str):
                text = _substitute_dynamic_values(expectations, phase_data)
                llm_sections.append(f"Checklist alumno:\n- {text}")
            elif isinstance(expectations, Sequence):
                items = "\n".join(f"- {_substitute_dynamic_values(str(item), phase_data)}" for item in expectations)
                llm_sections.append(f"Checklist alumno:\n{items}")
        controller_steps = llm_guidance.get("controllerChecklist")
        if controller_steps:
            if isinstance(controller_steps, str):
                text = _substitute_dynamic_values(controller_steps, phase_data)
                llm_sections.append(f"Checklist controlador:\n- {text}")
            elif isinstance(controller_steps, Sequence):
                items = "\n".join(f"- {_substitute_dynamic_values(str(item), phase_data)}" for item in controller_steps)
                llm_sections.append(f"Checklist controlador:\n{items}")
        allow_rules = llm_guidance.get("allowResponseRules")
        if allow_rules:
            if isinstance(allow_rules, str):
                text = _substitute_dynamic_values(allow_rules, phase_data)
                llm_sections.append(f"Cuándo responder:\n- {text}")
            elif isinstance(allow_rules, Sequence):
                items = "\n".join(f"- {_substitute_dynamic_values(str(item), phase_data)}" for item in allow_rules)
                llm_sections.append(f"Cuándo responder:\n{items}")
        feedback_guidance = llm_guidance.get("feedbackGuidance")
        if feedback_guidance:
            if isinstance(feedback_guidance, str):
                text = _substitute_dynamic_values(feedback_guidance, phase_data)
                llm_sections.append(f"Guía de feedback:\n- {text}")
            elif isinstance(feedback_guidance, Sequence):
                items = "\n".join(f"- {_substitute_dynamic_values(str(item), phase_data)}" for item in feedback_guidance)
                llm_sections.append(f"Guía de feedback:\n{items}")
        additional_notes = llm_guidance.get("notes")
        if additional_notes:
            text = _substitute_dynamic_values(additional_notes, phase_data)
            llm_sections.append(f"Notas adicionales: {text}")

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
