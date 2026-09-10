"""
FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000

Then expose it publicly (e.g. `ngrok http 8000`) and point your Twilio
phone number's Voice webhook at:
    https://<your-public-host>/calls/incoming
"""
from fastapi import FastAPI

from app.api.routes_calls import router as calls_router
from app.api.routes_health import router as health_router
from app.observability.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger("main")

app = FastAPI(title="Healthcare Voice AI", version="0.1.0")

app.include_router(health_router)
app.include_router(calls_router)


@app.on_event("startup")
async def on_startup():
    logger.info("app_startup")
