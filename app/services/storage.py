"""S3 storage helpers for session assets."""

from __future__ import annotations

from typing import Tuple
from uuid import UUID, uuid4

from botocore.exceptions import BotoCoreError, ClientError
from fastapi.concurrency import run_in_threadpool

from app.config.settings import settings
from app.services.aws import create_boto3_client


class StorageError(RuntimeError):
    """Raised when S3 asset persistence fails."""


_s3_client = create_boto3_client("s3", region_name=settings.s3.region)


def _object_url(bucket: str, key: str) -> str:
    region = settings.s3.region
    if region == "us-east-1":
        return f"https://{bucket}.s3.amazonaws.com/{key}"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


async def upload_readback_audio(
    session_id: UUID,
    audio_bytes: bytes,
    *,
    content_type: str = "audio/wav",
    extension: str = "wav",
) -> Tuple[str, str]:
    """Upload processed audio to S3 and return (object_key, public_url)."""

    if not audio_bytes:
        raise StorageError("Audio payload for upload was empty.")
    bucket = settings.s3.bucket_name
    if not bucket:
        raise StorageError("S3 bucket name is not configured.")

    object_key = f"sessions/{session_id}/readback-{uuid4().hex}.{extension.lstrip('.')}"
    try:
        await run_in_threadpool(
            _s3_client.put_object,
            Bucket=bucket,
            Key=object_key,
            Body=audio_bytes,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(f"Failed to upload readback audio: {exc}") from exc

    return object_key, _object_url(bucket, object_key)


__all__ = ["upload_readback_audio", "StorageError"]
