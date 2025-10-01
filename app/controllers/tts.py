"""Text-to-speech controller backed by Amazon Polly."""

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.config.settings import settings
from app.views import TextToSpeechRequest

router = APIRouter(prefix="/tts", tags=["tts"])

polly_client = boto3.client("polly", region_name=settings.s3.region)


@router.post("/", response_class=Response)
async def text_to_speech(request: TextToSpeechRequest) -> Response:
    """Convert text to speech using Amazon Polly and return MP3 bytes."""

    try:
        voice_id = request.voice_id or "Mia"
        result = polly_client.synthesize_speech(
            Text=request.text,
            VoiceId=voice_id,
            OutputFormat="mp3",
            Engine="neural",
        )
        audio_stream = result.get("AudioStream")
        if audio_stream is None:
            raise HTTPException(
                status_code=500, detail="Polly returned no audio stream"
            )
        audio_bytes = audio_stream.read()
    except (BotoCoreError, ClientError) as exc:  # pragma: no cover - network call
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(content=audio_bytes, media_type="audio/mpeg")
