"""
Call event tracking.

Writes structured lifecycle events for each call to Supabase
and mirrors them through the logger.

The database call_events table is linked to the calls table
using the internal call UUID.
"""

from datetime import datetime, timezone
from typing import Any

from app.data.call_repository import add_call_event
from app.observability.logging_config import get_logger


logger = get_logger("call_events")


async def log_call_event(
    call_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """
    Record a call lifecycle event.

    Examples:
        call_started
        call_answered
        intent_detected
        tool_called
        tool_result
        human_handoff
        call_ended
        error
    """

    payload = payload or {}

    logger.info(
        "call_event",
        call_id=call_id,
        event_type=event_type,
        **payload,
    )

    try:
        await _persist_call_event(
            call_id=call_id,
            event_type=event_type,
            payload=payload,
        )

    except Exception as exc:  # noqa: BLE001
        # Telemetry must never break the live phone call.
        logger.warning(
            "call_event_persist_failed",
            call_id=call_id,
            event_type=event_type,
            error=str(exc),
        )


async def _persist_call_event(
    call_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """
    Persist an event using the call repository.

    Supabase writes are synchronous, so run them in a worker thread
    to avoid blocking the async voice pipeline.
    """

    import asyncio

    await asyncio.to_thread(
        add_call_event,
        call_id,
        event_type,
        payload,
    )