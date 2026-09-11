"""
Session management for Voxevia.

This module manages short-lived voice-call session state
using Redis.

Redis is used only for temporary state.

Permanent information such as:
- patients
- appointments
- doctors
- transcripts
- call records

must remain in Supabase/PostgreSQL.
"""

from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.data.redis_client import (
    delete_session,
    get_session,
    set_session,
)


def create_session(
    session_id: str,
    call_id: str | None = None,
    conversation_id: str | None = None,
    provider_call_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a new temporary voice-call session.

    Only minimal temporary information should be stored.
    """

    settings = get_settings()

    now = datetime.now(timezone.utc).isoformat()

    session_data: dict[str, Any] = {
        "session_id": session_id,
        "call_id": call_id,
        "conversation_id": conversation_id,
        "provider_call_id": provider_call_id,
        "patient_id": None,
        "identity_verified": False,
        "current_intent": None,
        "selected_doctor_id": None,
        "selected_slot_id": None,
        "created_at": now,
        "last_activity_at": now,
    }

    set_session(
        session_id=session_id,
        data=session_data,
        ttl_seconds=settings.max_call_duration_seconds,
    )

    return session_data


def get_call_session(
    session_id: str,
) -> dict[str, Any] | None:
    """
    Retrieve an existing call session.
    """

    return get_session(session_id)


def update_call_session(
    session_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """
    Update temporary call-session state.
    """

    current_session = get_session(session_id)

    if current_session is None:
        raise KeyError(
            f"Session '{session_id}' does not exist."
        )

    now = datetime.now(timezone.utc).isoformat()

    updates = {
        **updates,
        "last_activity_at": now,
    }

    current_session.update(updates)

    settings = get_settings()

    set_session(
        session_id=session_id,
        data=current_session,
        ttl_seconds=settings.max_call_duration_seconds,
    )

    return current_session


def delete_call_session(
    session_id: str,
) -> bool:
    """
    Delete a call session.
    """

    return delete_session(session_id)


def verify_call_session_identity(
    session_id: str,
    patient_id: str,
) -> dict[str, Any]:
    """
    Mark a call session as identity verified.

    Only the patient ID is stored in Redis.
    Sensitive verification information such as
    date of birth is not stored in the session.
    """

    if not patient_id.strip():
        raise ValueError(
            "patient_id cannot be empty."
        )

    return update_call_session(
        session_id=session_id,
        updates={
            "patient_id": patient_id,
            "identity_verified": True,
        },
    )


def set_call_intent(
    session_id: str,
    intent: str,
) -> dict[str, Any]:
    """
    Store the current conversation intent.
    """

    if not intent.strip():
        raise ValueError(
            "intent cannot be empty."
        )

    return update_call_session(
        session_id=session_id,
        updates={
            "current_intent": intent.strip(),
        },
    )


def set_selected_doctor(
    session_id: str,
    doctor_id: str,
) -> dict[str, Any]:
    """
    Store the doctor selected during the current call.
    """

    if not doctor_id.strip():
        raise ValueError(
            "doctor_id cannot be empty."
        )

    return update_call_session(
        session_id=session_id,
        updates={
            "selected_doctor_id": doctor_id,
        },
    )


def set_selected_slot(
    session_id: str,
    slot_id: str,
) -> dict[str, Any]:
    """
    Store the appointment slot selected during the current call.
    """

    if not slot_id.strip():
        raise ValueError(
            "slot_id cannot be empty."
        )

    return update_call_session(
        session_id=session_id,
        updates={
            "selected_slot_id": slot_id,
        },
    )