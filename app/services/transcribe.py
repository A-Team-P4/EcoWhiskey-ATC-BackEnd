"""Amazon Transcribe integration helpers."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4
from urllib.error import URLError
from urllib.request import urlopen

from botocore.exceptions import BotoCoreError, ClientError
from fastapi.concurrency import run_in_threadpool

from app.config.settings import settings
from app.services.aws import create_boto3_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranscriptionResult:
    """Structured transcription outcome returned to controllers."""

    transcript: str
    job_name: str
    media_uri: str
    transcript_uri: str
    object_key: str


class TranscriptionError(RuntimeError):
    """Raised when Amazon Transcribe fails to process audio successfully."""


_s3_client = create_boto3_client("s3", region_name=settings.s3.region)
_transcribe_client = create_boto3_client("transcribe", region_name=settings.s3.region)


class TranscribeService:
    """High-level facade for uploading audio and retrieving a transcript."""

    def __init__(
        self,
        bucket_name: str,
        *,
        language_code: str = "es-US",
        media_format: str = "mp3",
        media_sample_rate_hz: int | None = 24000,
        poll_interval: float = 2.0,
        timeout_seconds: float = 120.0,
        cleanup_objects: bool = True,
        job_name_prefix: str = "atc-transcribe-",
    ) -> None:
        if not bucket_name:
            raise ValueError("An S3 bucket name is required for transcription uploads.")
        self._bucket_name = bucket_name
        self._language_code = language_code
        self._media_format = media_format
        self._media_sample_rate_hz = media_sample_rate_hz
        self._poll_interval = poll_interval
        self._timeout_seconds = timeout_seconds
        self._cleanup_objects = cleanup_objects
        self._job_name_prefix = job_name_prefix

    async def transcribe_session_audio(
        self,
        session_id: UUID,
        audio_bytes: bytes,
        content_type: str,
    ) -> TranscriptionResult:
        """Upload audio for the session, run Transcribe, and return the transcript."""

        if not audio_bytes:
            raise TranscriptionError("The uploaded audio file is empty.")

        object_key = self._build_object_key(session_id)
        await self._upload_to_s3(audio_bytes, content_type, object_key)

        job_name = self._build_job_name(session_id)
        media_uri = f"s3://{self._bucket_name}/{object_key}"

        try:
            await self._start_job(job_name, media_uri)
            job_info = await self._wait_for_job(job_name)
            transcript_uri = job_info["TranscriptionJob"]["Transcript"][
                "TranscriptFileUri"
            ]
            transcript_text = await self._fetch_transcript(transcript_uri)
            return TranscriptionResult(
                transcript=transcript_text,
                job_name=job_name,
                media_uri=media_uri,
                transcript_uri=transcript_uri,
                object_key=object_key,
            )
        finally:
            if self._cleanup_objects:
                await self._delete_from_s3(object_key)

    def _build_object_key(self, session_id: UUID) -> str:
        return f"sessions/{session_id}/{uuid4().hex}.{self._media_format}"

    def _build_job_name(self, session_id: UUID) -> str:
        return f"{self._job_name_prefix}{session_id}-{uuid4().hex}"

    async def _upload_to_s3(
        self,
        audio_bytes: bytes,
        content_type: str,
        object_key: str,
    ) -> None:
        buffer = BytesIO(audio_bytes)
        extra_args = {"ContentType": content_type} if content_type else None
        try:
            await run_in_threadpool(
                _s3_client.upload_fileobj,
                buffer,
                self._bucket_name,
                object_key,
                **({"ExtraArgs": extra_args} if extra_args else {}),
            )
        except (BotoCoreError, ClientError) as exc:
            raise TranscriptionError("Failed to upload audio to S3.") from exc
        finally:
            buffer.close()

    async def _start_job(self, job_name: str, media_uri: str) -> None:
        kwargs: dict[str, Any] = {
            "TranscriptionJobName": job_name,
            "LanguageCode": self._language_code,
            "MediaFormat": self._media_format,
            "Media": {"MediaFileUri": media_uri},
        }
        if self._media_sample_rate_hz:
            kwargs["MediaSampleRateHertz"] = self._media_sample_rate_hz

        try:
            await run_in_threadpool(
                _transcribe_client.start_transcription_job,
                **kwargs,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Amazon Transcribe failed to start job '%s'", job_name)
            raise TranscriptionError(
                f"Failed to start the transcription job: {exc}"
            ) from exc

    async def _wait_for_job(self, job_name: str) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout_seconds

        while True:
            try:
                response = await run_in_threadpool(
                    _transcribe_client.get_transcription_job,
                    TranscriptionJobName=job_name,
                )
            except (BotoCoreError, ClientError) as exc:
                raise TranscriptionError(
                    "Failed to fetch transcription job status."
                ) from exc

            job = response.get("TranscriptionJob", {})
            status = job.get("TranscriptionJobStatus")
            if status == "COMPLETED":
                return response
            if status == "FAILED":
                reason = job.get(
                    "FailureReason",
                    "Transcription job failed without a reason.",
                )
                raise TranscriptionError(f"Transcription job failed: {reason}")

            if loop.time() >= deadline:
                raise TranscriptionError(
                    "Transcription job timed out before completion."
                )

            await asyncio.sleep(self._poll_interval)

    async def _fetch_transcript(self, transcript_uri: str) -> str:
        def _download() -> str:
            with urlopen(transcript_uri) as response:
                payload = response.read()
            data = json.loads(payload.decode("utf-8"))
            transcripts = data.get("results", {}).get("transcripts", [])
            if not transcripts:
                raise ValueError("Transcript payload did not include transcripts.")
            transcript_text = transcripts[0].get("transcript")
            if not transcript_text:
                raise ValueError("Transcript payload was empty.")
            return transcript_text

        try:
            return await run_in_threadpool(_download)
        except (URLError, ValueError, json.JSONDecodeError) as exc:
            raise TranscriptionError("Failed to download transcript text.") from exc

    async def _delete_from_s3(self, object_key: str) -> None:
        try:
            await run_in_threadpool(
                _s3_client.delete_object,
                Bucket=self._bucket_name,
                Key=object_key,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.warning(
                "Failed to delete temporary audio object '%s': %s",
                object_key,
                exc,
            )


def get_transcribe_service() -> TranscribeService:
    """Return a lazily-instantiated transcribe service singleton."""

    return _DEFAULT_SERVICE


_DEFAULT_SERVICE = TranscribeService(bucket_name=settings.s3.bucket_name)
