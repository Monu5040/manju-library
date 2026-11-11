from datetime import time

import pytest

from audit.models import AuditLog
from billing.models import Payment
from billing.services import next_receipt_number
from members.services import create_student

pytestmark = pytest.mark.django_db


@pytest.fixture
def asha(branch):
    return create_student(branch=branch, full_name="Asha Kumari", mobile="9876543210")


def test_receipts_continue_from_1107_and_after_imported_numbers(branch, asha, staff_api):
    first = staff_api.post(
        "/api/admin/payments/", {"student": asha.id, "amount": 450, "mode": "CASH"}
    ).json()
    assert first["receipt_no"] == 1107
    # A receipt imported from Excel with a higher number pushes the sequence on.
    Payment.objects.create(branch=branch, student=asha, receipt_no=1200, amount=10)
    second = staff_api.post(
        "/api/admin/payments/",
        {"student": asha.id, "amount": 450, "mode": "UPI", "reference": "UPI123"},
    ).json()
    assert second["receipt_no"] == 1201
    assert second["mode_label"] == "UPI"


def test_payments_cannot_be_edited_or_deleted(owner_api, asha):
    payment = owner_api.post("/api/admin/payments/", {"student": asha.id, "amount": 450}).json()
    url = f"/api/admin/payments/{payment['id']}/"
    assert owner_api.patch(url, {"amount": 1}).status_code == 405
    assert owner_api.delete(url).status_code == 405


def test_void_is_owner_only_and_needs_a_reason(owner_api, staff_api, asha):
    payment = staff_api.post("/api/admin/payments/", {"student": asha.id, "amount": 450}).json()
    url = f"/api/admin/payments/{payment['id']}/void/"
    assert staff_api.post(url, {"reason": "typo"}).status_code == 403
    assert owner_api.post(url, {}).status_code == 400
    voided = owner_api.post(url, {"reason": "Entered twice"}).json()
    assert voided["is_void"] is True and voided["void_reason"] == "Entered twice"
    assert owner_api.post(url, {"reason": "again"}).status_code == 400
    assert AuditLog.objects.filter(action="payment.voided").exists()
    summary = owner_api.get("/api/admin/payments/summary/").json()
    assert summary == {"total": 0.0, "count": 0, "by_mode": []}


def test_payment_summary_by_mode_and_search(staff_api, asha):
    staff_api.post("/api/admin/payments/", {"student": asha.id, "amount": 450, "mode": "CASH"})
    staff_api.post("/api/admin/payments/", {"student": asha.id, "amount": 300, "mode": "UPI"})
    summary = staff_api.get("/api/admin/payments/summary/").json()
    assert summary["total"] == 750 and summary["count"] == 2
    assert {row["mode"]: row["total"] for row in summary["by_mode"]} == {"CASH": 450, "UPI": 300}
    assert staff_api.get("/api/admin/payments/?q=1107").json()["count"] == 1
    assert staff_api.get("/api/admin/payments/?q=asha").json()["count"] == 2


def test_receipt_numbers_are_sequential(branch):
    from django.db import transaction

    with transaction.atomic():
        numbers = [next_receipt_number(branch) for _ in range(3)]
    assert numbers == [1107, 1108, 1109]


def test_payment_must_match_the_students_membership(staff_api, asha, branch, seats):
    from decimal import Decimal

    from library.models import Shift
    from members.models import Membership
    from members.services import save_membership

    shift = Shift.objects.create(branch=branch, name="Day", start_time=time(10), end_time=time(18))
    ravi = create_student(branch=branch, full_name="Ravi", mobile="9876543211")
    from django.utils import timezone

    m = save_membership(
        Membership(
            branch=branch,
            student=ravi,
            shift=shift,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            price=Decimal("10"),
        )
    )
    response = staff_api.post(
        "/api/admin/payments/", {"student": asha.id, "membership": m.id, "amount": 10}
    )
    assert response.status_code == 400
