"""Application entry point and FastAPI app factory."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .config.settings import settings
from .controllers import audio, auth, test, tts, users, training_context
from .database import dispose_engine, init_models
from .middleware import StructuredLoggingMiddleware, TelemetryMiddleware


def _configure_logging() -> None:
    """Ensure structured middleware logs stream to stdout and file."""

    logging.getLogger().handlers.clear()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )

    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    middleware_logger = logging.getLogger("app.middleware.structured")
    middleware_logger.handlers.clear()
    middleware_stdout = logging.StreamHandler(sys.stdout)
    middleware_stdout.setFormatter(logging.Formatter("%(message)s"))
    middleware_logger.addHandler(middleware_stdout)
    middleware_logger.setLevel(logging.INFO)
    middleware_logger.propagate = False

    pipeline_log_path = Path(settings.audio_log_file)
    pipeline_log_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline_handler = RotatingFileHandler(
        pipeline_log_path,
        maxBytes=500_000,
        backupCount=5,
        encoding="utf-8",
    )
    pipeline_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    pipeline_logger = logging.getLogger("app.services.audio_pipeline")
    pipeline_logger.handlers.clear()
    pipeline_logger.addHandler(pipeline_handler)
    pipeline_logger.setLevel(logging.INFO)

    transcript_log_path = Path(getattr(settings, "transcript_log_file", "logs/transcripts.log"))
    transcript_log_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_handler = RotatingFileHandler(
        transcript_log_path,
        maxBytes=500_000,
        backupCount=5,
        encoding="utf-8",
    )
    transcript_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    transcript_logger = logging.getLogger("app.logs.transcript")
    transcript_logger.handlers.clear()
    transcript_logger.addHandler(transcript_handler)
    transcript_logger.setLevel(logging.INFO)

    noisy_loggers = [
        "botocore",
        "boto3",
        "urllib3",
        "sqlalchemy.engine",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)


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
