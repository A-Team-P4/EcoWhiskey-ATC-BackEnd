"""Security helpers for password management and JWT handling."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from app.config.settings import settings

_SALT_BYTES = 16
_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash for the supplied password."""

    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _ITERATIONS,
    )
    return base64.b64encode(salt + derived).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Check whether the provided password matches the stored hash."""

    try:
        decoded = base64.b64decode(hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False

    salt = decoded[:_SALT_BYTES]
    stored = decoded[_SALT_BYTES:]
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _ITERATIONS,
    )
    return hmac.compare_digest(candidate, stored)


class AuthenticationError(Exception):
    """Raised when a JWT cannot be decoded or is otherwise invalid."""


class TokenPayload(BaseModel):
    """Minimal payload structure embedded in JWT access tokens."""

    sub: str
    exp: datetime


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token for the provided subject."""

    expires_delta = expires_delta or timedelta(
        minutes=settings.security.access_token_expires_minutes
    )
    expire_at = datetime.now(timezone.utc) + expires_delta
    to_encode = {"sub": subject, "exp": expire_at}
    secret = settings.security.jwt_secret_key.get_secret_value()
    return jwt.encode(
        to_encode,
        secret,
        algorithm=settings.security.jwt_algorithm,
    )


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token, returning its payload."""

    secret = settings.security.jwt_secret_key.get_secret_value()
    try:
        payload = jwt.decode(
            token, secret, algorithms=[settings.security.jwt_algorithm]
        )
        return TokenPayload.model_validate(payload)
    except (JWTError, ValidationError) as exc:  # pragma: no cover - defensive branch
        raise AuthenticationError("Invalid authentication token") from exc


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "AuthenticationError",
]
