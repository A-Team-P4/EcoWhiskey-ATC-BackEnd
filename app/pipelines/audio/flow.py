"""High-level orchestration map for the audio analysis pipeline.

The HTTP controller in ``app/controllers/audio.py`` still contains the
asynchronous choreography that ties everything together, but this module
documents the canonical execution order so team members can navigate the
codebase more easily:

1. ``ingestion`` – validate the upload and obtain raw audio bytes.
2. ``transcription`` – call Amazon Transcribe (or the configured ASR) to obtain text.
3. ``context`` – load the session scenario, turns, and frequency guards.
4. ``validation`` – ensure the tuned frequency matches the expected intent.
5. ``prompts`` – construct the system/user prompts for the LLM.
6. ``llm`` – invoke the conversational model and validate the contract.
7. ``persistence`` – append the new turn to the repository.
8. ``synthesis`` – generate readback audio with the Radio TTS service.

Only stages 3, 5, and 6 live in this package today; the remaining helpers
stay close to the FastAPI layer because they are HTTP/transport aware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class PipelineStage:
    """Human-readable description of one stage in the audio pipeline."""

    order: int
    name: str
    module: str
    summary: str


class AudioAnalysisPipeline:
    """Utility wrapper for documenting the `/audio/analyze` flow."""

    _STAGES: List[PipelineStage] = [
        PipelineStage(
            1,
            "Ingestion",
            "app.controllers.audio",
            "Resolve content type, read the upload into memory, store the transcript request.",
        ),
        PipelineStage(
            2,
            "Transcription",
            "app.controllers.audio",
            "Forward the audio bytes to the configured ASR provider (Amazon Transcribe).",
        ),
        PipelineStage(
            3,
            "Session Context",
            "app.pipelines.audio.context",
            "Merge stored session data with scenario JSON to determine the active phase.",
        ),
        PipelineStage(
            4,
            "Frequency Guardrails",
            "app.controllers.audio",
            "Compare tuned frequency against the expected bucket for the active phase.",
        ),
        PipelineStage(
            5,
            "Prompt Assembly",
            "app.pipelines.audio.prompts",
            "Render system/user prompts tailored to the controller role and scenario.",
        ),
        PipelineStage(
            6,
            "LLM Invocation",
            "app.pipelines.audio.llm",
            "Call Bedrock and validate the structured JSON response.",
        ),
        PipelineStage(
            7,
            "Turn Persistence",
            "app.controllers.audio",
            "Append student/controller turns and phase transitions to the repository.",
        ),
        PipelineStage(
            8,
            "Readback Synthesis",
            "app.controllers.audio",
            "Synthesize Polly/Radio TTS audio and upload it to storage (S3).",
        ),
    ]

    @classmethod
    def describe(cls) -> Iterable[PipelineStage]:
        """Expose the ordered list of stages for debugging and documentation."""

        return tuple(cls._STAGES)


__all__ = ["AudioAnalysisPipeline", "PipelineStage"]
