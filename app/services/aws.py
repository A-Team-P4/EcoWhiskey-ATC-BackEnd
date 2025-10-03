"""Shared AWS helpers for service clients."""

from __future__ import annotations

from typing import Any

import boto3

from app.config.settings import settings


def create_boto3_client(service_name: str, *, region_name: str | None = None):
    """Instantiate a boto3 client using configured credentials if available."""

    region = region_name or settings.s3.region
    client_kwargs: dict[str, Any] = {"region_name": region}
    if settings.s3.access_key and settings.s3.secret_key:
        client_kwargs["aws_access_key_id"] = settings.s3.access_key
        client_kwargs["aws_secret_access_key"] = settings.s3.secret_key
    return boto3.client(service_name, **client_kwargs)


__all__ = ["create_boto3_client"]
