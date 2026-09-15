"""
<<<<<<< HEAD
Patient lookup / creation tools, exposed to the LangGraph agent via
@tool decorators from langchain_core.
"""
=======
Patient tools for the LangGraph agent.

These tools keep the interface expected by M2,
while using the actual M3 Supabase patients schema.
"""

>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
from typing import Optional

from langchain_core.tools import tool

from app.data.supabase_client import get_supabase


@tool
<<<<<<< HEAD
def find_patient(phone_number: str, last_name: Optional[str] = None) -> dict:
    """
    Look up a patient by phone number (and optionally last name to
    disambiguate). Returns patient record or {"found": False}.
    """
    supabase = get_supabase()
    query = supabase.table("patients").select("*").eq("phone_number", phone_number)
    if last_name:
        query = query.eq("last_name", last_name)
    result = query.execute()

    if not result.data:
        return {"found": False}
    return {"found": True, "patient": result.data[0]}
=======
def find_patient(
    phone_number: str,
    last_name: Optional[str] = None,
) -> dict:
    """
    Find an existing patient by phone number.

    The agent uses the argument name phone_number,
    but the database column is called phone.
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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0


@tool
def create_patient(
    first_name: str,
    last_name: str,
    phone_number: str,
    date_of_birth: Optional[str] = None,
    email: Optional[str] = None,
) -> dict:
    """
<<<<<<< HEAD
    Create a new patient record. Use only after confirming the caller is
    not already an existing patient (via find_patient).
    """
    supabase = get_supabase()
    record = {
        "first_name": first_name,
        "last_name": last_name,
        "phone_number": phone_number,
        "date_of_birth": date_of_birth,
        "email": email,
    }
    result = supabase.table("patients").insert(record).execute()
    return {"patient": result.data[0] if result.data else record}
=======
    Create a new patient.

    The agent provides first_name and last_name,
    while the database stores the complete name
    in the full_name column.
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
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
