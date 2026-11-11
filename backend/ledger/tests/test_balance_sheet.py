"""The old Balance Sheet import, on a workbook laid out like the library's (amounts made up)."""

import io
from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from billing.services import record_payment
from ledger.models import LedgerEntry, LedgerImport
from members.services import create_student

pytestmark = pytest.mark.django_db

URL = "/api/admin/ledger/imports/"


def balance_workbook() -> bytes:
    """Two ledgers side by side under title rows, with empty days, like the real sheet."""
    book = Workbook()
    book.active.title = "Admission Sheet"
    sheet = book.create_sheet("Balance Sheet")
    sheet["B2"], sheet["L2"] = "Total:", "Total:"
    sheet["B4"], sheet["G4"], sheet["J4"] = "INCOME LEDGER", "Balance Amount:", "EXPENSE LEDGER"
    for col, title in zip(
        "BCDE", ["Date", "No. of students", "Daily Collection Amount", "Remarks"], strict=True
    ):
        sheet[f"{col}6"] = title
    for col, title in zip("JKLM", ["Date", "Details", "Amount", "Remarks"], strict=True):
        sheet[f"{col}6"] = title
    income = [(1, 1, 400), (2, 6, 2350), (3, 7, 2800), (4, None, None), (5, None, None)]
    for row, (day, students, amount) in enumerate(income, start=7):
        sheet[f"B{row}"] = date(2025, 7, day)
        sheet[f"C{row}"], sheet[f"D{row}"] = students, amount
    sheet["G7"] = "Total Dues:"
    sheet["J7"], sheet["K7"], sheet["L7"] = date(2025, 7, 2), "Electricity bill", 1500
    sheet["J8"], sheet["K8"], sheet["L8"] = date(2025, 7, 3), "Xerox paper", 120
    sheet["J9"] = date(2025, 7, 4)
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


def upload(client, content: bytes, name: str = "Manju Library.xlsx"):
    return client.post(URL, {"file": SimpleUploadedFile(name, content)}, format="multipart")


def test_balance_sheet_is_checked_then_imported_without_counting_twice(owner_api, branch):
    student = create_student(branch=branch, full_name="Asha Kumari", mobile="9876543210")
    # Imported from the Admission Sheet earlier: part of 2 July, more than all of 3 July.
    record_payment(student=student, amount=Decimal("450"), paid_on=date(2025, 7, 2))
    record_payment(student=student, amount=Decimal("3000"), paid_on=date(2025, 7, 3))

    job = upload(owner_api, balance_workbook()).json()
    assert job["status"] == "CHECKED" and job["sheet"] == "Balance Sheet"
    summary = job["summary"]
    assert (summary["income_days"], Decimal(summary["sheet_income"])) == (3, 5550)
    assert (summary["days_to_add"], Decimal(summary["income_to_add"])) == (2, 2300)
    assert (summary["days_covered"], summary["expenses_to_add"]) == (1, 2)
    assert [d["status"] for d in job["income"]] == ["add", "add", "covered"]
    assert Decimal(job["income"][1]["to_add"]) == 1900
    assert [e["category"] for e in job["expenses"]] == ["electricity", "stationery"]
    assert LedgerEntry.objects.count() == 0  # checking saves nothing

    done = owner_api.post(f"{URL}{job['id']}/commit/").json()
    assert done["status"] == "IMPORTED" and done["summary"]["created"] == 4
    day = owner_api.get("/api/admin/ledger/daily/?from=2025-07-02&to=2025-07-02").json()
    assert day["days"][0]["income"] == 2350  # the sheet's figure: 450 fees + 1900 added
    assert day["days"][0]["expenses"] == 1500
    note = LedgerEntry.objects.get(entry_date=date(2025, 7, 2), category__code="past-fees")
    assert note.details.startswith("6 students, ₹2,350 in the old Balance Sheet")

    again = upload(owner_api, balance_workbook()).json()["summary"]
    assert (again["days_to_add"], again["days_already"], again["expenses_to_add"]) == (0, 2, 0)

    undone = owner_api.post(f"{URL}{job['id']}/undo/").json()
    assert undone["status"] == "UNDONE" and undone["summary"]["removed"] == 4
    assert LedgerEntry.objects.count() == 0


def test_undo_is_refused_once_an_imported_entry_was_changed(owner_api):
    job = upload(owner_api, balance_workbook()).json()
    owner_api.post(f"{URL}{job['id']}/commit/")
    entry = LedgerEntry.objects.filter(import_batch_id=job["id"]).first()
    owner_api.patch(f"/api/admin/ledger/entries/{entry.pk}/", {"amount": "999"}, format="json")
    response = owner_api.post(f"{URL}{job['id']}/undo/")
    assert response.status_code == 400
    assert "changed since" in response.json()["detail"]
    assert LedgerImport.objects.get(pk=job["id"]).status == "IMPORTED"


def test_a_csv_with_only_the_income_ledger_works(owner_api):
    content = (
        b"Date,No. of students,Daily Collection Amount,Remarks\r\n"
        b"01-07-2025,1,400,\r\n"
        b"31-06-2025,2,500,\r\n"
        b"02-07-2025,,,\r\n"
        b'03-07-2025,2,"1,250",Two renewals\r\n'
    )
    job = upload(owner_api, content, "balance.csv").json()
    assert Decimal(job["summary"]["income_to_add"]) == 1650
    assert job["errors"] == [
        {"row": 3, "side": "Income", "message": "Date '31-06-2025' is not a real date."}
    ]
    assert job["income"][1]["remarks"] == "Two renewals"


def test_files_without_a_balance_sheet_and_staff_are_turned_away(owner_api, staff_api):
    response = upload(owner_api, b"Name,Mobile\r\nAsha,9876543210\r\n", "students.csv")
    assert response.status_code == 400
    assert response.json()["file"].startswith("No Balance Sheet found.")
    assert upload(staff_api, balance_workbook()).status_code == 403
