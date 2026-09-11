"""
Patient API.

Handles hospital patient records.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.data.supabase_client import get_supabase


router = APIRouter(
    prefix="/patients",
    tags=["Patients"],
)


@router.get("")
def get_patients(
    phone: str | None = Query(default=None),
):
    """
    Return patients.

    Optionally search by phone number.
    """

    try:
        supabase = get_supabase()

        query = (
            supabase
            .table("patients")
            .select("*")
        )

        if phone:
            query = query.eq(
                "phone",
                phone,
            )

        response = (
            query
            .order("full_name")
            .execute()
        )

        return {
            "status": "ok",
            "patients": response.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch patients: {exc}",
        )


@router.get("/{patient_id}")
def get_patient(patient_id: str):
    """
    Return one patient.

    The value can be either:
    - patient number, for example P0001
    - patient UUID
    """

    try:
        supabase = get_supabase()

        # -------------------------------------------------
        # 1. First try patient_number
        # -------------------------------------------------

        response = (
            supabase
            .table("patients")
            .select("*")
            .eq("patient_number", patient_id)
            .limit(1)
            .execute()
        )

        if response.data:
            return {
                "status": "ok",
                "patient": response.data[0],
            }

        # -------------------------------------------------
        # 2. If not found, check whether it is a UUID
        # -------------------------------------------------

        try:
            UUID(patient_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="Patient not found.",
            )

        # -------------------------------------------------
        # 3. Search by UUID
        # -------------------------------------------------

        response = (
            supabase
            .table("patients")
            .select("*")
            .eq("id", patient_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Patient not found.",
            )

        return {
            "status": "ok",
            "patient": response.data[0],
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch patient: {exc}",
        )