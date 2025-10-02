"""Telemetry middleware for request instrumentation."""

from __future__ import annotations

import time
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.telemetry import observe_request


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Collect request metrics for Prometheus."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start_time = time.perf_counter()
        method = request.method
        route = self._resolve_route(request)

        try:
            response = await call_next(request)
        except Exception:  # pragma: no cover - defensive
            duration_seconds = time.perf_counter() - start_time
            observe_request(method, route, 500, duration_seconds)
            raise

        duration_seconds = time.perf_counter() - start_time
        observe_request(method, route, response.status_code, duration_seconds)
        return response

    @staticmethod
    def _resolve_route(request: Request) -> str:
        """Return best-effort route pattern for metrics labels."""

        scope_route: Any = request.scope.get("route")
        if scope_route is not None:
            path = getattr(scope_route, "path", None)
            if path:
                return path

        return request.url.path
