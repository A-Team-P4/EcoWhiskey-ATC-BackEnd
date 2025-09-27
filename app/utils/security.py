"""Security helpers for password management."""

from __future__ import annotations

import base64
import hashlib
import os

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
    return hashlib.compare_digest(candidate, stored)


__all__ = ["hash_password", "verify_password"]
