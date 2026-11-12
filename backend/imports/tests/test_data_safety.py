"""How an import treats personal data and hostile files (findings of the Phase 5 review)."""

import io
import re
import time
import zipfile
from datetime import timedelta

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from audit.models import AuditLog
from conftest import valid_aadhaar
from imports.models import ImportJob
from imports.reader import MAX_COLS, UnreadableFile, read_table
from imports.tests.test_import import sheet_row, workbook_bytes

pytestmark = pytest.mark.django_db

AADHAAR = valid_aadhaar("34567890123")


def upload(client, content: bytes, name="Manju Library.xlsx"):
    return client.post(
        "/api/admin/imports/", {"file": SimpleUploadedFile(name, content)}, format="multipart"
    )


def rows_with_one_error():
    good = sheet_row(roll=1, name="Asha Kumari", mobile="9876543210", aadhaar=AADHAAR)
    bad = sheet_row(roll=2, name="", mobile="9876500001", aadhaar=AADHAAR)  # no name: an error
    return [good, bad]


def test_aadhaar_is_masked_in_answers_and_encrypted_at_rest(owner_api):
    body = upload(owner_api, workbook_bytes(rows_with_one_error())).json()
    assert AADHAAR not in str(body)  # not in the problem rows, the preview or anywhere else
    assert body["preview"] == []
    job = ImportJob.objects.get(pk=body["id"])
    assert bytes(job.content).startswith(b"enc:v1:")  # the uploaded workbook itself
    assert AADHAAR not in str(list(job.rows.values_list("raw", "values", "warnings")))


def test_the_error_file_gives_the_owner_the_full_row_and_is_logged(owner_api):
    job_id = upload(owner_api, workbook_bytes(rows_with_one_error())).json()["id"]
    response = owner_api.get(f"/api/admin/imports/{job_id}/error-file/")
    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    header = [c.value for c in sheet[1]]
    assert header[:2] == ["Row", "Error"]
    aadhaar_column = header.index("Aadhaar No.")
    assert sheet.cell(row=2, column=aadhaar_column + 1).value == AADHAAR  # to fix and re-upload
    entry = AuditLog.objects.get(action="export.import_errors")
    assert entry.metadata["rows"] == 1
    assert 'filename="errors-Manju Library.xlsx"' in response["Content-Disposition"]


def test_an_old_import_still_opens_after_its_file_is_deleted(owner_api):
    job_id = upload(owner_api, workbook_bytes(rows_with_one_error())).json()["id"]
    ImportJob.objects.filter(pk=job_id).update(
        content=None, created_at=timezone.now() - timedelta(days=8)
    )
    response = owner_api.get(f"/api/admin/imports/{job_id}/")
    assert response.status_code == 200
    assert response.json()["file_deleted"] is True and response.json()["columns"] == []


def test_a_damaged_workbook_is_refused_clearly(owner_api):
    content = b"PK\x03\x04" + b"\x00" * 64  # starts like an .xlsx, is not one
    response = upload(owner_api, content)
    assert response.status_code == 400 and "file" in response.json()


def test_a_tiny_file_claiming_huge_size_stays_small():
    book = openpyxl.Workbook()
    book.active.append(["Name", "Mobile"])
    book.active.append(["Asha", "9876543210"])
    plain = io.BytesIO()
    book.save(plain)
    # Rewrite the sheet so it claims to be 16,384 columns wide, as a hostile file would.
    crafted = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(plain.getvalue())) as source,
        zipfile.ZipFile(crafted, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = re.sub(rb'<dimension ref="[^"]+"', b'<dimension ref="A1:XFD2000"', data)
            target.writestr(item, data)
    started = time.monotonic()
    table = read_table(crafted.getvalue())
    assert time.monotonic() - started < 5
    assert table.rows == [["Name", "Mobile"], ["Asha", "9876543210"]]


def test_csv_rows_wider_than_the_limit_are_cut():
    wide = ",".join(["x"] * (MAX_COLS + 500)).encode()
    table = read_table(b"Name,Mobile\r\n" + wide + b"\r\n")
    assert max(len(row) for row in table.rows) <= MAX_COLS


def test_unreadable_files_raise_the_clear_error():
    with pytest.raises(UnreadableFile):
        read_table(b"\xd0\xcf\x11\xe0" + b"\x00" * 32)  # an .xls header and nothing else


def test_imports_stored_the_old_way_are_protected(owner_api):
    from imports.maintenance import protect_legacy_import_data

    job_id = upload(owner_api, workbook_bytes(rows_with_one_error())).json()["id"]
    job = ImportJob.objects.get(pk=job_id)
    # Put the job back the way it was stored before: plain file, plain Aadhaar in the rows.
    ImportJob.objects.filter(pk=job_id).update(content=workbook_bytes(rows_with_one_error()))
    for row in job.rows.all():
        row.raw["Aadhaar No."] = AADHAAR
        row.values = {**row.values, "aadhaar": AADHAAR}
        row.values.pop("aadhaar_cell", None)
        row.warnings = [f"Aadhaar '{AADHAAR[:6]}' is not 12 digits, so it was left out."]
        row.save()

    assert protect_legacy_import_data() == job.rows.count()
    job.refresh_from_db()
    assert bytes(job.content).startswith(b"enc:v1:")
    stored = str(list(job.rows.values_list("raw", "values", "warnings")))
    assert AADHAAR not in stored and AADHAAR[:6] not in stored
    assert protect_legacy_import_data() == 0  # safe to run twice
