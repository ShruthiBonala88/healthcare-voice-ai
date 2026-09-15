"""
Appointment-related tools for the hospital voice agent.

These tools provide:

- Department lookup
- Doctor lookup
- Doctor details
- Available appointment slots
- Atomic appointment booking
- Appointment cancellation
- Appointment rescheduling

Redis is used as a short-lived distributed lock for appointment slots.

The database RPC is the final source of truth for atomic booking.

Security:
- Protected appointment operations require the verified patient_id.
- Appointment cancellation and rescheduling verify appointment ownership.
"""

from contextlib import contextmanager
from typing import Any

from langchain_core.tools import tool

from app.data.redis_client import get_redis, lock_key
from app.data.supabase_client import get_supabase


# ============================================================
# REDIS SLOT LOCK
# ============================================================


@contextmanager
def _slot_lock(slot_id: str, ttl_seconds: int = 15):
    """
    Acquire a short-lived Redis lock for an appointment slot.

    Redis prevents multiple application workers from attempting
    the same slot at exactly the same time.

    PostgreSQL provides the final transaction-level correctness
    through the atomic RPC.
    """
    if not slot_id:
        raise ValueError("slot_id is required.")

    redis = get_redis()
    key = lock_key(f"slot:{slot_id}")

    acquired = redis.set(
        key,
        "1",
        nx=True,
        ex=ttl_seconds,
    )

    if not acquired:
        raise RuntimeError(
            "This slot is currently being booked by another caller."
        )

    try:
        yield
    finally:
        redis.delete(key)


# ============================================================
# DEPARTMENT TOOLS
# ============================================================


@tool
def get_departments() -> list[dict[str, Any]]:
    """
    Return all hospital departments.
    """
    supabase = get_supabase()

    response = (
        supabase.table("departments")
        .select("*")
        .order("name")
        .execute()
    )

    return response.data or []


# ============================================================
# DOCTOR TOOLS
# ============================================================


@tool
def get_doctors(
    department_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return doctors.

    If department_id is supplied, only doctors belonging
    to that department are returned.
    """
    supabase = get_supabase()

    query = (
        supabase.table("doctors")
        .select("*")
        .order("full_name")
    )

    if department_id:
        query = query.eq("department_id", department_id)

    response = query.execute()

    return response.data or []


@tool
def get_doctor_details(
    doctor_id: str,
) -> dict[str, Any]:
    """
    Return details for one doctor.
    """
    if not doctor_id:
        raise ValueError("doctor_id is required.")

    supabase = get_supabase()

    response = (
        supabase.table("doctors")
        .select("*")
        .eq("id", doctor_id)
        .limit(1)
        .execute()
    )

    doctors = response.data or []

    if not doctors:
        return {
            "found": False,
            "doctor": None,
        }

    return {
        "found": True,
        "doctor": doctors[0],
    }


# ============================================================
# AVAILABLE SLOT TOOL
# ============================================================


@tool
def get_available_slots(
    doctor_id: str,
    slot_date: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return available appointment slots for a doctor.

    slot_date should be YYYY-MM-DD when supplied.
    """
    if not doctor_id:
        raise ValueError("doctor_id is required.")

    supabase = get_supabase()

    query = (
        supabase.table("appointment_slots")
        .select("*")
        .eq("doctor_id", doctor_id)
        .eq("status", "available")
        .order("slot_date")
        .order("start_time")
    )

    if slot_date:
        query = query.eq("slot_date", slot_date)

    response = query.execute()

    return response.data or []


# ============================================================
# ATOMIC APPOINTMENT BOOKING
# ============================================================


@tool
def book_appointment(
    patient_id: str,
    slot_id: str,
    department_id: str | None = None,
    reason: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """
    Atomically book an appointment.

    The PostgreSQL function book_appointment_atomic performs:

    1. Locks the appointment slot.
    2. Checks that the slot exists.
    3. Checks that the slot is still available.
    4. Creates the appointment.
    5. Marks the slot as booked.

    Redis provides an additional short-lived application-level lock.
    PostgreSQL remains the final source of truth.
    """
    if not patient_id:
        raise ValueError("patient_id is required.")

    if not slot_id:
        raise ValueError("slot_id is required.")

    with _slot_lock(slot_id):
        supabase = get_supabase()

        response = supabase.rpc(
            "book_appointment_atomic",
            {
                "p_patient_id": patient_id,
                "p_slot_id": slot_id,
                "p_department_id": department_id,
                "p_reason": reason,
                "p_notes": notes,
            },
        ).execute()

    if not response.data:
        raise RuntimeError("Appointment booking failed.")

    appointment = response.data

    # Supabase RPC may return either a dict or a list.
    if isinstance(appointment, list):
        appointment = appointment[0]

    return {
        "success": True,
        "appointment": appointment,
    }


# ============================================================
# CANCEL APPOINTMENT
# ============================================================


@tool
def cancel_appointment(
    appointment_id: str,
    patient_id: str,
) -> dict[str, Any]:
    """
    Cancel an appointment belonging to the verified patient.

    Security:
        The appointment must belong to patient_id.

    The patient_id must come from the trusted,
    already-verified caller session.
    """
    if not appointment_id:
        raise ValueError(
            "appointment_id is required."
        )

    if not patient_id:
        raise ValueError(
            "patient_id is required."
        )

    supabase = get_supabase()

    response = (
        supabase.table("appointments")
        .update(
            {
                "status": "cancelled",
            }
        )
        .eq("id", appointment_id)
        .eq("patient_id", patient_id)
        .execute()
    )

    if not response.data:
        return {
            "success": False,
            "reason": (
                "Appointment not found or does not belong "
                "to the verified patient."
            ),
        }

    return {
        "success": True,
        "appointment": response.data[0],
    }


# ============================================================
# RESCHEDULE APPOINTMENT
# ============================================================


@tool
def reschedule_appointment(
    appointment_id: str,
    new_slot_id: str,
    patient_id: str,
) -> dict[str, Any]:
    """
    Reschedule an appointment belonging to the verified patient.

    Security:
        The appointment must belong to patient_id.

    The new slot is protected by the Redis lock.
    """
    if not appointment_id:
        raise ValueError(
            "appointment_id is required."
        )

    if not new_slot_id:
        raise ValueError(
            "new_slot_id is required."
        )

    if not patient_id:
        raise ValueError(
            "patient_id is required."
        )

    with _slot_lock(new_slot_id):
        supabase = get_supabase()

        # ----------------------------------------------------
        # Check new slot
        # ----------------------------------------------------

        slot_response = (
            supabase.table("appointment_slots")
            .select("*")
            .eq("id", new_slot_id)
            .limit(1)
            .execute()
        )

        slots = slot_response.data or []

        if not slots:
            return {
                "success": False,
                "reason": "New appointment slot not found.",
            }

        slot = slots[0]

        if slot.get("status") != "available":
            return {
                "success": False,
                "reason": "New appointment slot is not available.",
            }

        # ----------------------------------------------------
        # Get existing appointment
        # ----------------------------------------------------
        #
        # IMPORTANT:
        # The patient_id condition prevents one verified
        # patient from modifying another patient's appointment.
        #

        appointment_response = (
            supabase.table("appointments")
            .select("*")
            .eq("id", appointment_id)
            .eq("patient_id", patient_id)
            .limit(1)
            .execute()
        )

        appointments = appointment_response.data or []

        if not appointments:
            return {
                "success": False,
                "reason": (
                    "Appointment not found or does not belong "
                    "to the verified patient."
                ),
            }

        appointment = appointments[0]
        old_slot_id = appointment.get("slot_id")

        # ----------------------------------------------------
        # Update appointment
        # ----------------------------------------------------

        update_response = (
            supabase.table("appointments")
            .update(
                {
                    "doctor_id": slot["doctor_id"],
                    "slot_id": slot["id"],
                    "appointment_date": slot["slot_date"],
                    "start_time": slot["start_time"],
                    "end_time": slot["end_time"],
                }
            )
            .eq("id", appointment_id)
            .eq("patient_id", patient_id)
            .execute()
        )

        if not update_response.data:
            raise RuntimeError(
                "Failed to update appointment."
            )

        # ----------------------------------------------------
        # Mark new slot booked
        # ----------------------------------------------------

        new_slot_response = (
            supabase.table("appointment_slots")
            .update(
                {
                    "status": "booked",
                }
            )
            .eq("id", new_slot_id)
            .eq("status", "available")
            .execute()
        )

        if not new_slot_response.data:
            raise RuntimeError(
                "Failed to mark new slot as booked."
            )

        # ----------------------------------------------------
        # Release old slot
        # ----------------------------------------------------

        if old_slot_id and old_slot_id != new_slot_id:
            (
                supabase.table("appointment_slots")
                .update(
                    {
                        "status": "available",
                    }
                )
                .eq("id", old_slot_id)
                .execute()
            )

    return {
        "success": True,
        "appointment": update_response.data[0],
    }
