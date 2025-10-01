"""Structured logging middleware for FastAPI requests."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger("app.middleware.structured")

COLOR_RESET = "\u001b[0m"
COLOR_GREEN = "\u001b[32m"
COLOR_CYAN = "\u001b[36m"
COLOR_YELLOW = "\u001b[33m"
COLOR_RED = "\u001b[31m"


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Emit structured JSON logs for each HTTP request."""

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

        user_info = self._extract_user(request)
        if user_info is not None:
            log_payload["user"] = user_info

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
        await self._persist_log(log_payload)
        return response

    @staticmethod
    def _elapsed_ms(start_time: float) -> float:
        """Return elapsed milliseconds rounded to two decimals."""

        return round((time.perf_counter() - start_time) * 1000, 2)

    async def _persist_log(self, payload: dict[str, Any]) -> None:
        """Persist the request log entry without blocking the response."""

        try:
            from app.database import SessionFactory
            from app.models.log import RequestLog
        except Exception:  # pragma: no cover - defensive
            logger.exception("Failed to import logging dependencies")
            return

        timestamp_value = datetime.fromisoformat(payload["timestamp"])
        if timestamp_value.tzinfo is not None:
            timestamp_value = (
                timestamp_value.astimezone(timezone.utc).replace(tzinfo=None)
            )

        async with SessionFactory() as session:
            log_entry = RequestLog(
                timestamp=timestamp_value,
                method=payload.get("method"),
                url=payload.get("url"),
                status_code=payload.get("status_code", 0),
                client_ip=payload.get("client_ip"),
                duration_ms=self._safe_duration(payload.get("duration_ms")),
                user=payload.get("user"),
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
    def _extract_user(request: Request) -> dict[str, Any] | None:
        """Return a JSON-serialisable representation of the authenticated user."""

        user_obj: Any | None = None

        if "user" in request.scope:
            user_obj = request.scope.get("user")

        if user_obj is None and hasattr(request.state, "user"):
            try:
                user_obj = request.state.user  # type: ignore[attr-defined]
            except AttributeError:
                user_obj = None

        if user_obj is None:
            auth_header = request.headers.get("authorization")
            if auth_header:
                scheme, _, token = auth_header.partition(" ")
                if scheme.lower() == "bearer" and token:
                    try:
                        from app.utils import decode_access_token

                        token_payload = decode_access_token(token)
                        token_user = getattr(token_payload, "user", None)
                        if token_user:
                            if hasattr(token_user, "model_dump"):
                                user_obj = token_user.model_dump()
                            else:
                                user_obj = token_user
                        elif getattr(token_payload, "sub", None):
                            user_obj = {"id": token_payload.sub}
                    except Exception:  # pragma: no cover - defensive
                        logger.debug(
                            "Failed to decode access token for logging",
                            exc_info=True,
                        )

        if user_obj is None:
            return None

        if isinstance(user_obj, dict):
            return user_obj

        user_payload: dict[str, Any] = {}
        for attr, key in (
            ("id", "id"),
            ("email", "email"),
            ("username", "username"),
            ("name", "name"),
            ("account_type", "accountType"),
            ("accountType", "accountType"),
            ("school", "school"),
        ):
            value = getattr(user_obj, attr, None)
            if value is not None:
                user_payload[key] = value

        if not user_payload and hasattr(user_obj, "dict"):
            try:
                user_payload = user_obj.dict()  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive
                user_payload = {}

        return user_payload or {"repr": repr(user_obj)}

    @staticmethod
    def _format_console_message(payload: dict[str, Any]) -> str:
        """Return JSON log payload wrapped with ANSI color codes."""

        status = payload.get("status_code") or 0
        if 200 <= status < 300:
            color = COLOR_GREEN
        elif 400 <= status < 500:
            color = COLOR_YELLOW
        elif status >= 500:
            color = COLOR_RED
        else:
            color = COLOR_CYAN

        json_payload = StructuredLoggingMiddleware._to_json(payload)
        return f"{color}{json_payload}{COLOR_RESET}"

    @staticmethod
    def _to_json(payload: dict[str, Any]) -> str:
        """Serialize payload as compact JSON."""

        return json.dumps(payload, default=str, separators=(",", ":"))
