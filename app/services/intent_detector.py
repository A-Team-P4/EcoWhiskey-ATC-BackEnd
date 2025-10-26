"""Pattern-based intent detection for ATC transcripts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class IntentDefinition:
    """Static definition loaded from intent resources."""

    id: str
    frequency_group: str | None
    require_all: Sequence[re.Pattern[str]]
    require_any: Sequence[re.Pattern[str]]
    boost_keywords: Sequence[str]


@dataclass(frozen=True)
class DetectedIntent:
    """Outcome returned by the detector."""

    id: str
    frequency_group: str | None
    confidence: float
    matched_tokens: Sequence[str]


class IntentDetector:
    """Load intent definitions from JSON resources and score transcripts."""

    def __init__(self, intents: Sequence[IntentDefinition]) -> None:
        self._intents = intents

    @classmethod
    def from_directory(cls, root: Path) -> "IntentDetector":
        """Instantiate the detector from all JSON files in ``root``."""

        intents: list[IntentDefinition] = []
        if not root.exists():
            return cls(intents)

        for intent_path in sorted(root.glob("*.json")):
            data = _load_json(intent_path)
            if not data:
                continue
            intent = IntentDefinition(
                id=data.get("id", intent_path.stem),
                frequency_group=data.get("frequency_group"),
                require_all=_compile_patterns(data.get("phrases", {}).get("require_all", [])),
                require_any=_compile_patterns(data.get("phrases", {}).get("require_any", [])),
                boost_keywords=_normalise_keywords(data.get("boost_keywords", [])),
            )
            intents.append(intent)

        return cls(intents)

    def detect(self, transcript: str) -> DetectedIntent | None:
        """Return the most probable intent for the provided transcript."""

        if not transcript:
            return None

        transcript_norm = transcript.lower()
        best_result: DetectedIntent | None = None

        for definition in self._intents:
            if not _matches_all(definition.require_all, transcript_norm):
                continue

            optional_hits = _collect_matches(definition.require_any, transcript_norm)
            if definition.require_any and not optional_hits:
                continue

            keyword_hits = [
                keyword for keyword in definition.boost_keywords if keyword in transcript_norm
            ]

            total_hits = optional_hits + keyword_hits
            base_confidence = 0.6  # satisfied require_all clauses
            confidence = min(1.0, base_confidence + 0.1 * len(total_hits))

            if best_result is None or confidence > best_result.confidence:
                best_result = DetectedIntent(
                    id=definition.id,
                    frequency_group=definition.frequency_group,
                    confidence=confidence,
                    matched_tokens=total_hits,
                )

        return best_result

    @property
    def definitions(self) -> Sequence[IntentDefinition]:
        """Return the configured intent definitions."""

        return tuple(self._intents)


def _load_json(path: Path) -> Mapping[str, object]:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def _compile_patterns(patterns: Iterable[str]) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for raw in patterns:
        if not raw:
            continue
        compiled.append(re.compile(raw, re.IGNORECASE))
    return compiled


def _normalise_keywords(keywords: Iterable[str]) -> list[str]:
    return [keyword.lower() for keyword in keywords if keyword]


def _matches_all(patterns: Sequence[re.Pattern[str]], text: str) -> bool:
    return all(pattern.search(text) for pattern in patterns)


def _collect_matches(patterns: Sequence[re.Pattern[str]], text: str) -> list[str]:
    matches: list[str] = []
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            matches.append(match.group(0))
    return matches


__all__ = ["IntentDetector", "DetectedIntent", "IntentDefinition"]
