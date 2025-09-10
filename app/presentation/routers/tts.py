from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config.settings import settings
from app.presentation.dtos import TtsRequest

router = APIRouter(prefix="/tts", tags=["tts"])

polly_client = boto3.client("polly", region_name=settings.s3.region)


@router.post("/", response_class=Response)
async def text_to_speech(request: TtsRequest) -> Response:
    """Convert input text to MP3 audio using Amazon Polly."""
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
            raise HTTPException(status_code=500, detail="Polly returned no audio stream")
        audio_bytes = audio_stream.read()
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    return Response(content=audio_bytes, media_type="audio/mpeg")
