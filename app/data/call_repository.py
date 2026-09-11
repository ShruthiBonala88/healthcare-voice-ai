"""
Database repository for calls, conversations,
messages, and call events.
"""

from datetime import datetime, timezone
from typing import Any

from app.data.supabase_client import get_supabase


def create_conversation(
    phone_number: str,
    channel: str = "voice",
) -> dict[str, Any]:
    """Create a conversation when a call begins."""

    supabase = get_supabase()

    response = (
        supabase
        .table("conversations")
        .insert(
            {
                "phone_number": phone_number,
                "channel": channel,
                "status": "active",
            }
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Failed to create conversation."
        )

    return response.data[0]


def create_call(
    conversation_id: str,
    provider_call_id: str,
    from_number: str,
    to_number: str,
) -> dict[str, Any]:
    """Create a call record linked to a conversation."""

    supabase = get_supabase()

    response = (
        supabase
        .table("calls")
        .insert(
            {
                "conversation_id": conversation_id,
                "provider": "twilio",
                "provider_call_id": provider_call_id,
                "from_number": from_number,
                "to_number": to_number,
                "direction": "inbound",
                "status": "initiated",
            }
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Failed to create call."
        )

    return response.data[0]


def add_message(
    conversation_id: str,
    role: str,
    content: str,
) -> dict[str, Any]:
    """Store one conversation message."""

    allowed_roles = {
        "user",
        "assistant",
        "system",
        "tool",
    }

    if role not in allowed_roles:
        raise ValueError(
            f"Invalid message role: {role}"
        )

    if not content.strip():
        raise ValueError(
            "Message content cannot be empty."
        )

    supabase = get_supabase()

    response = (
        supabase
        .table("messages")
        .insert(
            {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
            }
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Failed to create message."
        )

    return response.data[0]


def add_call_event(
    call_id: str,
    event_type: str,
    event_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Store an event related to a call."""

    if not event_type.strip():
        raise ValueError(
            "Event type cannot be empty."
        )

    supabase = get_supabase()

    response = (
        supabase
        .table("call_events")
        .insert(
            {
                "call_id": call_id,
                "event_type": event_type,
                "event_data": event_data or {},
            }
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Failed to create call event."
        )

    return response.data[0]


def finish_call(
    call_id: str,
    conversation_id: str,
    duration_seconds: int | None = None,
) -> None:
    """Mark the call and conversation as completed."""

    supabase = get_supabase()

    now = datetime.now(timezone.utc).isoformat()

    (
        supabase
        .table("calls")
        .update(
            {
                "status": "completed",
                "duration_seconds": duration_seconds,
                "ended_at": now,
            }
        )
        .eq("id", call_id)
        .execute()
    )

    (
        supabase
        .table("conversations")
        .update(
            {
                "status": "completed",
                "ended_at": now,
            }
        )
        .eq("id", conversation_id)
        .execute()
    )