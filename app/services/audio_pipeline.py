"""Backward-compatible access to the audio analysis pipeline helpers.

The implementation now lives in ``app.pipelines.audio`` which organises the
codebase by pipeline stage. This module simply re-exports the public surface
to avoid breaking imports in legacy code while we complete the migration.
"""

from __future__ import annotations

import logging

from app.pipelines.audio import (
    LlmOutcome,
    LlmRequest,
    build_llm_request,
    call_conversation_llm,
    fetch_session_context,
)

logger = logging.getLogger("app.services.audio_pipeline")

__all__ = [
    "LlmOutcome",
    "LlmRequest",
    "fetch_session_context",
    "build_llm_request",
    "call_conversation_llm",
]
