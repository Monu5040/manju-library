"""Which spreadsheet column holds which value: aliases, header-row detection, auto-mapping."""

import re

# field -> (label shown in the app, header names it is known by)
FIELDS: dict[str, tuple[str, list[str]]] = {
    "roll_no": ("Roll no.", ["roll no", "roll", "roll number", "roll no."]),
    "full_name": ("Name", ["name", "student name", "full name", "student"]),
    "father_name": ("Father's name", ["fathers name", "father name", "guardian", "guardian name"]),
    "gender": ("Gender", ["gender", "sex"]),
    "mobile": ("Mobile", ["mobile no", "mobile", "mobile number", "phone", "phone no", "contact"]),
    "aadhaar": ("Aadhaar", ["aadhaar no", "aadhaar", "aadhar", "aadhar no", "aadhaar number"]),
    "admission_date": ("Admission date", ["admission date", "date of admission", "joining date"]),
    "seat": ("Seat (number or W1, W2… for waiting list)", ["seat no", "seat", "seat number"]),
    "shift": ("Shift (e.g. 10:15 AM - 06:30 PM)", ["study shift", "shift", "timing", "time"]),
    "custom_shift": (
        "Extra / custom time",
        ["additional shift", "custom shift", "custom time", "extra shift"],
    ),
    "start_date": (
        "Start (renewed) date",
        ["re newed date", "renewed date", "renewal date", "start date", "from"],
    ),
    "plan_months": ("Plan (months)", ["plan", "months", "subscription plan", "plan months"]),
    "end_date": ("Expiry date", ["expiry date", "end date", "valid till", "expiry", "to"]),
    "price": (
        "Fee for the plan (₹)",
        ["shift charge", "fee", "fees", "charge", "price", "plan fee"],
    ),
    "paid": ("Amount paid (₹)", ["fee deposited", "paid", "amount paid", "deposited", "amount"]),
    "paid_on": ("Paid date", ["paid date", "payment date", "date paid"]),
    "receipt_no": ("Receipt no.", ["new receipt no", "receipt no", "receipt", "receipt number"]),
    "notes": ("Remarks", ["remarks", "notes", "note", "comment"]),
}

# Columns the old workbook calculated with formulas or no longer needs; recalculated here.
IGNORED_HEADERS = {
    "sl no",
    "days left",
    "membership status",
    "payment status",
    "monthly avg fee",
    "due amount",
    "due date",
    "study hours",
    "seat status",
    "old receipt no",
}


def normalize_header(value) -> str:
    text = str(value or "").lower().replace("’", "'").replace("'", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


_ALIASES = {
    normalize_header(alias): key for key, (_, aliases) in FIELDS.items() for alias in aliases
}


def field_for(header) -> str | None:
    return _ALIASES.get(normalize_header(header))


def detect_header_row(rows: list[list], scan: int = 15) -> int:
    """Index of the row that looks most like column titles (most known names)."""
    best_index, best_score = 0, -1
    for index, row in enumerate(rows[:scan]):
        score = sum(
            1 for cell in row if field_for(cell) or normalize_header(cell) in IGNORED_HEADERS
        )
        if score > best_score:
            best_index, best_score = index, score
    return best_index


def auto_mapping(header: list) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(header):
        key = field_for(cell)
        if key and key not in mapping:
            mapping[key] = index
    return mapping


def describe_columns(header: list, mapping: dict[str, int]) -> list[dict]:
    by_index = {index: key for key, index in mapping.items()}
    columns = []
    for index, cell in enumerate(header):
        name = str(cell).strip() if cell is not None else ""
        if not name and index not in by_index:
            continue
        columns.append(
            {
                "index": index,
                "header": name or f"Column {index + 1}",
                "field": by_index.get(index),
                "ignored": normalize_header(cell) in IGNORED_HEADERS,
            }
        )
    return columns
