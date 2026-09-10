"""
Doctor Schedule API.

Handles the weekly working schedule of hospital doctors.
"""

from fastapi import APIRouter, HTTPException, Query

from app.data.supabase_client import get_supabase


router = APIRouter(
    prefix="/schedules",
    tags=["Doctor Schedules"],
)


@router.get("")
def get_schedules(
    doctor_id: str | None = Query(default=None),
):
    """
    Return doctor schedules.

    Optionally filter schedules by doctor.
    """

    try:
        supabase = get_supabase()

        query = (
            supabase
            .table("doctor_schedules")
            .select(
                "*, doctors(id, name, specialization)"
            )
            .eq("active", True)
        )

        if doctor_id:
            query = query.eq(
                "doctor_id",
                doctor_id,
            )

        response = (
            query
            .order("day_of_week")
            .order("start_time")
            .execute()
        )

        return {
            "status": "ok",
            "schedules": response.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch schedules: {exc}",
        )


@router.get("/{schedule_id}")
def get_schedule(schedule_id: str):
    """
    Return one doctor schedule.
    """

    try:
        supabase = get_supabase()

        response = (
            supabase
            .table("doctor_schedules")
            .select(
                "*, doctors(id, name, specialization)"
            )
            .eq("id", schedule_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Doctor schedule not found.",
            )

        return {
            "status": "ok",
            "schedule": response.data[0],
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch schedule: {exc}",
        )