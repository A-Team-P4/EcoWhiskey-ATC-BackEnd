"""Amazon Transcribe integration helpers using Streaming API."""

from __future__ import annotations

import os
import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

from app.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranscriptionResult:
    """Structured transcription outcome returned to controllers."""

    transcript: str
    language_code: str | None = None


class TranscriptionError(RuntimeError):
    """Raised when Amazon Transcribe fails to process audio successfully."""


class TranscribeService:
    """High-level facade for streaming audio to Amazon Transcribe."""

    def __init__(
        self,
        region: str,
        language_code: str = "es-US",
        media_sample_rate_hz: int = 44100,
        media_encoding: str = "pcm",
    ) -> None:
        self._region = region
        self._language_code = language_code
        self._media_sample_rate_hz = media_sample_rate_hz
        self._media_encoding = media_encoding
        
        # Ensure credentials are available to the SDK
        if settings.s3.access_key:
            os.environ["AWS_ACCESS_KEY_ID"] = settings.s3.access_key
        if settings.s3.secret_key:
            os.environ["AWS_SECRET_ACCESS_KEY"] = settings.s3.secret_key
            
        self._client = TranscribeStreamingClient(region=region)

    async def transcribe_session_audio(
        self,
        session_id: UUID,
        audio_bytes: bytes,
        content_type: str,
    ) -> TranscriptionResult:
        """Stream audio to Transcribe and return the full transcript."""

        if not audio_bytes:
            raise TranscriptionError("The uploaded audio file is empty.")

        # Convert to PCM via ffmpeg
        try:
            pcm_data = await self._convert_to_pcm(audio_bytes)
        except Exception as exc:
            raise TranscriptionError(f"Audio conversion failed: {exc}") from exc

        stream = await self._client.start_stream_transcription(
            language_code=self._language_code,
            media_sample_rate_hz=self._media_sample_rate_hz,
            media_encoding=self._media_encoding,
        )

        handler = _SimpleTranscriptHandler(stream.output_stream)

        async def write_chunks():
            # Chunk size: 4KB (approx 23ms at 44.1kHz 16-bit mono, or 46ms at 22kHz)
            # Transcribe recommends bigger chunks, e.g. 100ms.
            # 100ms at 44100Hz 16-bit (2 bytes) = 44100 * 2 * 0.1 = 8820 bytes.
            chunk_size = 8192
            for i in range(0, len(pcm_data), chunk_size):
                chunk = pcm_data[i : i + chunk_size]
                await stream.input_stream.send_audio_event(audio_chunk=chunk)
            await stream.input_stream.end_stream()

        try:
            await asyncio.gather(write_chunks(), handler.handle_events())
        except Exception as exc:
            raise TranscriptionError(f"Streaming transcription failed: {exc}") from exc

        return TranscriptionResult(transcript=handler.transcript.strip())

    async def _convert_to_pcm(self, audio_bytes: bytes) -> bytes:
        """Convert input audio to raw PCM s16le via ffmpeg."""
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i", "pipe:0",
            "-f", "s16le",
            "-ac", "1",
            "-ar", str(self._media_sample_rate_hz),
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await process.communicate(input=audio_bytes)
        if process.returncode != 0:
            raise TranscriptionError("ffmpeg failed to convert audio to PCM.")
        return stdout


class _SimpleTranscriptHandler(TranscriptResultStreamHandler):
    def __init__(self, transcript_result_stream):
        super().__init__(transcript_result_stream)
        self.transcript = ""

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            if not result.is_partial:
                for alt in result.alternatives:
                    self.transcript += alt.transcript + " "


def get_transcribe_service() -> TranscribeService:
    """Return a lazily-instantiated transcribe service singleton."""
    return _DEFAULT_SERVICE


_DEFAULT_SERVICE = TranscribeService(region=settings.s3.region)
