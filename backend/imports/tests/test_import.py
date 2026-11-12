"""
Imports, using a workbook laid out like the library's real Admission Sheet (summary row on
top, headers with trailing spaces, formula columns, blank rows) filled with made-up people.
"""

import csv
import io
from datetime import datetime, time, timedelta
from decimal import Decimal

import openpyxl
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import User
from audit.models import AuditLog
from billing.models import Payment
from conftest import valid_aadhaar
from imports import parsing as p
from imports.models import ImportJob, ImportRow
from imports.services import check, commit, plain_aadhaar, setup_job, undo
from library.models import Seat, Shift
from members.models import Membership, Student, WaitlistEntry

pytestmark = pytest.mark.django_db

HEADERS = [
    "Sl. No.",
    "Roll No.",
    "Seat No.",
    "Seat Status",
    "Old Receipt No.",
    "New Receipt No.",
    "Name",
    "Gender",
    "Father's Name",
    "Aadhaar No.",
    "Mobile No. ",
    "Admission Date ",
    "Re-newed Date",
    "Plan",
    "Expiry Date",
    "Days Left",
    "Membership Status",
    "Study Shift",
    "Additional Shift",
    "Study Hours",
    "Shift Charge",
    "Fee Deposited",
    "Due Amount",
    "Paid Date",
    "Due Date",
    "Payment Status",
    "Monthly Avg Fee",
    "Remarks",
]
DAY = "10:15 AM - 06:30 PM"


def sheet_row(**v):
    """One data row in the workbook's column order."""
    order = [
        "sl",
        "roll",
        "seat",
        "seat_status",
        "old_receipt",
        "receipt",
        "name",
        "gender",
        "father",
        "aadhaar",
        "mobile",
        "admitted",
        "renewed",
        "plan",
        "expiry",
        "days_left",
        "status",
        "shift",
        "extra",
        "hours",
        "charge",
        "paid",
        "due",
        "paid_on",
        "due_on",
        "pay_status",
        "avg",
        "remarks",
    ]
    return [v.get(key) for key in order]


def workbook_bytes(rows) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Admission Sheet"
    ws.append(
        [
            "sc",
            None,
            3,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            " ",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "Monthly Average",
            None,
            23075,
        ]
    )
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    for _ in range(5):  # leftover formula rows: empty values
        ws.append([None] * len(HEADERS))
    wb.create_sheet("Balance Sheet")
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def start_dt(days_ago: int) -> datetime:
    day = timezone.localdate() - timedelta(days=days_ago)
    return datetime(day.year, day.month, day.day)


@pytest.fixture
def library_rows():
    s = start_dt(10)
    e = s + timedelta(days=29)
    return [
        sheet_row(
            roll=1,
            seat=9,
            receipt=1101,
            name="TEST ONE",
            gender="Female",
            father="FATHER ONE",
            aadhaar=f"{valid_aadhaar()[:4]}-{valid_aadhaar()[4:8]}-{valid_aadhaar()[8:]}",
            mobile=9000000101,
            admitted=s,
            renewed=s,
            plan=1,
            expiry=e,
            days_left=19,
            status="Active",
            shift=DAY,
            hours="08 Hours",
            charge=450,
            paid=450,
            due=0,
            paid_on=s,
            pay_status="Fully Paid",
        ),
        sheet_row(
            roll=2,
            seat="W7",
            receipt=982,
            name="TEST WAITING",
            gender="Male",
            mobile=9000000102,
            admitted=s,
            renewed=s,
            shift=DAY,
            charge=500,
            paid=500,
            paid_on=s,
        ),
        sheet_row(
            roll=3,
            seat=17,
            receipt=1060,
            name="TEST CUSTOM",
            gender="Female",
            mobile=9000000103,
            admitted="26-12-2023",
            renewed=s,
            plan=2,
            expiry=s + timedelta(days=59),
            extra="08:00AM-02:00PM",
            charge=300,
            paid=250,
            due=50,
            paid_on=s,
            pay_status="Payment Due",
        ),
        sheet_row(
            roll=4,
            seat=20,
            name="TEST DAMAGED AADHAAR",
            mobile=9000000104,
            aadhaar="2.24052E+11",
            admitted=s,
            renewed=s,
            plan=1,
            expiry=e,
            shift="02:30 PM - 06:30 PM",
            charge=350,
            paid=350,
        ),
        sheet_row(
            roll=5,
            seat=21,
            name="TEST NIGHT",
            mobile=9000000105,
            admitted=s,
            renewed=s,
            plan=1,
            expiry=e,
            shift="Night Shift",
            charge=400,
            paid=400,
        ),
        sheet_row(
            roll=6,
            seat=9,
            name="TEST CLASH",
            mobile=9000000106,
            admitted=s,
            renewed=s,
            plan=1,
            expiry=e,
            shift=DAY,
            charge=450,
            paid=450,
        ),
        sheet_row(
            roll=7,
            seat=22,
            receipt=1101,
            name="TEST SIBLING",
            mobile=9000000101,
            admitted=s,
            renewed=s,
            plan=1,
            expiry=e,
            shift="06:00 AM - 10:00 AM",
            charge=250,
            paid=250,
            due_on=" ",
        ),
        sheet_row(roll=8, name="TEST BAD MOBILE", mobile=12345),
        sheet_row(roll=1, name="TEST DUPLICATE ROLL", mobile=9000000108),
        sheet_row(
            roll=9,
            seat=23,
            name="TEST NUMERIC AADHAAR",
            mobile=9000000109,
            aadhaar=int(valid_aadhaar("34567890123")),
            admitted=s,
            renewed=s,
            plan=3,
            shift=DAY,
            charge=1200,
            paid=1000,
        ),
    ]


def run_check(branch, owner, rows):
    job, table = setup_job(
        branch=branch, file_name="Manju Library.xlsx", content=workbook_bytes(rows), by=owner
    )
    return check(job, table)


def row(job, number) -> ImportRow:
    return job.rows.get(row_number=number)


# --- reading and checking --------------------------------------------------------------


def test_header_row_and_columns_are_found(branch, super_admin, library_rows):
    job = run_check(branch, super_admin, library_rows)
    assert job.header_row == 1
    assert job.sheet == "Admission Sheet"
    for field, title in [
        ("mobile", "Mobile No. "),
        ("admission_date", "Admission Date "),
        ("start_date", "Re-newed Date"),
        ("receipt_no", "New Receipt No."),
        ("custom_shift", "Additional Shift"),
        ("paid", "Fee Deposited"),
    ]:
        assert job.mapping[field] == HEADERS.index(title), field
    assert "Due Amount" not in [HEADERS[i] for i in job.mapping.values()]


def test_dry_run_reports_each_problem_and_saves_nothing(branch, super_admin, library_rows):
    job = run_check(branch, super_admin, library_rows)
    assert job.summary["rows"] == 10  # blank leftover rows are ignored
    assert job.summary["errors"] == 4
    assert Student.objects.count() == 0 and Membership.objects.count() == 0

    assert row(job, 3).result == "READY" and row(job, 3).warnings == []
    assert "No membership created" in " ".join(row(job, 4).warnings)  # W7 without an expiry
    assert row(job, 4).values["waitlist_position"] == 7
    assert row(job, 5).values["custom_times"] == ["08:00:00", "14:00:00"]
    assert row(job, 5).values["admission_date"] == "2023-12-26"
    assert "damaged by Excel" in row(job, 6).warnings[0]
    assert "Night Shift" in row(job, 7).errors[0]
    assert "Seat 9 is also given to TEST ONE (row 3)" in row(job, 8).errors[0]
    assert "already used" in row(job, 9).warnings[0]  # receipt 1101 twice
    assert "not a 10-digit" in row(job, 10).errors[0]
    assert "used twice in this file (also row 3)" in row(job, 11).errors[0]
    stored = row(job, 12)
    # Stored encrypted, shown masked: the whole number never sits in the row as plain text.
    assert stored.values["aadhaar"].startswith("enc:v1:")
    assert plain_aadhaar(stored.values["aadhaar"]) == valid_aadhaar("34567890123")
    assert valid_aadhaar("34567890123") not in str(stored.raw)
    assert f"XXXX-XXXX-{valid_aadhaar('34567890123')[-4:]}" in stored.raw.values()


def test_import_refuses_errors_unless_told_to_skip(branch, super_admin, library_rows):
    job = run_check(branch, super_admin, library_rows)
    with pytest.raises(ValidationError, match="4 rows have errors"):
        commit(job, by=super_admin)
    assert Student.objects.count() == 0


def test_import_creates_students_memberships_payments_and_setup(branch, super_admin, library_rows):
    job = commit(run_check(branch, super_admin, library_rows), by=super_admin, skip_errors=True)
    assert job.status == ImportJob.Status.IMPORTED
    assert job.summary["imported"] == 6 and job.summary["skipped"] == 4
    assert Student.objects.count() == 6

    one = Student.objects.get(full_name="TEST ONE")
    assert one.roll_no == 1 and one.aadhaar_last4 == valid_aadhaar()[-4:] and one.gender == "F"
    m = one.memberships.get()
    assert (m.seat.number, m.shift.name, m.price) == ("9", "10:15 AM – 6:30 PM", Decimal("450"))
    assert Payment.objects.get(student=one).receipt_no == 1101

    custom = Student.objects.get(full_name="TEST CUSTOM").memberships.get()
    assert (custom.custom_start_time, custom.custom_end_time) == (time(8), time(14))
    assert custom.shift is None and custom.seat.number == "17"
    assert WaitlistEntry.objects.get().position == 7

    sibling = Student.objects.get(full_name="TEST SIBLING")
    assert sibling.account_id == one.account_id
    assert Payment.objects.get(student=sibling).receipt_no != 1101  # number was taken; a new one

    assert set(Shift.objects.values_list("name", flat=True)) == {
        "10:15 AM – 6:30 PM",
        "2:30 PM – 6:30 PM",
        "6:00 AM – 10:00 AM",
    }
    assert set(Seat.objects.values_list("number", flat=True)) >= {"9", "17", "20", "22", "23"}
    # Later receipts continue after the highest imported number.
    from django.db import transaction

    from billing.services import next_receipt_number

    with transaction.atomic():
        assert next_receipt_number(branch) > 1101


def test_undo_removes_everything_the_import_created(branch, super_admin, library_rows):
    job = commit(run_check(branch, super_admin, library_rows), by=super_admin, skip_errors=True)
    accounts_before = User.objects.filter(role="STUDENT").count()
    assert accounts_before == 5  # siblings share one login
    undo(job, by=super_admin)
    assert Student.objects.count() == Membership.objects.count() == Payment.objects.count() == 0
    assert WaitlistEntry.objects.count() == 0
    assert User.objects.filter(role="STUDENT").count() == 0


def test_undo_is_refused_after_new_activity(branch, super_admin, library_rows):
    from billing.services import record_payment

    job = commit(run_check(branch, super_admin, library_rows), by=super_admin, skip_errors=True)
    record_payment(student=Student.objects.get(full_name="TEST ONE"), amount=Decimal("100"))
    with pytest.raises(ValidationError, match="cannot be undone"):
        undo(job, by=super_admin)


def test_csv_with_semicolons_bom_and_day_first_dates(branch, super_admin):
    text = (
        "\ufeffRoll No.;Name;Mobile No.;Re-newed Date;Expiry Date;Study Shift;Seat No.;"
        "Shift Charge;Fee Deposited\r\n"
    )
    today = timezone.localdate()
    end = today + timedelta(days=20)
    text += f"1;CSV PERSON;+91 90000 00201;{today:%d/%m/%Y};{end:%Y-%m-%d};{DAY};5;₹1,200;1200\r\n"
    job, table = setup_job(
        branch=branch, file_name="students.csv", content=text.encode("utf-8"), by=super_admin
    )
    assert (table.file_format, table.delimiter) == ("csv", ";")
    job = check(job, table)
    assert job.summary["ready"] == 1, list(job.rows.values("errors"))
    values = job.rows.get().values
    assert values["mobile"] == "9000000201"
    assert values["membership"] == {
        "start": today.isoformat(),
        "end": end.isoformat(),
        "price": "1200.00",
    }


def test_windows_1252_csv_is_read(branch, super_admin):
    content = "Name,Mobile No.\r\nJosé Kumar,9000000301\r\n".encode("cp1252")
    job, table = setup_job(
        branch=branch, file_name="old-excel.csv", content=content, by=super_admin
    )
    assert table.rows[1][0] == "José Kumar"


# --- cell parsing -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10:15 AM - 06:30 PM", (time(10, 15), time(18, 30))),
        ("08:00AM-02:00PM", (time(8), time(14))),
        ("7am to 1pm", (time(7), time(13))),
        ("10:45 PM – 6:00 AM", (time(22, 45), time(6))),
        ("Night Shift", None),
    ],
)
def test_time_ranges(text, expected):
    assert p.parse_time_range(text) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("26-12-2023", "2023-12-26"),
        ("05/08/2025", "2025-08-05"),
        ("2025-08-05", "2025-08-05"),
        ("5-Aug-2025", "2025-08-05"),
        (45874, "2025-08-05"),
        ("  ", None),
    ],
)
def test_dates_are_read_day_first(value, expected):
    result = p.parse_date(value, "Date")
    assert (result.isoformat() if result else None) == expected


def test_cell_errors_are_plain_words():
    with pytest.raises(p.CellError, match="not a real date"):
        p.parse_date("31-02-2025", "Expiry date")
    with pytest.raises(p.CellError, match="damaged by Excel"):
        p.parse_mobile("9.87654E+09")
    assert p.parse_seat("W 12") == ("waitlist", 12)
    assert p.parse_seat("WG1") == ("waitlist", 1, "WG1")
    assert p.parse_seat(9) == ("seat", "9")
    assert p.parse_money("₹1,23,450", "Fee") == Decimal("123450.00")
    assert p.parse_text("'=SUM(A1)") == "=SUM(A1)"


# --- API --------------------------------------------------------------------------------------


def test_upload_check_commit_and_files_through_the_api(owner_api, staff_api, library_rows):
    from django.core.files.uploadedfile import SimpleUploadedFile

    upload = SimpleUploadedFile("Manju Library.xlsx", workbook_bytes(library_rows))
    assert (
        staff_api.post("/api/admin/imports/", {"file": upload}, format="multipart").status_code
        == 403
    )

    upload.seek(0)
    created = owner_api.post("/api/admin/imports/", {"file": upload}, format="multipart")
    assert created.status_code == 201, created.json()
    body = created.json()
    assert body["sheets"] == ["Admission Sheet", "Balance Sheet"]
    assert body["summary"]["errors"] == 4 and len(body["problem_rows"]) == 4
    mobile_column = next(c for c in body["columns"] if c["field"] == "mobile")
    assert mobile_column["header"] == "Mobile No."
    assert any(c["ignored"] for c in body["columns"] if c["header"] == "Days Left")

    job_id = body["id"]
    errors = owner_api.get(f"/api/admin/imports/{job_id}/error-file/?file_type=csv")
    assert errors.status_code == 200 and errors["Content-Type"].startswith("text/csv")
    lines = list(csv.reader(io.StringIO(errors.content.decode("utf-8-sig"))))
    assert lines[0][:2] == ["Row", "Error"] and len(lines) == 5

    rejected = owner_api.post(f"/api/admin/imports/{job_id}/commit/", {}, format="json")
    assert rejected.status_code == 400
    done = owner_api.post(
        f"/api/admin/imports/{job_id}/commit/", {"skip_errors": True}, format="json"
    )
    assert (
        done.status_code == 200 and done.json()["status"] == "IMPORTED" and done.json()["can_undo"]
    )
    assert AuditLog.objects.filter(action="import.committed").exists()

    upload.seek(0)
    again = owner_api.post("/api/admin/imports/", {"file": upload}, format="multipart").json()
    assert again["duplicate_of"]["id"] == job_id

    template = owner_api.get("/api/admin/imports/template/")
    sheet = openpyxl.load_workbook(io.BytesIO(template.content)).active
    assert [c.value for c in sheet[1]][:3] == ["Roll No.", "Name", "Father's Name"]


def test_recheck_with_a_different_mapping(owner_api, library_rows):
    from django.core.files.uploadedfile import SimpleUploadedFile

    body = owner_api.post(
        "/api/admin/imports/",
        {"file": SimpleUploadedFile("x.xlsx", workbook_bytes(library_rows))},
        format="multipart",
    ).json()
    mapping = {k: v for k, v in body["mapping"].items() if k != "aadhaar"}
    rechecked = owner_api.post(
        f"/api/admin/imports/{body['id']}/check/", {"mapping": mapping}, format="json"
    ).json()
    assert all("Aadhaar" not in " ".join(r["warnings"]) for r in rechecked["warning_rows"])
    bad = owner_api.post(
        f"/api/admin/imports/{body['id']}/check/",
        {"mapping": {"mobile": 3, "full_name": 3}},
        format="json",
    )
    assert bad.status_code == 400


def test_second_time_slot_is_kept_in_notes(branch, super_admin):
    s = start_dt(3)
    rows = [
        sheet_row(
            roll=1,
            seat=5,
            name="TWO SLOTS",
            mobile=9000000401,
            admitted=s,
            renewed=s,
            plan=1,
            shift="06:00 AM - 10:00 AM",
            extra="04:00PM-08:00PM",
            charge=600,
            paid=600,
        ),
        sheet_row(roll=2, seat="WG1", name="GIRLS WAITLIST", mobile=9000000402, admitted=s),
    ]
    job = commit(run_check(branch, super_admin, rows), by=super_admin)
    m = Student.objects.get(full_name="TWO SLOTS").memberships.get()
    assert m.shift.name == "6:00 AM – 10:00 AM"
    assert "Also studies 4:00 PM – 8:00 PM" in m.notes
    assert WaitlistEntry.objects.get().note == "Waiting list code WG1 in the old sheet"
    assert job.summary["imported"] == 2
