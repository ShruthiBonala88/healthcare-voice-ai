<<<<<<< HEAD
<<<<<<< Updated upstream
from fastapi import APIRouter

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
async def health_check():
    return {
        "status": "healthy"
=======
=======
"""
Health check routes for Voxevia.
"""

>>>>>>> 6928a2c (Complete backend security validation and tests)
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
<<<<<<< HEAD
>>>>>>> Stashed changes
=======
>>>>>>> 6928a2c (Complete backend security validation and tests)
    }