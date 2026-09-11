"""
Doctor API.

Handles doctors working in the hospital.
"""

from fastapi import APIRouter, HTTPException, Query

from app.data.supabase_client import get_supabase


router = APIRouter(
    prefix="/doctors",
    tags=["Doctors"],
)


@router.get("")
def get_doctors(
    department_id: str | None = Query(default=None),
):
    """
    Return active doctors.

    Optionally filter doctors by department.
    """

    try:
        supabase = get_supabase()

        query = (
            supabase
            .table("doctors")
            .select(
                "*, departments(id, name)"
            )
            .eq("status", "active")
        )

        if department_id:
            query = query.eq(
                "department_id",
                department_id,
            )

        response = (
            query
            .order("name")
            .execute()
        )

        return {
            "status": "ok",
            "doctors": response.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch doctors: {exc}",
        )


@router.get("/{doctor_id}")
def get_doctor(doctor_id: str):
    """
    Return one doctor by ID.
    """

    try:
        supabase = get_supabase()

        response = (
            supabase
            .table("doctors")
            .select(
                "*, departments(id, name)"
            )
            .eq("id", doctor_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Doctor not found.",
            )

        return {
            "status": "ok",
            "doctor": response.data[0],
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch doctor: {exc}",
        )