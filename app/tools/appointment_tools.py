"""
Appointment scheduling tools. All mutating tools acquire a Redis
distributed lock on the target slot to prevent double-booking when
multiple calls race for the same slot.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta

from langchain_core.tools import tool

from app.data.redis_client import get_redis, lock_key
from app.data.supabase_client import get_supabase


@contextmanager
def _slot_lock(slot_id: str, ttl_seconds: int = 15):
    redis = get_redis()
    key = lock_key(f"slot:{slot_id}")
    acquired = redis.set(key, "1", nx=True, ex=ttl_seconds)
    if not acquired:
        raise RuntimeError("This slot is currently being booked by another caller.")
    try:
        yield
    finally:
        redis.delete(key)


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
