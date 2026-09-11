"""Appointment tools with a short-lived Redis slot lock."""

from contextlib import contextmanager
from typing import Any

from langchain_core.tools import tool

from app.data.redis_client import get_redis, lock_key
from app.data.supabase_client import get_supabase


@contextmanager
def _slot_lock(slot_id: str, ttl_seconds: int = 15):
    redis = get_redis()
    key = lock_key(f"slot:{slot_id}")
    if not redis.set(key, "1", nx=True, ex=ttl_seconds):
        raise RuntimeError("This slot is currently being booked by another caller.")
    try:
        yield
    finally:
        redis.delete(key)


@tool
def get_departments() -> list[dict[str, Any]]:
    """List hospital departments."""
    return get_supabase().table("departments").select("*").order("name").execute().data or []


@tool
def get_doctors(department_id: str | None = None) -> list[dict[str, Any]]:
    """List doctors, optionally filtered by department."""
    query = get_supabase().table("doctors").select("*").order("full_name")
    if department_id:
        query = query.eq("department_id", department_id)
    return query.execute().data or []


@tool
def get_doctor_details(doctor_id: str) -> dict[str, Any]:
    """Return details for one doctor."""
    rows = get_supabase().table("doctors").select("*").eq("id", doctor_id).limit(1).execute().data or []
    return {"found": bool(rows), "doctor": rows[0] if rows else None}


@tool
def get_available_slots(doctor_id: str, slot_date: str | None = None) -> list[dict[str, Any]]:
    """List available appointment slots."""
    query = (
        get_supabase().table("appointment_slots").select("*")
        .eq("doctor_id", doctor_id).eq("status", "available")
        .order("slot_date").order("start_time")
    )
    if slot_date:
        query = query.eq("slot_date", slot_date)
    return query.execute().data or []


@tool
def book_appointment(
    patient_id: str,
    slot_id: str,
    department_id: str | None = None,
    reason: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Book an available appointment slot."""
    with _slot_lock(slot_id):
        result = get_supabase().rpc("book_appointment_atomic", {
            "p_patient_id": patient_id,
            "p_slot_id": slot_id,
            "p_department_id": department_id,
            "p_reason": reason,
            "p_notes": notes,
        }).execute()
    if not result.data:
        raise RuntimeError("Appointment booking failed.")
    appointment = result.data[0] if isinstance(result.data, list) else result.data
    return {"success": True, "appointment": appointment}


@tool
def cancel_appointment(appointment_id: str) -> dict[str, Any]:
    """Cancel an existing appointment."""
    result = get_supabase().table("appointments").update({"status": "cancelled"}).eq("id", appointment_id).execute()
    return {"success": bool(result.data), "appointment": result.data[0] if result.data else None}


@tool
def reschedule_appointment(appointment_id: str, new_slot_id: str) -> dict[str, Any]:
    """Move an appointment to another available slot."""
    supabase = get_supabase()
    with _slot_lock(new_slot_id):
        slot_rows = supabase.table("appointment_slots").select("*").eq("id", new_slot_id).limit(1).execute().data or []
        appointment_rows = supabase.table("appointments").select("*").eq("id", appointment_id).limit(1).execute().data or []
        if not slot_rows or slot_rows[0].get("status") != "available":
            return {"success": False, "reason": "New appointment slot is not available."}
        if not appointment_rows:
            return {"success": False, "reason": "Appointment not found."}
        old_slot_id = appointment_rows[0].get("slot_id")
        updated = supabase.table("appointments").update({"slot_id": new_slot_id, "doctor_id": slot_rows[0]["doctor_id"]}).eq("id", appointment_id).execute()
        supabase.table("appointment_slots").update({"status": "booked"}).eq("id", new_slot_id).execute()
        if old_slot_id:
            supabase.table("appointment_slots").update({"status": "available"}).eq("id", old_slot_id).execute()
    return {"success": bool(updated.data), "appointment": updated.data[0] if updated.data else None}
