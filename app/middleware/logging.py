"""Structured logging middleware for FastAPI requests."""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar, Optional

import hashlib
from cryptography.fernet import Fernet
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config.settings import settings

logger = logging.getLogger("app.middleware.structured")

COLOR_RESET = "\u001b[0m"
COLOR_GREEN = "\u001b[32m"
COLOR_CYAN = "\u001b[36m"
COLOR_YELLOW = "\u001b[33m"
COLOR_RED = "\u001b[31m"


@dataclass(slots=True)
class SessionContext:
    """Aggregated session metadata for request logging."""

    identifier: str
    user_id: int | str
    started_at: datetime
    expires_at: Optional[datetime]
    fingerprint: str


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Emit structured JSON logs for each HTTP request."""

    _cipher: ClassVar[Optional[Fernet]] = None

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start_time = time.perf_counter()
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else None,
        }

        session_context = self._build_session_context(request, log_payload["timestamp"])
        if session_context is not None:
            log_payload["session"] = {
                "id": session_context.identifier,
                "user_id": session_context.user_id,
            }

        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover - defensive
            log_payload["status_code"] = 500
            log_payload["duration_ms"] = self._elapsed_ms(start_time)
            log_payload["error"] = repr(exc)
            logger.exception(self._format_console_message(log_payload))
            raise

        log_payload["status_code"] = response.status_code
        log_payload["duration_ms"] = self._elapsed_ms(start_time)
        logger.info(self._format_console_message(log_payload))
        await self._persist_log(log_payload, session_context)
        return response

    @staticmethod
    def _elapsed_ms(start_time: float) -> float:
        """Return elapsed milliseconds rounded to two decimals."""

        return round((time.perf_counter() - start_time) * 1000, 2)

    async def _persist_log(
        self,
        payload: dict[str, Any],
        session_context: SessionContext | None,
    ) -> None:
        """Persist the request log entry without blocking the response."""

        if not settings.persist_request_logs:
            return

        status_code = payload.get("status_code")
        if status_code == 307:
            logger.debug(
                "Skipping persistence for redirect response",
                extra={"status_code": status_code, "url": payload.get("url")},
            )
            return

        try:
            from app.database import session_scope
            from app.models.log import RequestLog
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to import logging dependencies")
            return

        timestamp_value = datetime.fromisoformat(payload["timestamp"])
        if timestamp_value.tzinfo is not None:
            timestamp_value = timestamp_value.astimezone(timezone.utc).replace(
                tzinfo=None
            )

        session_identifier: Optional[str] = None
        session_user_id: Optional[str] = None
        session_started_at: Optional[datetime] = None
        session_expires_at: Optional[datetime] = None
        session_fingerprint: Optional[str] = None

        if session_context is not None:
            session_identifier = session_context.identifier
            session_user_id = str(session_context.user_id)
            session_started_at = self._normalize_timestamp(session_context.started_at)
            session_expires_at = self._normalize_timestamp(session_context.expires_at)
            session_fingerprint = session_context.fingerprint

        async with session_scope() as session:
            log_entry = RequestLog(
                timestamp=timestamp_value,
                method=payload.get("method"),
                url=payload.get("url"),
                status_code=payload.get("status_code", 0),
                client_ip=payload.get("client_ip"),
                duration_ms=self._safe_duration(payload.get("duration_ms")),
                session_id=session_identifier,
                session_user_id=session_user_id,
                session_started_at=session_started_at,
                session_expires_at=session_expires_at,
                session_fingerprint=session_fingerprint,
            )

            session.add(log_entry)
            try:
                await session.commit()
            except Exception:  # pragma: no cover - defensive
                await session.rollback()
                logger.exception("Failed to persist request log entry")

    @staticmethod
    def _safe_duration(value: Any) -> int | None:
        """Convert a duration payload value into an integer safely."""

        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            logger.debug("Invalid duration in log payload", extra={"value": value})
            return None

    @staticmethod
    def _normalize_timestamp(value: Optional[datetime]) -> datetime | None:
        """Return a naive UTC datetime for persistence."""

        if value is None:
            return None

        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)

        return value

    def _build_session_context(
        self,
        request: Request,
        request_timestamp: str,
    ) -> SessionContext | None:
        """Construct an encrypted session descriptor for the current request."""

        user_obj: Any | None = None

        if "user" in request.scope:
            user_obj = request.scope.get("user")

        if user_obj is None and hasattr(request.state, "user"):
            try:
                user_obj = request.state.user  # type: ignore[attr-defined]
            except AttributeError:
                user_obj = None

        resolved_id = self._resolve_user_id(user_obj)
        token_payload: Any | None = None
        token = self._extract_bearer_token(request)

        if token:
            try:
                from app.utils import decode_access_token

                token_payload = decode_access_token(token)
            except Exception:  # pragma: no cover - defensive
                logger.debug(
                    "Failed to decode access token when constructing session context",
                    exc_info=True,
                )
                token_payload = None

        expires_at: Optional[datetime] = None
        if token_payload is not None:
            token_user = getattr(token_payload, "user", None)
            token_user_id = self._resolve_user_id(token_user)

            if resolved_id is None:
                resolved_id = token_user_id or getattr(token_payload, "sub", None)

            raw_expires = getattr(token_payload, "exp", None)
            if isinstance(raw_expires, datetime):
                expires_at = raw_expires.astimezone(timezone.utc)

        if resolved_id is None:
            return None

        started_at: Optional[datetime] = None
        if token_payload is not None:
            raw_started = getattr(token_payload, "iat", None)
            if isinstance(raw_started, datetime):
                started_at = raw_started.astimezone(timezone.utc)

        if started_at is None:
            started_at = datetime.fromisoformat(request_timestamp)
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            else:
                started_at = started_at.astimezone(timezone.utc)

        identifier_source = f"{resolved_id}:{int(started_at.timestamp())}"
        session_fingerprint = hashlib.sha256(identifier_source.encode("utf-8")).hexdigest()

        client_ip = request.client.host if request.client else None
        user_agent_raw = request.headers.get("user-agent")
        user_agent = user_agent_raw[:256] if isinstance(user_agent_raw, str) else None

        encrypted_payload = {
            "session": session_fingerprint,
            "user_id": str(resolved_id),
            "started_at": started_at.isoformat(),
        }
        if expires_at is not None:
            encrypted_payload["expires_at"] = expires_at.isoformat()
        if client_ip:
            encrypted_payload["client_ip"] = client_ip
        if user_agent:
            encrypted_payload["user_agent"] = user_agent

        try:
            session_identifier = self._encrypt_session_metadata(encrypted_payload)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to encrypt session metadata for logging")
            return None

        return SessionContext(
            identifier=session_identifier,
            user_id=resolved_id,
            started_at=started_at,
            expires_at=expires_at,
            fingerprint=session_fingerprint,
        )

    @classmethod
    def _encrypt_session_metadata(cls, metadata: dict[str, Any]) -> str:
        """Encrypt session metadata into an opaque token."""

        cipher = cls._get_cipher()
        payload_bytes = json.dumps(metadata, default=str, separators=(',', ':')).encode(
            "utf-8"
        )
        return cipher.encrypt(payload_bytes).decode("utf-8")

    @classmethod
    def _get_cipher(cls) -> Fernet:
        """Return a cached Fernet cipher initialised from the JWT secret."""

        if cls._cipher is None:
            secret_bytes = (
                settings.security.jwt_secret_key.get_secret_value().encode("utf-8")
            )
            digest = hashlib.sha256(secret_bytes).digest()
            key = base64.urlsafe_b64encode(digest)
            cls._cipher = Fernet(key)
        return cls._cipher

    @staticmethod
    def _extract_bearer_token(request: Request) -> Optional[str]:
        """Return the bearer token from the request headers when present."""

        auth_header = request.headers.get("authorization")
        if not auth_header:
            return None

        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None

        return token

    @staticmethod
    def _resolve_user_id(source: Any) -> int | str | None:
        """Extract the best effort user identifier from various representations."""

        if source is None:
            return None

        if isinstance(source, dict):
            for key in ("id", "user_id", "userId"):
                value = source.get(key)
                if value is not None:
                    return value
            return None

        for attr in ("id", "user_id", "userId"):
            if hasattr(source, attr):
                value = getattr(source, attr)
                if value is not None:
                    return value

        if hasattr(source, "model_dump"):
            try:
                data = source.model_dump()
            except Exception:  # pragma: no cover - defensive
                data = None
            if isinstance(data, dict):
                return StructuredLoggingMiddleware._resolve_user_id(data)

        if hasattr(source, "dict"):
            try:
                data = source.dict()
            except Exception:  # pragma: no cover - defensive
                data = None
            if isinstance(data, dict):
                return StructuredLoggingMiddleware._resolve_user_id(data)

        return None

    @staticmethod
    def _format_console_message(payload: dict[str, Any]) -> str:
        """Return minimal request metadata wrapped with ANSI color codes."""

        status = payload.get("status_code") or 0
        if 200 <= status < 300:
            color = COLOR_GREEN
        elif 400 <= status < 500:
            color = COLOR_YELLOW
        elif status >= 500:
            color = COLOR_RED
        else:
            color = COLOR_CYAN

        user_id = None
        session_info = payload.get("session")
        if isinstance(session_info, dict):
            user_id = session_info.get("user_id")

        fields = [
            ("timestamp", payload.get("timestamp")),
            ("method", payload.get("method")),
            ("url", payload.get("url")),
            ("client_ip", payload.get("client_ip")),
            ("user_id", user_id),
        ]
        message = ", ".join(
            f"{name}={value if value is not None else '-'}" for name, value in fields
        )

        return f"{color}{message}{COLOR_RESET}"

    @staticmethod
    def _to_json(payload: dict[str, Any]) -> str:
        """Serialize payload as compact JSON."""

        return json.dumps(payload, default=str, separators=(',', ':'))
