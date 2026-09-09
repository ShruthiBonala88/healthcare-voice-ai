"""
FastAPI application entrypoint for Healthcare Voice AI.

Run locally:
    uvicorn app.main:app --reload --port 8000

Then expose it publicly, for example:
    ngrok http 8000

Twilio Voice webhook:
    https://<your-public-host>/calls/incoming
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_calls import router as calls_router
from app.api.routes_health import router as health_router
from app.observability.logging_config import (
    configure_logging,
    get_logger,
)


# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

configure_logging()
logger = get_logger("main")


# ---------------------------------------------------------
# Application Lifecycle
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle.
    """

    # -------------------------
    # Startup
    # -------------------------
    logger.info("app_startup")

    yield

    # -------------------------
    # Shutdown
    # -------------------------
    logger.info("app_shutdown")


# ---------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------

app = FastAPI(
    title="Healthcare Voice AI",
    description=(
        "Inbound Healthcare Voice AI system for handling "
        "patient phone calls, appointments, hospital information, "
        "and human handoff."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------
# Root Endpoint
# ---------------------------------------------------------

@app.get("/")
async def root():
    """
    Basic service information.
    """

    return {
        "status": "ok",
        "service": "Healthcare Voice AI",
        "version": "0.1.0",
        "mode": "inbound",
    }


# ---------------------------------------------------------
# Routers
# ---------------------------------------------------------

app.include_router(
    health_router,
)

app.include_router(
    calls_router,
)


# ---------------------------------------------------------
# Application Info
# ---------------------------------------------------------

@app.get("/info")
async def info():
    """
    Basic API information.
    """

    return {
        "service": "Healthcare Voice AI",
        "version": "0.1.0",
        "mode": "inbound",
        "features": [
            "Inbound voice calls",
            "Appointment booking",
            "Appointment cancellation",
            "Appointment rescheduling",
            "Doctor information",
            "Department information",
            "Hospital information",
            "Human handoff",
        ],
    }