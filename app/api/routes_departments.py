"""
Department API.

Handles hospital department information.
"""

from fastapi import APIRouter, HTTPException

from app.data.supabase_client import get_supabase


router = APIRouter(
    prefix="/departments",
    tags=["Departments"],
)


@router.get("")
def get_departments():
    """
    Return all active hospital departments.
    """

    try:
        supabase = get_supabase()

        response = (
            supabase
            .table("departments")
            .select("*")
            .eq("status", "active")
            .order("name")
            .execute()
        )

        return {
            "status": "ok",
            "departments": response.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch departments: {exc}",
        )


@router.get("/{department_id}")
def get_department(department_id: str):
    """
    Return one department by ID.
    """

    try:
        supabase = get_supabase()

        response = (
            supabase
            .table("departments")
            .select("*")
            .eq("id", department_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Department not found.",
            )

        return {
            "status": "ok",
            "department": response.data[0],
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch department: {exc}",
        )