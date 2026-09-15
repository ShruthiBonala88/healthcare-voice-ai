"""
Phone number utilities for Voxevia.

This module normalizes Indian phone numbers into
E.164 format.

Examples:

    9876543210
    09876543210
    919876543210
    +919876543210
    +91 9876543210
    +91-9876543210

All become:

    +919876543210
"""

import re


INDIA_COUNTRY_CODE = "91"
INDIA_LOCAL_LENGTH = 10


def normalize_phone_number(phone_number: str) -> str:
    """
    Normalize an Indian phone number to E.164 format.

    Raises:
        ValueError: If the phone number is invalid.
    """

    if not isinstance(phone_number, str):
        raise ValueError("Phone number must be a string.")

    phone_number = phone_number.strip()

    if not phone_number:
        raise ValueError("Phone number cannot be empty.")

    # Reject letters and unexpected characters.
    # Allow digits and common phone-number formatting characters.
    if not re.fullmatch(r"[0-9+\-\s().]+", phone_number):
        raise ValueError("Invalid characters in phone number.")

    # Remove formatting characters.
    digits = re.sub(r"\D", "", phone_number)

    # Case 1:
    # 9876543210
    if len(digits) == 10:
        local_number = digits

    # Case 2:
    # 09876543210
    elif len(digits) == 11 and digits.startswith("0"):
        local_number = digits[1:]

    # Case 3:
    # 919876543210
    elif len(digits) == 12 and digits.startswith(INDIA_COUNTRY_CODE):
        local_number = digits[2:]

    else:
        raise ValueError(
            "Invalid Indian phone number format."
        )

    # Indian mobile numbers normally start with 6, 7, 8 or 9.
    if len(local_number) != INDIA_LOCAL_LENGTH:
        raise ValueError(
            "Indian mobile number must contain 10 digits."
        )

    if local_number[0] not in {"6", "7", "8", "9"}:
        raise ValueError(
            "Invalid Indian mobile number."
        )

    return f"+{INDIA_COUNTRY_CODE}{local_number}"


def is_valid_phone_number(phone_number: str) -> bool:
    """
    Return True if the phone number is a valid
    Indian mobile number supported by Voxevia.
    """

    try:
        normalize_phone_number(phone_number)
        return True
    except ValueError:
        return False


def mask_phone_number(phone_number: str) -> str:
    """
    Return a masked phone number for logs.

    Example:

        +919876543210
        -> +91******3210
    """

    normalized = normalize_phone_number(phone_number)

    return (
        normalized[:3]
        + "******"
        + normalized[-4:]
    )