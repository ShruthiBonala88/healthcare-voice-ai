"""
Patient tools for the LangGraph agent.

These tools expose patient lookup and creation operations,
using the Supabase patients schema.
"""
from typing import Optional

from langchain_core.tools import tool

from app.data.supabase_client import get_supabase


@tool
def find_patient(
    phone_number: str,
    last_name: Optional[str] = None,
) -> dict:
    """
    Find an existing patient by phone number.
    Optionally filter by last name to disambiguate.
    
    Args:
        phone_number: Patient's phone number
        last_name: Optional last name to filter results
        
    Returns:
        {"found": True, "patient": {...}} or {"found": False}
    """
    supabase = get_supabase()

    response = (
        supabase
        .table("patients")
        .select("*")
        .eq("phone", phone_number)
        .limit(10)
        .execute()
    )

    patients = response.data or []

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

    if not patients:
        return {
            "found": False,
        }

    patient = patients[0]

    return {
        "found": True,
        "patient": patient,
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
    Create a new patient record.
    Use only after confirming the caller is not already an existing patient.
    
    Args:
        first_name: Patient's first name
        last_name: Patient's last name
        phone_number: Patient's phone number
        date_of_birth: Optional date of birth (YYYY-MM-DD)
        email: Optional email address
        
    Returns:
        {"created": True, "patient": {...}} or {"created": False, "error": "..."}
    """
    supabase = get_supabase()

    full_name = (
        f"{first_name.strip()} {last_name.strip()}"
    ).strip()

    record = {
        "full_name": full_name,
        "phone": phone_number,
        "date_of_birth": date_of_birth,
        "email": email,
    }

    response = (
        supabase
        .table("patients")
        .insert(record)
        .execute()
    )

    if not response.data:
        return {
            "created": False,
            "error": "Patient could not be created.",
        }

    return {
        "created": True,
        "patient": response.data[0],
    }
