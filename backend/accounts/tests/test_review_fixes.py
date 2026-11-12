"""Findings of the Phase 5 access-control review, each kept fixed by a test."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.utils import timezone

from audit.models import AuditLog
from billing.services import record_payment
from ledger.models import CashClosing, LedgerCategory
from members.models import Membership
from members.services import create_student, save_membership

pytestmark = pytest.mark.django_db


@pytest.fixture
def membership(branch, shifts):
    person = create_student(branch=branch, full_name="Asha Kumari", mobile="9876543210")
    start = timezone.localdate()
    return save_membership(
        Membership(
            branch=branch,
            student=person,
            shift=shifts["day"],
            start_date=start,
            end_date=start + timedelta(days=29),
            price=Decimal("450"),
        )
    )


def test_staff_cannot_write_off_fees_or_add_free_months(membership, staff_api, owner_api, shifts):
    url = f"/api/admin/memberships/{membership.pk}/"
    later = (membership.end_date + timedelta(days=365)).isoformat()
    for change in ({"discount": "450"}, {"end_date": later}, {"price": "1"}):
        assert staff_api.patch(url, change, format="json").status_code == 403
    moved = staff_api.patch(url, {"shift": shifts["morning"].pk, "notes": "Moved"}, format="json")
    assert moved.status_code == 200  # the seat, shift and notes stay staff work
    assert owner_api.patch(url, {"discount": "50"}, format="json").status_code == 200


def test_closed_cash_days_cannot_receive_backdated_cash(membership, staff_api, branch, super_admin):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    CashClosing.objects.create(
        branch=branch,
        day=yesterday,
        period_start=yesterday,
        opening=0,
        cash_in=0,
        cash_out=0,
        expected=0,
        counted=0,
        closed_by=super_admin,
    )
    body = {"student": membership.student_id, "amount": "450", "mode": "CASH"}
    backdated = staff_api.post(
        "/api/admin/payments/", {**body, "paid_on": str(yesterday)}, format="json"
    )
    assert backdated.status_code == 400 and "already counted" in str(backdated.json())
    future = staff_api.post(
        "/api/admin/payments/", {**body, "paid_on": str(today + timedelta(days=2))}, format="json"
    )
    assert future.status_code == 400
    upi = {**body, "mode": "UPI", "paid_on": str(yesterday)}  # not in the drawer: allowed
    assert staff_api.post("/api/admin/payments/", upi, format="json").status_code == 201
    assert staff_api.post("/api/admin/payments/", body, format="json").status_code == 201  # today

    category = LedgerCategory.objects.get(code="rent")
    entry = {"category": category.pk, "amount": "100", "mode": "CASH", "entry_date": str(yesterday)}
    refused = staff_api.post("/api/admin/ledger/entries/", entry, format="json")
    assert refused.status_code == 400 and "entry_date" in refused.json()
    # Imports bring in old payments on purpose, and may.
    record_payment(
        student=membership.student, amount=Decimal("10"), paid_on=yesterday, check_closed_days=False
    )


def test_reformatting_a_mobile_does_not_reset_the_guess_limit(api, staff):
    cache.clear()
    tries = ["9123456781", "+91 91234 56781", "91234-56781", "9123456781a", " 9123456781 "]
    codes = []
    for n in range(12):
        identifier = tries[n % len(tries)]
        response = api.post(
            "/api/auth/admin/login/", {"identifier": identifier, "password": "wrong"}, format="json"
        )
        codes.append(response.status_code)
    assert 429 in codes  # one bucket for the account, however it was typed


def test_staff_password_resets_are_recorded(owner_api, staff):
    response = owner_api.patch(
        f"/api/admin/staff/{staff.pk}/", {"password": "a-new-long-password-123"}, format="json"
    )
    assert response.status_code == 200
    assert AuditLog.objects.filter(action="staff.password_reset", entity_id=str(staff.pk)).exists()


def test_backoffice_sign_ins_are_recorded(client, super_admin):
    client.post("/backoffice/login/", {"username": super_admin.mobile, "password": "wrong"})
    failed = AuditLog.objects.get(action="backoffice.login_failed")
    assert super_admin.mobile not in str(failed.metadata)
