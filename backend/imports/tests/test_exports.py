import io
from decimal import Decimal

import openpyxl
import pytest
from django.utils import timezone

from audit.models import AuditLog
from billing.services import record_payment
from conftest import valid_aadhaar, verified_client
from members.models import Membership
from members.services import create_student, default_end_date, save_membership

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_students(branch, seats, shifts):
    asha = create_student(
        branch=branch, full_name="Asha Kumari", mobile="9876543210", aadhaar=valid_aadhaar()
    )
    sneaky = create_student(branch=branch, full_name='=HYPERLINK("http://x")', mobile="9876543211")
    start = timezone.localdate()
    m = save_membership(
        Membership(
            branch=branch,
            student=asha,
            seat=seats[0],
            shift=shifts["day"],
            start_date=start,
            end_date=default_end_date(start, 1),
            price=Decimal("450"),
        )
    )
    record_payment(student=asha, membership=m, amount=Decimal("200"), mode="UPI")
    return asha, sneaky


def xlsx_rows(response):
    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    return [[c.value for c in row] for row in sheet.iter_rows()]


def test_owner_exports_students_with_masked_aadhaar_by_default(owner_api, two_students):
    response = owner_api.get("/api/admin/students/export/")
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith('attachment; filename="students-')
    rows = xlsx_rows(response)
    header, asha = rows[0], rows[1]
    record = dict(zip(header, asha, strict=False))
    assert record["Name"] == "Asha Kumari"
    assert record["Aadhaar No."] == f"XXXX-XXXX-{valid_aadhaar()[-4:]}"
    assert (
        record["Seat No."],
        record["Shift Charge"],
        record["Fee Deposited"],
        record["Due Amount"],
    ) == ("1", 450, 200, 250)
    assert rows[2][1] == '\'=HYPERLINK("http://x")'  # never runs as a formula

    full = xlsx_rows(owner_api.get("/api/admin/students/export/?include_full_aadhaar=1"))
    assert (
        dict(zip(full[0], full[1], strict=False))["Aadhaar No."].replace("-", "") == valid_aadhaar()
    )
    assert AuditLog.objects.filter(action="export.students", metadata__full_aadhaar=True).exists()


def test_csv_export_is_excel_friendly(owner_api, two_students):
    response = owner_api.get("/api/admin/students/export/?file_type=csv&q=asha")
    content = response.content.decode("utf-8")
    assert content.startswith("\ufeff")
    lines = content.lstrip("\ufeff").splitlines()
    assert len(lines) == 2 and "Asha Kumari" in lines[1]
    assert timezone.localdate().isoformat() in lines[1]  # dates as YYYY-MM-DD


def test_export_rights(staff, owner_api, two_students):
    staff_api = verified_client(staff)
    assert staff_api.get("/api/admin/students/export/").status_code == 403
    staff.can_export = True
    staff.save()
    assert staff_api.get("/api/admin/students/export/").status_code == 200
    assert staff_api.get("/api/admin/students/export/?include_full_aadhaar=1").status_code == 403
    payments = staff_api.get("/api/admin/payments/export/?file_type=csv")
    assert payments.status_code == 200
    lines = payments.content.decode("utf-8-sig").splitlines()
    assert lines[0].startswith("Receipt No.,Date,Roll No.,Name,Amount,Paid By")
    assert ",200,UPI," in lines[1]
