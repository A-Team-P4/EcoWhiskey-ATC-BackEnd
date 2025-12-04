"""Thin Bedrock client wrapper for conversational LLM invocations."""

from __future__ import annotations

import base64
import logging
from typing import Optional

from fastapi.concurrency import run_in_threadpool

from app.config.settings import settings
from app.services.aws import create_boto3_client

logger = logging.getLogger(__name__)


class LlmInvocationError(RuntimeError):
    """Raised when the Bedrock invocation fails."""


def _decode_bedrock_api_key(secret_value: Optional[str]) -> tuple[str, str] | None:
    """Decode the BEDROCK_API_KEY secret into access/secret key components."""

    if not secret_value:
        return None

    try:
        decoded_bytes = base64.b64decode(secret_value.strip())
    except Exception:  # pragma: no cover - defensive
        decoded_bytes = secret_value.encode("utf-8", "ignore")

    filtered = "".join(chr(b) for b in decoded_bytes if 31 < b < 127)
    if ":" not in filtered:
        return None
    access_key, secret_key = filtered.split(":", 1)
    return access_key, secret_key


class BedrockLlmClient:
    """Invoke Amazon Bedrock models with standard configuration."""

    def __init__(self) -> None:
        self._model_id = settings.bedrock.model_id

        api_key_tuple = None
        if settings.bedrock.api_key:
            api_key_tuple = _decode_bedrock_api_key(
                settings.bedrock.api_key.get_secret_value()
            )

        try:
            self._client = create_boto3_client(
                "bedrock-runtime",
                region_name=settings.bedrock.region,
                aws_access_key_id=api_key_tuple[0] if api_key_tuple else None,
                aws_secret_access_key=api_key_tuple[1] if api_key_tuple else None,
            )
        except Exception as exc:  # pragma: no cover - configuration issue
            logger.warning("No se pudo inicializar Bedrock: %s", exc)
            self._client = None

    async def invoke(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        model_id: str | None = None,
    ) -> str | None:
        """Run a Bedrock `converse` call and return the aggregate text output."""

        target_model_id = model_id or self._model_id
        if not self._client or not target_model_id:
            return None

        inference_cfg = {
            "maxTokens": max_tokens or settings.bedrock.max_tokens,
            "temperature": (
                temperature
                if temperature is not None
                else settings.bedrock.temperature
            ),
            "topP": top_p if top_p is not None else settings.bedrock.top_p,
        }

        def _call() -> str:
            response = self._client.converse(
                modelId=target_model_id,
                system=[{"text": system_prompt}],
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                inferenceConfig=inference_cfg,
            )
            content_blocks = (
                response.get("output", {})
                .get("message", {})
                .get("content", [])
            )
            texts = [block.get("text", "") for block in content_blocks if block.get("text")]
            return "\n".join(texts).strip()

        try:
            result = await run_in_threadpool(_call)
        except Exception as exc:  # pragma: no cover - external dependency
            raise LlmInvocationError(str(exc)) from exc

        return result or None


__all__ = ["BedrockLlmClient", "LlmInvocationError"]
