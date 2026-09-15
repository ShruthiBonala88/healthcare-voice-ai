"""
Patient tools for the LangGraph agent.

These tools use the actual M3 Supabase patients schema.

Security:
- Existing patient lookup is protected by the policy layer.
- Only minimum necessary patient fields are returned.
- New patient creation validates required information.
"""

from typing import Optional

from langchain_core.tools import tool

from app.data.supabase_client import get_supabase
from app.utils.phone import normalize_phone_number


@tool
def find_patient(
    phone_number: str,
    last_name: Optional[str] = None,
) -> dict:
    """
    Find an existing patient by phone number.

    This tool should only be called after patient identity
    authorization has been handled by the policy layer.

    The argument name is phone_number while the database
    column is called phone.
    """

    # -----------------------------------------------------
    # Validate phone number
    # -----------------------------------------------------

    if not phone_number or not phone_number.strip():
        raise ValueError("phone_number is required.")

    normalized_phone = normalize_phone_number(phone_number)

    # -----------------------------------------------------
    # Supabase
    # -----------------------------------------------------

    supabase = get_supabase()

    # -----------------------------------------------------
    # Minimum necessary fields
    # -----------------------------------------------------
    #
    # Do NOT use:
    #
    #     .select("*")
    #
    # because the agent does not need every patient field.
    #
    # -----------------------------------------------------

    response = (
        supabase
        .table("patients")
        .select(
            "id, patient_number, full_name, phone"
        )
        .eq("phone", normalized_phone)
        .limit(10)
        .execute()
    )

    patients = response.data or []

    # -----------------------------------------------------
    # Optional last-name filtering
    # -----------------------------------------------------

    if last_name:

        last_name_lower = last_name.strip().lower()

        patients = [
            patient
            for patient in patients
            if patient.get("full_name", "")
            .strip()
            .lower()
            .endswith(last_name_lower)
        ]

    # -----------------------------------------------------
    # Patient not found
    # -----------------------------------------------------

    if not patients:
        return {
            "found": False,
        }

    # -----------------------------------------------------
    # Return minimum necessary information
    # -----------------------------------------------------

    patient = patients[0]

    return {
        "found": True,
        "patient": {
            "id": patient.get("id"),
            "patient_number": patient.get("patient_number"),
            "full_name": patient.get("full_name"),
            "phone": patient.get("phone"),
        },
    }


@tool
def create_patient(
    first_name: str,
    last_name: str,
    phone_number: str,
    date_of_birth: Optional[str] = None,
    email: Optional[str] = None,
) -> dict:
    """
    Create a new patient.

    This operation is allowed during initial registration,
    but required fields are validated before database insertion.
    """

    # -----------------------------------------------------
    # Validate first name
    # -----------------------------------------------------

    if not first_name or not first_name.strip():
        raise ValueError("first_name is required.")

    # -----------------------------------------------------
    # Validate last name
    # -----------------------------------------------------

    if not last_name or not last_name.strip():
        raise ValueError("last_name is required.")

    # -----------------------------------------------------
    # Validate phone
    # -----------------------------------------------------

    if not phone_number or not phone_number.strip():
        raise ValueError("phone_number is required.")

    normalized_phone = normalize_phone_number(phone_number)

    # -----------------------------------------------------
    # Build full name
    # -----------------------------------------------------

    full_name = (
        f"{first_name.strip()} {last_name.strip()}"
    ).strip()

    # -----------------------------------------------------
    # Build database record
    # -----------------------------------------------------

    record = {
        "full_name": full_name,
        "phone": normalized_phone,
        "date_of_birth": date_of_birth,
        "email": email,
    }

    # -----------------------------------------------------
    # Insert patient
    # -----------------------------------------------------

    supabase = get_supabase()

    response = (
        supabase
        .table("patients")
        .insert(record)
        .execute()
    )

    # -----------------------------------------------------
    # Insert failed
    # -----------------------------------------------------

    if not response.data:
        return {
            "created": False,
            "error": "Patient could not be created.",
        }

    # -----------------------------------------------------
    # Return minimum necessary information
    # -----------------------------------------------------

    patient = response.data[0]

    return {
        "created": True,
        "patient": {
            "id": patient.get("id"),
            "patient_number": patient.get("patient_number"),
            "full_name": patient.get("full_name"),
            "phone": patient.get("phone"),
        },
    }