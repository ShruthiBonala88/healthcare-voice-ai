"""
Call event tracking: writes structured events for each call to Supabase
(call_events table) and mirrors key milestones through the logger so they
show up in your log aggregator regardless of DB availability.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from app.data.supabase_client import get_supabase
from app.observability.logging_config import get_logger

logger = get_logger("call_events")


async def log_call_event(
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
