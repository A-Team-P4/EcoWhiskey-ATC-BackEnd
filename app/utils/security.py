"""Security helpers for password management and JWT handling."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from app.config.settings import settings
from app.models.user import User

_SALT_BYTES = 16
_ITERATIONS = 120_000
_TEMP_PASSWORD_MIN_LENGTH = 8
_TEMP_PASSWORD_CHARSET = string.ascii_letters + string.digits


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


def generate_temporary_password(length: int = 12) -> str:
    """Create a temporary password complying with basic complexity rules."""

    if length < _TEMP_PASSWORD_MIN_LENGTH:
        raise ValueError("Temporary password must be at least 8 characters long.")

    while True:
        candidate = "".join(
            secrets.choice(_TEMP_PASSWORD_CHARSET) for _ in range(length)
        )
        if (
            any(c.islower() for c in candidate)
            and any(c.isupper() for c in candidate)
            and any(c.isdigit() for c in candidate)
        ):
            return candidate


class AuthenticationError(Exception):
    """Raised when a JWT cannot be decoded or is otherwise invalid."""


class TokenPayload(BaseModel):
    """Minimal payload structure embedded in JWT access tokens."""

    sub: str
    exp: datetime
    user: dict[str, Any] | None = None
    iat: datetime | None = None


def create_access_token(
    subject: str,
    user: User | None = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT access token for the provided subject."""

    now = datetime.now(timezone.utc)
    expires_delta = expires_delta or timedelta(
        minutes=settings.security.access_token_expires_minutes
    )
    expire_at = now + expires_delta
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire_at, "iat": now}

    if user is not None:
        full_name = f"{user.first_name} {user.last_name}".strip()
        to_encode["user"] = {
            "id": user.id,
            "name": full_name,
        }

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
    "generate_temporary_password",
    "create_access_token",
    "decode_access_token",
    "AuthenticationError",
]
