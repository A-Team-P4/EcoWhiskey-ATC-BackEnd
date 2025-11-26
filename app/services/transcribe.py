"""Amazon Transcribe integration helpers using Streaming API."""

from __future__ import annotations

import os
import asyncio
import logging
import subprocess
from dataclasses import dataclass
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
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
            # Chunk size: 4KB (approx 23ms at 44.1kHz 16-bit mono)
            # 44100 Hz * 2 bytes/sample = 88200 bytes/sec
            # 8192 bytes / 88200 bytes/sec ~= 0.092 seconds (92ms)
            chunk_size = 8192
            bytes_per_sec = self._media_sample_rate_hz * 2  # 16-bit = 2 bytes
            sleep_time = chunk_size / bytes_per_sec
            
            logger.info(f"Starting stream. Total bytes: {len(pcm_data)}. Chunk size: {chunk_size}. Sleep: {sleep_time:.4f}s")
            
            total_sent = 0
            for i in range(0, len(pcm_data), chunk_size):
                chunk = pcm_data[i : i + chunk_size]
                await stream.input_stream.send_audio_event(audio_chunk=chunk)
                total_sent += len(chunk)
                # Sleep to simulate real-time streaming
                await asyncio.sleep(sleep_time)
                
                if i % (chunk_size * 50) == 0: # Log every ~50 chunks
                     logger.debug(f"Streamed {total_sent}/{len(pcm_data)} bytes")

            logger.info("Finished streaming audio bytes. Ending stream.")
            await stream.input_stream.end_stream()

        try:
            await asyncio.gather(write_chunks(), handler.handle_events())
        except Exception as exc:
            logger.error(f"Streaming loop failed: {exc}")
            raise TranscriptionError(f"Streaming transcription failed: {exc}") from exc

        logger.info(f"Transcription complete. Length: {len(handler.transcript)}")
        return TranscriptionResult(transcript=handler.transcript.strip())

    async def _convert_to_pcm(self, audio_bytes: bytes) -> bytes:
        """Convert input audio to raw PCM s16le via ffmpeg using a thread."""
        return await run_in_threadpool(self._convert_to_pcm_sync, audio_bytes)

    def _convert_to_pcm_sync(self, audio_bytes: bytes) -> bytes:
        """Synchronous ffmpeg conversion using a temporary file to support seeking."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name

        try:
            process = subprocess.run(
                [
                    "ffmpeg",
                    "-y", # Overwrite output if exists (though we use pipe)
                    "-i", tmp_path,
                    "-f", "s16le",
                    "-ac", "1",
                    "-ar", str(self._media_sample_rate_hz),
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            if not process.stdout:
                logger.warning("ffmpeg produced empty output. stderr: %s", process.stderr.decode("utf-8", errors="replace"))
            return process.stdout
        except subprocess.CalledProcessError as exc:
            error_msg = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "No stderr"
            logger.error("ffmpeg failed. stderr: %s", error_msg)
            raise TranscriptionError(f"ffmpeg failed to convert audio to PCM: {error_msg}") from exc
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

class _SimpleTranscriptHandler(TranscriptResultStreamHandler):
    def __init__(self, transcript_result_stream):
        super().__init__(transcript_result_stream)
        self.transcript = ""

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            if not result.is_partial:
                for alt in result.alternatives:
                    logger.debug(f"Received transcript chunk: {alt.transcript[:20]}...")
                    self.transcript += alt.transcript + " "


def get_transcribe_service() -> TranscribeService:
    """Return a lazily-instantiated transcribe service singleton."""
    return _DEFAULT_SERVICE


_DEFAULT_SERVICE = TranscribeService(region=settings.s3.region)
