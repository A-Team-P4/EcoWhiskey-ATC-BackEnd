"""Request ingestion helpers (Stage 01 of the audio pipeline)."""

from __future__ import annotations

import mimetypes
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Final

from fastapi import HTTPException, UploadFile, status

_ALLOWED_CONTENT_TYPES: Final[set[str]] = {
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
}


def resolve_content_type(audio_file: UploadFile) -> str:
    """Accept MP3/M4A uploads regardless of whether the client set a content-type."""

    content_type = audio_file.content_type
    if not content_type and audio_file.filename:
        guessed_type, _ = mimetypes.guess_type(audio_file.filename)
        content_type = guessed_type

    content_type = content_type or "audio/mpeg"

    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only MP3 or M4A audio files are supported",
        )
    return content_type


async def read_audio_bytes(audio_file: UploadFile) -> bytes:
    """Load the upload fully into memory, rejecting empty payloads."""

    audio_bytes = await audio_file.read()
    await audio_file.close()

    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty",
        )
    return audio_bytes


def normalize_frequency(value: str | None) -> str | None:
    """Normalize frequency strings (e.g., 118.3 -> 118.300) for robust comparisons."""

    if value is None:
        return None

    cleaned = str(value).strip()
    if not cleaned:
        return None

    cleaned = cleaned.replace(",", ".")
    try:
        as_decimal = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return cleaned.lower()

    normalized = as_decimal.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return format(normalized, "f")


__all__ = ["resolve_content_type", "read_audio_bytes", "normalize_frequency"]
