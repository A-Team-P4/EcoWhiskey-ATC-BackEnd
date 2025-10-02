"""Prometheus metrics definitions and helpers."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests processed",
    ("method", "route", "status"),
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "route"),
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)

LOGIN_COUNTER = Counter(
    "app_logins_total",
    "Number of successful user login events",
)

ERROR_COUNTER = Counter(
    "app_internal_errors_total",
    "Number of requests ending in internal server error responses",
    ("method", "route"),
)


def observe_request(
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """Record metrics for a completed HTTP request."""

    safe_route = route or "unknown"
    safe_method = method or "UNKNOWN"
    status_label = str(status_code)
    observed_duration = duration_seconds if duration_seconds >= 0 else 0

    REQUEST_COUNT.labels(
        method=safe_method,
        route=safe_route,
        status=status_label,
    ).inc()
    REQUEST_LATENCY.labels(
        method=safe_method,
        route=safe_route,
    ).observe(observed_duration)

    if status_code >= 500:
        ERROR_COUNTER.labels(
            method=safe_method,
            route=safe_route,
        ).inc()


def increment_login() -> None:
    """Increment the successful login counter."""

    LOGIN_COUNTER.inc()
