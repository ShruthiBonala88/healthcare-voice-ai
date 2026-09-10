"""
Appointment Slot API.

Handles available, booked, and blocked appointment slots
for hospital doctors.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.data.supabase_client import get_supabase


router = APIRouter(
    prefix="/slots",
    tags=["Appointment Slots"],
)


@router.get("/availability")
def get_available_slots(
    doctor_id: str = Query(...),
    slot_date: date = Query(...),
):
    """
    Return available appointment slots for a doctor on a specific date.
    """

    try:
        supabase = get_supabase()

        response = (
            supabase
            .table("appointment_slots")
            .select("*")
            .eq("doctor_id", doctor_id)
            .eq("slot_date", slot_date.isoformat())
            .eq("status", "available")
            .order("start_time")
            .execute()
        )

        return {
            "status": "ok",
            "doctor_id": doctor_id,
            "slot_date": slot_date.isoformat(),
            "available_slots": response.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch available slots: {exc}",
        )


@router.get("")
def get_slots(
    doctor_id: str | None = Query(default=None),
    slot_date: date | None = Query(default=None),
):
    """
    Return appointment slots.

    Optional filters:
    - doctor_id
    - slot_date
    """

    try:
        supabase = get_supabase()

        query = (
            supabase
            .table("appointment_slots")
            .select(
                "*, doctors(id, name, specialization)"
            )
        )

        if doctor_id:
            query = query.eq(
                "doctor_id",
                doctor_id,
            )

        if slot_date:
            query = query.eq(
                "slot_date",
                slot_date.isoformat(),
            )

        response = (
            query
            .order("slot_date")
            .order("start_time")
            .execute()
        )

        return {
            "status": "ok",
            "slots": response.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch appointment slots: {exc}",
        )


@router.get("/{slot_id}")
def get_slot(slot_id: str):
    """
    Return one appointment slot.
    """

    try:
        supabase = get_supabase()

        response = (
            supabase
            .table("appointment_slots")
            .select(
                "*, doctors(id, name, specialization)"
            )
            .eq("id", slot_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Appointment slot not found.",
            )

        return {
            "status": "ok",
            "slot": response.data[0],
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch appointment slot: {exc}",
        )