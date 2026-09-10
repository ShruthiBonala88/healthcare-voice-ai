"""
Patient lookup / creation tools, exposed to the LangGraph agent via
@tool decorators from langchain_core.
"""
from typing import Optional

from langchain_core.tools import tool

from app.data.supabase_client import get_supabase


@tool
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


@tool
def create_patient(
    first_name: str,
    last_name: str,
    phone_number: str,
    date_of_birth: Optional[str] = None,
    email: Optional[str] = None,
) -> dict:
    """
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
