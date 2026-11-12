"""One-off protection for imports stored before Aadhaar was masked and encrypted."""

import re

from core.crypto import encrypt, encrypt_bytes, is_encrypted, mask_digits

from .models import ImportJob, ImportRow
from .reader import UnreadableFile, display, read_table

AADHAAR_IN_WARNING = re.compile(r"Aadhaar '([^']*)'")


def _digits(value) -> str:
    return "".join(ch for ch in str(value) if ch.isdigit())


def protect_legacy_import_data() -> int:
    """Encrypt stored uploads and Aadhaar values, mask Aadhaar in the rows as read."""
    changed_rows = 0
    for job in ImportJob.objects.all():
        header_name = None
        content = bytes(job.content) if job.content is not None else None
        if content is not None and not content.startswith(b"enc:v1:"):
            index = (job.mapping or {}).get("aadhaar")
            if index is not None:
                try:
                    header = read_table(content, job.sheet or None).rows[job.header_row]
                    if index < len(header):
                        header_name = display(header[index]) or f"Column {index + 1}"
                except (UnreadableFile, IndexError):
                    header_name = None
            job.content = encrypt_bytes(content)
            job.save(update_fields=["content"])
        for row in ImportRow.objects.filter(job=job):
            raw, values = dict(row.raw), dict(row.values)
            digits = values.get("aadhaar") or ""
            plain = digits if digits and not is_encrypted(digits) else ""
            if plain:
                values["aadhaar"] = encrypt(plain)
            key = header_name if header_name in raw else None
            if key is None and plain:
                key = next((k for k, v in raw.items() if _digits(v) == plain), None)
            if key and not str(raw[key]).startswith("XXXX-XXXX-") and raw[key] != "(hidden)":
                values["aadhaar_cell"] = encrypt(str(raw[key]))
                raw[key] = mask_digits(raw[key])
            warnings = [
                AADHAAR_IN_WARNING.sub(lambda m: f"Aadhaar {mask_digits(m.group(1))}", w)
                for w in row.warnings
            ]
            if (raw, values, warnings) != (row.raw, row.values, row.warnings):
                row.raw, row.values, row.warnings = raw, values, warnings
                row.save(update_fields=["raw", "values", "warnings"])
                changed_rows += 1
    return changed_rows
