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


async def upload_session_asset(
    session_id: UUID,
    data: bytes,
    *,
    kind: str,
    extension: str,
    content_type: str,
) -> str:
    """Upload a raw asset to S3 under the session prefix."""

    if not data:
        return ""

    bucket = settings.s3.bucket_name
    if not bucket:
        return ""

    object_key = f"sessions/{session_id}/{kind}-{uuid4().hex}.{extension.lstrip('.')}"
    try:
        await run_in_threadpool(
            _s3_client.put_object,
            Bucket=bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as exc:
        # Log but don't fail the request if storage fails
        # (or maybe we should? The user wants to keep files)
        # For now, let's re-raise as StorageError so the caller decides
        raise StorageError(f"Failed to upload session asset: {exc}") from exc

    return _object_url(bucket, object_key)


__all__ = ["upload_readback_audio", "upload_session_asset", "StorageError"]
