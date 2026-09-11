from langchain_core.tools import tool

from app.data.supabase_client import get_supabase


@tool
def verify_patient_identity(
    phone_number: str,
    date_of_birth: str,
) -> dict:
    """
    Verify a patient using phone number and date of birth.
    """

    supabase = get_supabase()

    result = (
        supabase.table("patients")
        .select("*")
        .eq("phone_number", phone_number)
        .eq("date_of_birth", date_of_birth)
        .execute()
    )

    if not result.data:
        return {
            "verified": False,
            "reason": "Patient identity could not be verified.",
        }

    patient = result.data[0]

    return {
        "verified": True,
        "patient_id": patient["id"],
        "patient": patient,
    }

    