"""Call lifecycle telemetry that never breaks the live call."""

import asyncio
from typing import Any

from app.data.call_repository import add_call_event
from app.observability.logging_config import get_logger

logger = get_logger("call_events")


async def log_call_event(
    call_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    payload = payload or {}
    logger.info("call_event", call_id=call_id, event_type=event_type, **payload)
    try:
        await asyncio.to_thread(add_call_event, call_id, event_type, payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "call_event_persist_failed",
            call_id=call_id,
            event_type=event_type,
            error=str(exc),
        )
