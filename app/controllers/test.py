"""Diagnostic endpoints."""

from fastapi import APIRouter

from app.config.settings import settings


router = APIRouter(prefix="/test", tags=["test"])


@router.get("/health")
async def test_health_check() -> dict[str, str]:
    """Return service health metadata for diagnostics."""

    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }
