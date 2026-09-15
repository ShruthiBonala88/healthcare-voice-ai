"""
Health check routes for Voxevia.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import get_settings


router = APIRouter(
    tags=["Health"],
)


@router.get("/health")
async def health():
    """
    Basic liveness check for load balancers and uptime monitors.
    """
    settings = get_settings()

    return {
        "status": "ok",
        "env": settings.app_env,
        "time": datetime.now(timezone.utc).isoformat(),
    }