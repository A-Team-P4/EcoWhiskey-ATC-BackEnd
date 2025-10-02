"""Audio analysis endpoints."""

from typing import Final
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.controllers.dependencies import CurrentUserDep

router = APIRouter(prefix="/audio", tags=["audio"])

_ALLOWED_CONTENT_TYPES: Final[set[str]] = {"audio/mpeg", "audio/mp3"}
_HARD_CODED_AUDIO_URL: Final[str] = "https://ecowhiskey-atc-audio.s3.us-east-2.amazonaws.com/out.mp3"


@router.post("/analyze")
async def analyze_audio(
    #_current_user: CurrentUserDep,
    session_id: UUID = Form(...),
    audio_file: UploadFile = File(...),
) -> dict[str, str]:
    """Receive an MP3 audio file and return a placeholder S3 URL."""

    if audio_file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only MP3 audio files are supported",
        )

    # Consume the uploaded file to avoid leaving temporary resources open.
    await audio_file.read()
    await audio_file.close()

    return {
        "session_id": str(session_id),
        "audio_url": _HARD_CODED_AUDIO_URL,
    }
