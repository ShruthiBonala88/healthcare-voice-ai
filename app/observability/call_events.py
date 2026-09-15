"""
Call-event observability for Voxevia.

Call events are:
- logged locally
- persisted to Supabase

Examples:
    call_started
    call_connected
    speech_started
    speech_ended
    transcription_completed
    agent_response_generated
    tool_started
    tool_completed
    tool_failed
    human_handoff_requested
    call_completed
    call_failed
"""

from typing import Any

from app.data.call_repository import add_call_event
from app.observability.logging_config import get_logger


logger = get_logger("call_events")


ALLOWED_EVENT_TYPES = {
    "call_started",
    "call_connected",
    "speech_started",
    "speech_ended",
    "transcription_started",
    "transcription_completed",
    "agent_started",
    "agent_response_generated",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "human_handoff_requested",
    "call_completed",
    "call_failed",
}


async def log_call_event(
    call_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """
    Log and persist a call lifecycle event.

    Telemetry failures must never crash the active voice call.
    """

    if not call_id.strip():
        raise ValueError("call_id cannot be empty.")

    if not event_type.strip():
        raise ValueError("event_type cannot be empty.")

    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(
            f"Unsupported call event type: {event_type}"
        )

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
    except Exception as exc:
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
    Persist a call event without blocking the async event loop.
    """

    import asyncio

    await asyncio.to_thread(
        add_call_event,
        call_id,
        event_type,
        payload,
    )