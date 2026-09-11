"""
<<<<<<< HEAD
Appointment scheduling tools. All mutating tools acquire a Redis
distributed lock on the target slot to prevent double-booking when
multiple calls race for the same slot.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
=======
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
"""

from contextlib import contextmanager
from typing import Any
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0

from langchain_core.tools import tool

from app.data.redis_client import get_redis, lock_key
from app.data.supabase_client import get_supabase


<<<<<<< HEAD
@contextmanager
def _slot_lock(slot_id: str, ttl_seconds: int = 15):
    redis = get_redis()
    key = lock_key(f"slot:{slot_id}")
    acquired = redis.set(key, "1", nx=True, ex=ttl_seconds)
    if not acquired:
        raise RuntimeError("This slot is currently being booked by another caller.")
    try:
        yield
=======
# ============================================================
# REDIS SLOT LOCK
# ============================================================

@contextmanager
def _slot_lock(slot_id: str, ttl_seconds: int = 15):
    """
    Acquire a short-lived Redis lock for an appointment slot.

    Redis prevents multiple application workers from attempting
    the same slot at exactly the same time.

    PostgreSQL still provides the actual transaction-level
    correctness through the atomic RPC.
    """

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

>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
    finally:
        redis.delete(key)


<<<<<<< HEAD
@tool
def get_departments() -> list[dict]:
    """List all hospital departments."""
    supabase = get_supabase()
    return supabase.table("departments").select("*").execute().data


@tool
def get_doctors(department_id: str) -> list[dict]:
    """List doctors within a given department."""
    supabase = get_supabase()
    return (
        supabase.table("doctors")
        .select("*")
        .eq("department_id", department_id)
        .execute()
        .data
    )


@tool
def get_doctor_details(doctor_id: str) -> dict:
    """Get detailed info (specialty, bio) for a specific doctor."""
    supabase = get_supabase()
    result = supabase.table("doctors").select("*").eq("id", doctor_id).execute()
    return result.data[0] if result.data else {"found": False}


@tool
def get_available_slots(doctor_id: str, days_ahead: int = 7) -> list[dict]:
    """
    List open (unbooked) appointment slots for a doctor within the next
    `days_ahead` days.
    """
    supabase = get_supabase()
    now = datetime.utcnow()
    end = now + timedelta(days=days_ahead)
    result = (
        supabase.table("appointment_slots")
        .select("*")
        .eq("doctor_id", doctor_id)
        .eq("is_booked", False)
        .gte("start_at", now.isoformat())
        .lte("start_at", end.isoformat())
        .order("start_at")
        .execute()
    )
    return result.data


@tool
def book_appointment(patient_id: str, doctor_id: str, slot_id: str, reason: str = "") -> dict:
    """
    Book an appointment for a patient in a specific open slot. Locks the
    slot to prevent race conditions, marks it booked, and creates the
    appointment record atomically (best-effort; wrap in a DB transaction
    or Postgres function in production for full atomicity).
    """
    supabase = get_supabase()
    with _slot_lock(slot_id):
        slot = supabase.table("appointment_slots").select("*").eq("id", slot_id).execute()
        if not slot.data or slot.data[0]["is_booked"]:
            return {"success": False, "reason": "Slot is no longer available."}

        appointment = (
            supabase.table("appointments")
            .insert(
                {
                    "patient_id": patient_id,
                    "doctor_id": doctor_id,
                    "slot_id": slot_id,
                    "reason": reason,
                    "status": "scheduled",
                }
            )
            .execute()
        )
        supabase.table("appointment_slots").update({"is_booked": True}).eq(
            "id", slot_id
        ).execute()

    return {"success": True, "appointment": appointment.data[0]}


@tool
def cancel_appointment(appointment_id: str) -> dict:
    """Cancel an existing appointment and free up its slot."""
    supabase = get_supabase()
    appt = (
        supabase.table("appointments")
        .update({"status": "cancelled"})
        .eq("id", appointment_id)
        .execute()
    )
    if appt.data:
        slot_id = appt.data[0]["slot_id"]
        supabase.table("appointment_slots").update({"is_booked": False}).eq(
            "id", slot_id
        ).execute()
        return {"success": True}
    return {"success": False, "reason": "Appointment not found."}


@tool
def reschedule_appointment(appointment_id: str, new_slot_id: str) -> dict:
    """Move an existing appointment to a new open slot."""
    supabase = get_supabase()
    with _slot_lock(new_slot_id):
        new_slot = (
            supabase.table("appointment_slots").select("*").eq("id", new_slot_id).execute()
        )
        if not new_slot.data or new_slot.data[0]["is_booked"]:
            return {"success": False, "reason": "New slot is no longer available."}

        old_appt = supabase.table("appointments").select("*").eq("id", appointment_id).execute()
        if not old_appt.data:
            return {"success": False, "reason": "Original appointment not found."}
        old_slot_id = old_appt.data[0]["slot_id"]

        supabase.table("appointments").update({"slot_id": new_slot_id}).eq(
            "id", appointment_id
        ).execute()
        supabase.table("appointment_slots").update({"is_booked": True}).eq(
            "id", new_slot_id
        ).execute()
        supabase.table("appointment_slots").update({"is_booked": False}).eq(
            "id", old_slot_id
        ).execute()

    return {"success": True}
=======
# ============================================================
# DEPARTMENT TOOLS
# ============================================================

@tool
def get_departments() -> list[dict[str, Any]]:
    """
    Return all active hospital departments.
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
def get_doctors(department_id: str | None = None) -> list[dict[str, Any]]:
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
def get_doctor_details(doctor_id: str) -> dict[str, Any]:
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

    The PostgreSQL function:

        book_appointment_atomic

    performs the following operations inside one transaction:

        1. Locks the appointment slot.
        2. Checks that the slot exists.
        3. Checks that the slot is still available.
        4. Creates the appointment.
        5. Marks the slot as booked.

    If any operation fails, PostgreSQL rolls back the transaction.

    Redis provides an additional short-lived application-level lock.
    PostgreSQL remains the final source of truth.
    """

    if not patient_id:
        raise ValueError("patient_id is required.")

    if not slot_id:
        raise ValueError("slot_id is required.")

    # --------------------------------------------------------
    # Redis lock
    # --------------------------------------------------------

    with _slot_lock(slot_id):

        supabase = get_supabase()

        # ----------------------------------------------------
        # PostgreSQL atomic transaction
        # ----------------------------------------------------

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
        raise RuntimeError(
            "Appointment booking failed."
        )

    appointment = response.data

    # Depending on the Supabase client response,
    # the RPC result may be represented as either:
    #
    #   dict
    #
    # or:
    #
    #   list[dict]
    #
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
) -> dict[str, Any]:
    """
    Cancel an existing appointment.
    """

    if not appointment_id:
        raise ValueError(
            "appointment_id is required."
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
        .execute()
    )

    if not response.data:
        return {
            "success": False,
            "reason": "Appointment not found.",
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
) -> dict[str, Any]:
    """
    Reschedule an appointment to another available slot.

    The new slot is protected by the Redis lock.

    NOTE:
    Full rescheduling should eventually use a PostgreSQL
    transaction/RPC similar to atomic booking so that:
        old appointment
        old slot
        new slot

    are changed atomically.

    For now this function performs the basic operation.
    """

    if not appointment_id:
        raise ValueError(
            "appointment_id is required."
        )

    if not new_slot_id:
        raise ValueError(
            "new_slot_id is required."
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

        appointment_response = (
            supabase.table("appointments")
            .select("*")
            .eq("id", appointment_id)
            .limit(1)
            .execute()
        )

        appointments = appointment_response.data or []

        if not appointments:
            return {
                "success": False,
                "reason": "Appointment not found.",
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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
