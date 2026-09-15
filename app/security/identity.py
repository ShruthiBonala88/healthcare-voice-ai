"""
Patient identity verification.

This module contains the actual database verification logic.

Verification uses:
    1. Caller phone number
    2. Patient number
    3. Date of birth

This module does NOT contain LangChain tools.
"""

from typing import Any

from app.data.supabase_client import get_supabase
from app.utils.phone import normalize_phone_number


def verify_patient_identity(
    caller_phone: str,
    patient_number: str,
    date_of_birth: str,
) -> dict[str, Any]:
    """
    Verify a hospital patient using caller phone,
    patient number, and date of birth.

    Returns only the minimum information required
    by the application.

    Example success:
        {
            "verified": True,
            "patient_id": "...",
            "patient_number": "P0001"
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

    # Normalize the caller's phone number before querying
    # the database so formats such as:
    # 9876543210
    # 09876543210
    # +91 9876543210
    # +91-9876543210
    # are converted to the same canonical format.
    try:
        caller_phone = normalize_phone_number(caller_phone)
    except ValueError:
        return {
            "verified": False,
            "patient_id": None,
            "reason": "Invalid caller phone number.",
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