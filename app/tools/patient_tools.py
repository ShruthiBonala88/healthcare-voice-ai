"""Patient lookup and creation tools."""

from typing import Optional

from langchain_core.tools import tool

from app.data.supabase_client import get_supabase


@tool
def find_patient(phone_number: str, last_name: Optional[str] = None) -> dict:
    """Find a patient by phone number and optional last name."""
    supabase = get_supabase()
    patients = (
        supabase.table("patients")
        .select("*")
        .eq("phone", phone_number)
        .limit(10)
        .execute()
        .data
        or []
    )
    if last_name:
        suffix = last_name.strip().lower()
        patients = [p for p in patients if p.get("full_name", "").lower().endswith(suffix)]
    return {"found": bool(patients), "patient": patients[0] if patients else None}


@tool
def create_patient(
    first_name: str,
    last_name: str,
    phone_number: str,
    date_of_birth: Optional[str] = None,
    email: Optional[str] = None,
) -> dict:
    """Create a new patient record."""
    record = {
        "full_name": f"{first_name.strip()} {last_name.strip()}".strip(),
        "phone": phone_number,
        "date_of_birth": date_of_birth,
        "email": email,
    }
    response = get_supabase().table("patients").insert(record).execute()
    if not response.data:
        return {"created": False, "error": "Patient could not be created."}
    return {"created": True, "patient": response.data[0]}
