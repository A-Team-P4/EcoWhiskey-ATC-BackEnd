"""Application entry point and FastAPI app factory."""

from __future__ import annotations

import logging
import sys

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .config.settings import settings
from .controllers import audio, auth, schools, test, tts, users, training_context
from .database import dispose_engine, init_models
from .middleware import StructuredLoggingMiddleware, TelemetryMiddleware


def _configure_logging() -> None:
    """Ensure structured middleware logs stream to stdout."""

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))

    middleware_logger = logging.getLogger("app.middleware.structured")
    middleware_logger.setLevel(logging.INFO)
    middleware_logger.handlers.clear()
    middleware_logger.addHandler(handler)
    middleware_logger.propagate = False


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    _configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        description="EcoWhiskey Air Traffic Control Backend API",
    )

    app.add_middleware(TelemetryMiddleware)
    app.add_middleware(StructuredLoggingMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(schools.router)
    app.include_router(tts.router)
    app.include_router(audio.router)
    app.include_router(test.router)
    app.include_router(training_context.router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        """Root endpoint."""

        return {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "status": "operational",
        }

    @app.get("/health", include_in_schema=False)
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""

        return {
            "status": "healthy",
            "service": settings.app_name,
            "version": settings.app_version,
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        """Expose application metrics for Prometheus scraping."""

        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    @app.on_event("startup")
    async def startup_event() -> None:
        await init_models()

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        await dispose_engine()

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
