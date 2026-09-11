"""
<<<<<<< HEAD
Call event tracking: writes structured events for each call to Supabase
(call_events table) and mirrors key milestones through the logger so they
show up in your log aggregator regardless of DB availability.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from app.data.supabase_client import get_supabase
from app.observability.logging_config import get_logger

=======
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


>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
logger = get_logger("call_events")


async def log_call_event(
<<<<<<< HEAD
    call_sid: str,
    event_type: str,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """
    Record a call lifecycle event, e.g.:
      call_started, call_answered, intent_detected, tool_called,
      tool_result, human_handoff, call_ended, error
    """
    payload = payload or {}
    logger.info("call_event", call_sid=call_sid, event_type=event_type, **payload)

    try:
        supabase = get_supabase()
        supabase.table("call_events").insert(
            {
                "call_sid": call_sid,
                "event_type": event_type,
                "payload": payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001 - never let telemetry break the call
        logger.warning("call_event_persist_failed", call_sid=call_sid, error=str(exc))
=======
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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
