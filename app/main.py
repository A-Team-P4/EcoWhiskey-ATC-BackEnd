import logging
import sys
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .middleware import StructuredLoggingMiddleware

from .config.settings import settings
from .controllers import auth, hello, test, tts, users
from .database import init_models


def _configure_logging():
    """
    Ensure 'app.middleware.structured' logs go to stdout.
    Your middleware already emits compact JSON strings,
    so we keep a plain '%(message)s' formatter.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))

    lg = logging.getLogger("app.middleware.structured")
    lg.setLevel(logging.INFO)
    lg.handlers.clear()
    lg.addHandler(handler)
    lg.propagate = False  # evita duplicados si el root también tiene handlers

def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    _configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        description="EcoWhiskey Air Traffic Control Backend API",
    )

    app.add_middleware(StructuredLoggingMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Include routers
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(tts.router)
    app.include_router(test.router)


    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "status": "operational",
        }

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "service": settings.app_name,
            "version": settings.app_version,
        }

    # Global exception handler
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )

    @app.on_event("startup")
    async def startup_event():
        """Ensure required database tables exist"""
        await init_models()

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host=settings.host, port=settings.port, reload=settings.debug
    )