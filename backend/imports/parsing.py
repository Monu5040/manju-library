"""Turn one spreadsheet cell into a clean value, or explain in plain words why it cannot."""

import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from accounts.models import MOBILE_PATTERN, normalize_mobile
from core.crypto import mask_digits
from core.validators import normalize_aadhaar, verhoeff_is_valid


class CellError(ValueError):
    pass


def blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def damaged_number(value) -> bool:
    """Excel shows long numbers like 2.24052E+11 and saving a CSV keeps only that."""
    return isinstance(value, str) and bool(re.fullmatch(r"\s*\d(\.\d+)?[eE]\+?\d+\s*", value))


def parse_text(value) -> str:
    if blank(value):
        return ""
    text = str(value).strip()
    # Undo the formula-safety prefix our own exports add.
    if text.startswith("'") and len(text) > 1 and text[1] in "=+-@":
        text = text[1:]
    return re.sub(r"\s+", " ", text)


def parse_int(value, what: str) -> int | None:
    if blank(value):
        return None
    if isinstance(value, bool):
        raise CellError(f"{what} is not a number.")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip()
    if re.fullmatch(r"\d+(\.0+)?", text):
        return int(float(text))
    raise CellError(f"{what} '{text}' is not a whole number.")


def parse_money(value, what: str) -> Decimal | None:
    if blank(value):
        return None
    if isinstance(value, bool):
        raise CellError(f"{what} is not an amount.")
    text = (
        str(value)
        .strip()
        .replace("₹", "")
        .replace(",", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .strip()
    )
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise CellError(f"{what} '{value}' is not an amount.") from exc
    if amount < 0:
        raise CellError(f"{what} cannot be negative.")
    return amount.quantize(Decimal("0.01"))


_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}


def parse_date(value, what: str, day_first: bool = True) -> date | None:
    if blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and 20000 < value < 80000:
        return date(1899, 12, 30) + timedelta(days=int(value))  # Excel serial number
    text = str(value).strip()
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?", text):
        y, mo, d = map(int, m.groups())
    elif m := re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})", text):
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        d, mo = (a, b) if day_first else (b, a)
        y += 2000 if y < 100 else 0
    elif m := re.fullmatch(r"(\d{1,2})[-/ ]([A-Za-z]{3})[A-Za-z]*[-/ ,]+(\d{2}|\d{4})", text):
        d, mo, y = int(m.group(1)), _MONTHS.get(m.group(2).lower()), int(m.group(3))
        y += 2000 if y < 100 else 0
        if mo is None:
            raise CellError(f"{what} '{text}' is not a date.")
    else:
        raise CellError(f"{what} '{text}' is not a date (use DD-MM-YYYY).")
    try:
        return date(y, mo, d)
    except ValueError as exc:
        raise CellError(f"{what} '{text}' is not a real date.") from exc


def parse_mobile(value) -> str:
    if damaged_number(value):
        raise CellError(
            "The mobile number was damaged by Excel (shown as 2.2E+11). Re-enter it as text."
        )
    mobile = normalize_mobile(value)
    if not re.fullmatch(MOBILE_PATTERN, mobile):
        raise CellError(f"Mobile '{parse_text(value)}' is not a 10-digit Indian mobile number.")
    return mobile


def parse_aadhaar(value) -> tuple[str, str | None]:
    """(digits, warning). Problems only warn: the number is left out, the student still imports."""
    if blank(value):
        return "", None
    if damaged_number(value):
        return "", "Aadhaar was damaged by Excel (shown as 2.2E+11), so it was left out."
    digits = normalize_aadhaar(value)
    if not re.fullmatch(r"[2-9]\d{11}", digits):
        masked = mask_digits(parse_text(value))
        return "", f"Aadhaar {masked} is not 12 digits, so it was left out."
    if not verhoeff_is_valid(digits):
        return "", "Aadhaar has a typing mistake (wrong check digit), so it was left out."
    return digits, None


def parse_gender(value) -> str:
    text = parse_text(value).lower()
    if not text:
        return ""
    if text in {"f", "female", "girl", "woman"}:
        return "F"
    if text in {"m", "male", "boy", "man"}:
        return "M"
    return "O"


def parse_seat(value) -> tuple[str, str | int] | tuple[str, int, str] | None:
    """
    ('seat', '9'); ('waitlist', 7) for W7; ('waitlist', 1, 'WG1') for other waiting-list codes
    such as WG1, keeping the code; None when empty.
    """
    if blank(value):
        return None
    text = parse_text(value).upper().replace(" ", "")
    if isinstance(value, (int, float)):
        text = str(int(value))
    if m := re.fullmatch(r"W(\d+)", text):
        return ("waitlist", int(m.group(1)))
    if m := re.fullmatch(r"W[A-Z]{1,3}-?(\d+)", text):
        return ("waitlist", int(m.group(1)), text)
    if re.fullmatch(r"[A-Z]?\d+[A-Z]?", text):
        return ("seat", text.lstrip("0") or "0")
    raise CellError(f"Seat '{text}' is not a seat number or W-number.")


_TIME = r"(\d{1,2})(?:[:.](\d{2}))?\s*([AaPp])\.?\s*[Mm]\.?"


def _to_time(hour: str, minute: str | None, meridiem: str) -> time:
    h, m = int(hour), int(minute or 0)
    if not (1 <= h <= 12 and 0 <= m < 60):
        raise CellError("Time out of range.")
    if meridiem.lower() == "p" and h != 12:
        h += 12
    if meridiem.lower() == "a" and h == 12:
        h = 0
    return time(h, m)


def parse_time_range(value) -> tuple[time, time] | None:
    """'10:15 AM - 06:30 PM', '08:00AM-02:00PM', '7am to 1pm' → (start, end)."""
    if blank(value):
        return None
    text = parse_text(value)
    m = re.fullmatch(_TIME + r"\s*(?:-|–|—|to)\s*" + _TIME, text, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return _to_time(*m.groups()[:3]), _to_time(*m.groups()[3:])
    except CellError as exc:
        raise CellError(f"Time '{text}' is not valid.") from exc
