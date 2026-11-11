from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from audit.models import AuditLog
from billing.services import record_payment, void_payment
from members.models import Membership
from members.services import create_student, default_end_date, save_membership
from portal.models import Notice

pytestmark = pytest.mark.django_db


@pytest.fixture
def family(branch, seats, shifts, day_plan):
    """Two siblings sharing their parent's phone, and an unrelated student."""
    kavya = create_student(
        branch=branch, full_name="Kavya Sinha", mobile="9470000001", father_name="Sanjay"
    )
    satya = create_student(branch=branch, full_name="Satya Prakash", mobile="9470000001")
    other = create_student(branch=branch, full_name="Someone Else", mobile="9470000009")
    start = timezone.localdate() - timedelta(days=25)
    m = save_membership(
        Membership(
            branch=branch,
            student=kavya,
            plan=day_plan,
            shift=shifts["day"],
            seat=seats[0],
            start_date=start,
            end_date=default_end_date(start, 1),
            price=Decimal("450"),
            notes="Staff only: asked for a fan seat",
        )
    )
    record_payment(
        student=kavya, membership=m, amount=Decimal("300"), mode="UPI", reference="UPI-1"
    )
    void = record_payment(student=kavya, membership=m, amount=Decimal("50"))
    void_payment(void, reason="Typed twice")
    other_payment = record_payment(student=other, amount=Decimal("100"))
    return kavya, satya, other, other_payment


def portal_client(student) -> APIClient:
    client = APIClient()
    client.force_login(student.account)
    return client


def test_home_shows_both_siblings_notices_and_fees(family, branch, day_plan):
    kavya, satya, *_ = family
    Notice.objects.create(branch=branch, title="Closed on Diwali", body="Library closed 1 Nov.")
    Notice.objects.create(
        branch=branch,
        title="Old",
        body="x",
        starts_on=timezone.localdate() - timedelta(days=9),
        ends_on=timezone.localdate() - timedelta(days=2),
    )
    Notice.objects.create(
        branch=branch, title="Later", body="x", starts_on=timezone.localdate() + timedelta(days=3)
    )

    home = portal_client(kavya).get("/api/portal/home/").json()
    assert [p["full_name"] for p in home["profiles"]] == ["Kavya Sinha", "Satya Prakash"]
    first = home["profiles"][0]
    current = first["current_membership"]
    assert (
        current["seat_number"],
        current["shift_name"],
        current["paid_total"],
        current["due_total"],
    ) == ("1", "Day", 300, 150)
    assert current["days_left"] <= 7 and first["total_due"] == 150
    assert home["profiles"][1]["current_membership"] is None
    assert [n["title"] for n in home["notices"]] == ["Closed on Diwali"]
    assert home["plans"][0]["price"] == 450 and home["library"]["name"] == "Manju Library"


def test_detail_hides_staff_only_information(family):
    kavya, *_ = family
    detail = portal_client(kavya).get(f"/api/portal/students/{kavya.id}/").json()
    assert "notes" not in detail["memberships"][0]
    payments = detail["payments"]
    assert {p["amount"] for p in payments} == {300, 50}
    assert all(
        set(p) == {"id", "receipt_no", "paid_on", "amount", "mode_label", "reference", "is_void"}
        for p in payments
    )
    assert "Staff only" not in str(detail) and "Typed twice" not in str(detail)


def test_students_cannot_see_other_students(family):
    kavya, _, other, other_payment = family
    client = portal_client(kavya)
    assert client.get(f"/api/portal/students/{other.id}/").status_code == 404
    assert client.get(f"/api/portal/receipts/{other_payment.id}/").status_code == 404
    own = kavya.payments.first()
    receipt = client.get(f"/api/portal/receipts/{own.id}/").json()
    assert (
        receipt["student_name"] == "Kavya Sinha" and receipt["library"]["name"] == "Manju Library"
    )


def test_students_update_only_contact_details(family):
    kavya, *_ = family
    client = portal_client(kavya)
    response = client.patch(
        f"/api/portal/students/{kavya.id}/",
        {
            "address": "Ward 4, Station Road",
            "alt_mobile": "+91 98765 43210",
            "full_name": "Hacked",
            "roll_no": 99,
        },
        format="json",
    )
    assert response.status_code == 200
    kavya.refresh_from_db()
    assert (kavya.address, kavya.alt_mobile, kavya.full_name, kavya.roll_no) == (
        "Ward 4, Station Road",
        "9876543210",
        "Kavya Sinha",
        1,
    )
    assert AuditLog.objects.filter(
        action="portal.profile_updated", entity_id=str(kavya.id)
    ).exists()
    bad = client.patch(f"/api/portal/students/{kavya.id}/", {"alt_mobile": "123"}, format="json")
    assert bad.status_code == 400


def test_portal_is_for_students_only(staff_api, family):
    kavya, *_ = family
    assert staff_api.get("/api/portal/home/").status_code == 403
    assert APIClient().get("/api/portal/home/").status_code == 403


def test_notice_permissions(staff_api, owner_api):
    created = staff_api.post(
        "/api/admin/notices/", {"title": "Exam week", "body": "Quiet please."}, format="json"
    )
    assert created.status_code == 201, created.json()
    notice_id = created.json()["id"]
    assert created.json()["created_by_name"] == "Front Desk"
    assert (
        staff_api.patch(
            f"/api/admin/notices/{notice_id}/", {"is_pinned": True}, format="json"
        ).status_code
        == 200
    )
    bad = staff_api.patch(
        f"/api/admin/notices/{notice_id}/",
        {"starts_on": "2026-12-10", "ends_on": "2026-12-01"},
        format="json",
    )
    assert bad.status_code == 400
    assert staff_api.delete(f"/api/admin/notices/{notice_id}/").status_code == 403
    assert owner_api.delete(f"/api/admin/notices/{notice_id}/").status_code == 204


def test_correcting_a_mobile_moves_the_portal_to_the_new_number(family, owner_api, staff):
    kavya, *_ = family
    old_login = portal_client(kavya)

    response = owner_api.patch(
        f"/api/admin/students/{kavya.pk}/", {"mobile": "9470000055"}, format="json"
    )
    assert response.status_code == 200
    kavya.refresh_from_db()
    assert kavya.account.mobile == "9470000055"
    assert old_login.get(f"/api/portal/students/{kavya.pk}/").status_code == 404
    assert portal_client(kavya).get(f"/api/portal/students/{kavya.pk}/").status_code == 200

    # A staff member's number never becomes a student login, and the old link is dropped.
    response = owner_api.patch(
        f"/api/admin/students/{kavya.pk}/", {"mobile": staff.mobile}, format="json"
    )
    assert response.status_code == 200
    kavya.refresh_from_db()
    assert kavya.account is None
