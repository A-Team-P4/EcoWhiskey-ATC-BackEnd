"""Template loading and rendering for controller responses."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)


class TemplateRenderError(RuntimeError):
    """Raised when a template cannot be rendered with the provided slots."""


@dataclass(frozen=True)
class TemplateDefinition:
    template_id: str
    data: Mapping[str, Any]

    @property
    def required_slots(self) -> tuple[str, ...]:
        slots = self.data.get("slots", {})
        return tuple(slots.get("required", []))

    @property
    def optional_slots(self) -> tuple[str, ...]:
        slots = self.data.get("slots", {})
        return tuple(slots.get("optional", []))

    @property
    def frequency_group(self) -> str | None:
        return self.data.get("frequency_group")

    @property
    def defaults(self) -> Mapping[str, Any]:
        return self.data.get("fallback", {}).get("defaults", {})


@dataclass(frozen=True)
class RenderedPhrase:
    text: str
    template_id: str
    slots: Mapping[str, Any]
    metadata: Mapping[str, Any]


class TemplateRenderer:
    """Load and render response templates for controller messages."""

    def __init__(self, root: Path) -> None:
        self._templates: dict[str, TemplateDefinition] = {}

        for template_path in root.rglob("*.json"):
            try:
                with template_path.open("r", encoding="utf-8") as tpl_file:
                    data = json.load(tpl_file)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Plantilla inválida %s: %s", template_path, exc)
                continue
            template_id = data.get("id") or template_path.stem
            self._templates[template_id] = TemplateDefinition(
                template_id=template_id,
                data=data,
            )

    def get(self, template_id: str) -> TemplateDefinition | None:
        return self._templates.get(template_id)

    def render(
        self,
        template_id: str,
        *,
        slots: Mapping[str, Any],
    ) -> RenderedPhrase:
        template = self._templates.get(template_id)
        if not template:
            raise TemplateRenderError(f"Template '{template_id}' no encontrado.")

        normalized_slots: dict[str, Any] = dict(template.defaults)
        normalized_slots.update(slots)

        missing = [
            slot
            for slot in template.required_slots
            if normalized_slots.get(slot) in (None, "", [])
        ]
        if missing:
            raise TemplateRenderError(
                f"Faltan slots obligatorios para '{template_id}': {missing}"
            )

        render_payload = dict(normalized_slots)

        render_data = template.data.get("render", {})

        instruction_map: Mapping[str, str] = render_data.get("instruction_map", {})
        instruction_code = render_payload.get(
            "instruction_code",
            render_data.get("default_instruction_code"),
        )
        instruction_text = None
        if instruction_code and instruction_map:
            template_text = instruction_map.get(instruction_code)
            if template_text:
                try:
                    instruction_text = template_text.format(**render_payload)
                except KeyError as exc:
                    raise TemplateRenderError(
                        f"Slot faltante en instruction_map '{instruction_code}': {exc}"
                    ) from exc
        if instruction_text:
            render_payload.setdefault("instruction_text", instruction_text)

        phrase_template = render_data.get("spanish")
        if not phrase_template:
            raise TemplateRenderError(
                f"No existe render 'spanish' en la plantilla '{template_id}'."
            )

        try:
            text = phrase_template.format(**render_payload)
        except KeyError as exc:
            raise TemplateRenderError(
                f"Slot faltante en plantilla '{template_id}': {exc}"
            ) from exc

        metadata = template.data.get("metadata", {})

        return RenderedPhrase(
            text=text,
            template_id=template_id,
            slots=render_payload,
            metadata=metadata,
        )


__all__ = ["TemplateRenderer", "TemplateRenderError", "RenderedPhrase"]
