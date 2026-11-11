"""Validators shared across apps."""

import re

from django.core.exceptions import ValidationError

# Verhoeff checksum tables; Aadhaar numbers end in a Verhoeff check digit.
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def verhoeff_check_digit(digits: str) -> str:
    check = 0
    for i, char in enumerate(reversed(digits)):
        check = _D[check][_P[(i + 1) % 8][int(char)]]
    return str(_INV[check])


def verhoeff_is_valid(digits: str) -> bool:
    check = 0
    for i, char in enumerate(reversed(digits)):
        check = _D[check][_P[i % 8][int(char)]]
    return check == 0


def normalize_aadhaar(value) -> str:
    """Digits only; Excel often stores Aadhaar as a number or with dashes and spaces."""
    if value is None:
        return ""
    return re.sub(r"\D", "", str(value))


def validate_aadhaar(value: str) -> None:
    digits = normalize_aadhaar(value)
    if not re.fullmatch(r"[2-9]\d{11}", digits):
        raise ValidationError("An Aadhaar number has 12 digits and does not start with 0 or 1.")
    if not verhoeff_is_valid(digits):
        raise ValidationError(
            "This Aadhaar number has a typing mistake (its check digit is wrong)."
        )


def mask_aadhaar(last4: str) -> str:
    return f"XXXX-XXXX-{last4}" if last4 else ""


def format_aadhaar(digits: str) -> str:
    return f"{digits[:4]}-{digits[4:8]}-{digits[8:]}" if len(digits) == 12 else digits
