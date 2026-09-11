"""
Patient identity verification.

This module verifies a caller against the hospital's
patients table using:
    1. Caller phone number
    2. Patient number
    3. Date of birth

Only the minimum information required for verification
is returned to the agent/application.
"""

from typing import Any

from app.data.supabase_client import get_supabase


def verify_patient_identity(
    caller_phone: str,
    patient_number: str,
    date_of_birth: str,
) -> dict[str, Any]:
    """
    Verify a patient using caller phone, patient number,
    and date of birth.

    Returns:
        {
            "verified": True/False,
            "patient_id": "...",
            "patient_number": "..."
        }
    """

    caller_phone = caller_phone.strip()
    patient_number = patient_number.strip()
    date_of_birth = date_of_birth.strip()

    if not caller_phone:
        return {
            "verified": False,
            "patient_id": None,
            "reason": "Caller phone number is required.",
        }

    if not patient_number:
        return {
            "verified": False,
            "patient_id": None,
            "reason": "Patient number is required.",
        }

    if not date_of_birth:
        return {
            "verified": False,
            "patient_id": None,
            "reason": "Date of birth is required.",
        }

    supabase = get_supabase()

    response = (
        supabase.table("patients")
        .select("id, patient_number")
        .eq("phone", caller_phone)
        .eq("patient_number", patient_number)
        .eq("date_of_birth", date_of_birth)
        .limit(1)
        .execute()
    )

    patients = response.data or []

    if not patients:
        return {
            "verified": False,
            "patient_id": None,
            "reason": "Patient identity could not be verified.",
        }

    patient = patients[0]

    return {
        "verified": True,
        "patient_id": patient["id"],
        "patient_number": patient["patient_number"],
    }