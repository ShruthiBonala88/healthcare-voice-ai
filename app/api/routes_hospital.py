from fastapi import APIRouter, HTTPException

from app.data.supabase_client import get_supabase


router = APIRouter(
    prefix="/hospital",
    tags=["Hospital"],
)


@router.get("")
def get_hospital():
    """
    Return hospital information.
    """

    try:
        supabase = get_supabase()

        response = (
            supabase
            .table("hospital_information")
            .select("*")
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Hospital information not found.",
            )

        return {
            "status": "ok",
            "hospital": response.data[0],
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch hospital information: {exc}",
        )