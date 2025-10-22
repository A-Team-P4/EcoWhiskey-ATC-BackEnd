"""Helpers to construct system/user prompts for the audio pipeline LLM."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Sequence

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
    runway_conditions: str | None = None
    weather_snippet: str | None = None
    recent_turns: Sequence[str] | None = None


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str
    expected_slots: Sequence[str]


def build_prompt(
    *,
    intent: str,
    context: PromptContext,
    transcript: str,
    required_slots: Sequence[str],
    optional_slots: Sequence[str],
    template_example: dict[str, str] | None = None,
) -> PromptBundle:
    """Compose system/user prompts for the selected intent."""

    system_prompt = PROMPT_TEMPLATES.get(
        context.frequency_group,
        PROMPT_TEMPLATES["tower"],
    )
    system_prompt += (
        " Responde únicamente en formato JSON válido, sin comentarios ni texto adicional."
    )

    slots_lines = "\n".join(f"- {slot}" for slot in required_slots)
    optional_lines = "\n".join(f"- {slot}" for slot in optional_slots) or "Ninguno."

    turns_snippet = ""
    if context.recent_turns:
        formatted_turns: list[str] = []
        recent_slice = context.recent_turns[-4:]
        for idx, turn in enumerate(recent_slice):
            if isinstance(turn, dict):
                role = turn.get("role", "desconocido").capitalize()
                text = turn.get("text", "").strip()
                metadata_bits = []
                frequency = turn.get("frequency")
                if frequency:
                    metadata_bits.append(f"freq={frequency}")
                intent = turn.get("intent")
                if intent:
                    metadata_bits.append(f"intent={intent}")
                if turn.get("used_fallback"):
                    metadata_bits.append("fallback=true")
                metadata = f" ({', '.join(metadata_bits)})" if metadata_bits else ""
                line = f"{role}: {text}{metadata}"
            else:
                line = str(turn)
            formatted_turns.append(f"  {idx + 1}. {line}")
        turns_snippet = "Turnos previos:\n" + "\n".join(formatted_turns) + "\n\n"

    example_json = template_example or {
        "intent": intent,
        "confidence": 0.8,
        "slots": {slot: f"<{slot}>" for slot in required_slots},
        "notes": {"observations": []},
    }
    example_json_str = json.dumps(example_json, ensure_ascii=False, indent=2)

    user_prompt = (
        f"Transcripción textual del alumno:\n{transcript.strip()}\n\n"
        f"Contexto operativo:\n"
        f"- Aeropuerto: {context.airport}\n"
        f"- Grupo de frecuencia: {context.frequency_group}\n"
        f"- Condiciones de pista: {context.runway_conditions or 'no informado'}\n"
        f"- Clima relevante: {context.weather_snippet or 'no informado'}\n\n"
        f"{turns_snippet}"
        f"Debes extraer la intención y los slots solicitados.\n"
        f"Slots obligatorios:\n{slots_lines or 'Ninguno'}\n"
        f"Slots opcionales:\n{optional_lines}\n\n"
        "Responde SOLO con JSON válido exactamente con esta forma:\n"
        f"{example_json_str}\n"
        "No incluyas texto adicional ni escapes innecesarios."
    )

    return PromptBundle(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        expected_slots=required_slots,
    )


__all__ = ["PromptContext", "PromptBundle", "build_prompt"]
