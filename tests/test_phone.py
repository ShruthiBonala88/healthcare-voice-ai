from app.utils.phone import (
    is_valid_phone_number,
    mask_phone_number,
    normalize_phone_number,
)


def test_normalize_phone_number():
    assert normalize_phone_number("9876543210") == "+919876543210"
    assert normalize_phone_number("09876543210") == "+919876543210"
    assert normalize_phone_number("919876543210") == "+919876543210"
    assert normalize_phone_number("+919876543210") == "+919876543210"
    assert normalize_phone_number("+91 9876543210") == "+919876543210"
    assert normalize_phone_number("+91-9876543210") == "+919876543210"


def test_valid_phone_number():
    assert is_valid_phone_number("9876543210") is True
    assert is_valid_phone_number("+919876543210") is True


def test_invalid_phone_number():
    assert is_valid_phone_number("1234567890") is False
    assert is_valid_phone_number("987654321") is False
    assert is_valid_phone_number("abc") is False


def test_mask_phone_number():
    assert mask_phone_number("+919876543210") == "+91******3210"