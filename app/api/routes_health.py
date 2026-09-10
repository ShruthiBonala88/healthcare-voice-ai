from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health():
    """
    Basic liveness check for load balancers / uptime monitors.
    Returns 200 as long as the app process is up and settings loaded ok.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "env": settings.app_env,
        "time": datetime.now(timezone.utc).isoformat(),
    }