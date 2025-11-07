"""Audio analysis pipeline package.

Modules are organised by the order in which `/audio/analyze` executes:

1. `context` – fetch + normalize session state shared with the LLM.
2. `prompts` – assemble the Bedrock system/user prompts.
3. `llm` – call the conversational model and validate its response.
4. `flow` – human-readable description of the end-to-end stages.

The FastAPI controller imports from here so contributors can jump straight
to the relevant stage without wading through a single monolithic file.
"""

from .context import fetch_session_context
from .flow import AudioAnalysisPipeline, PipelineStage
from .ingestion import normalize_frequency, read_audio_bytes, resolve_content_type
from .intent import classify_intent
from .llm import call_conversation_llm
from .persistence import context_base
from .prompts import build_llm_request
from .synthesis import synthesize_controller_audio
from .transcription import transcribe_audio
from .types import LlmOutcome, LlmRequest

__all__ = [
    "AudioAnalysisPipeline",
    "PipelineStage",
    "LlmOutcome",
    "LlmRequest",
    "context_base",
    "fetch_session_context",
    "build_llm_request",
    "call_conversation_llm",
    "classify_intent",
    "normalize_frequency",
    "read_audio_bytes",
    "resolve_content_type",
    "synthesize_controller_audio",
    "transcribe_audio",
]
