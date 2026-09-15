"""
LangChain tool for patient identity verification.

This module exposes the secure identity-verification
service to the LangGraph agent.

The actual database verification logic lives in:
    app.security.identity

Keeping the database logic in one place prevents
the agent tool and security layer from using different rules.
"""

from langchain_core.tools import tool

from app.security.identity import (
    verify_patient_identity as _verify_patient_identity,
)


@tool
def verify_patient_identity(
    caller_phone: str,
    patient_number: str,
    date_of_birth: str,
) -> dict:
    """
    Verify a hospital patient using:

    1. Caller phone number
    2. Patient number
    3. Date of birth

    Only the minimum verification result is returned.
    """

    return _verify_patient_identity(
        caller_phone=caller_phone,
        patient_number=patient_number,
        date_of_birth=date_of_birth,
    )