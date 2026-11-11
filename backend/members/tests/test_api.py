from datetime import timedelta

import pytest
from django.utils import timezone

from audit.models import AuditLog
from conftest import valid_aadhaar
from members.models import Membership, Student

pytestmark = pytest.mark.django_db


def admit(
    api,
    *,
    name="Asha Kumari",
    mobile="9876543210",
    seat=None,
    shift=None,
    plan=None,
    start=None,
    pay=None,
    **student,
):
    body = {
        "student": {"full_name": name, "mobile": mobile, **student},
        "membership": {
            "plan": plan.id if plan else None,
            "shift": shift.id if shift else None,
            "seat": seat.id if seat else None,
            "start_date": (start or timezone.localdate()).isoformat(),
        },
    }
    if pay is not None:
        body["payment"] = {"amount": pay, "mode": "UPI"}
    return api.post("/api/admin/admissions/", body, format="json")


# --- admissions ------------------------------------------------------------------


def test_staff_admit_a_student_with_seat_plan_and_payment(staff_api, seats, shifts, day_plan):
    response = admit(staff_api, seat=seats[0], plan=day_plan, pay=200, aadhaar=valid_aadhaar())
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["student"]["roll_no"] == 1
    assert body["student"]["aadhaar_masked"].startswith("XXXX-XXXX-")
    assert "aadhaar" not in body["student"]
    m = body["membership"]
    assert (m["seat_number"], m["shift_name"], m["price"], m["paid_total"], m["due_total"]) == (
        "1",
        "Day",
        450,
        200,
        250,
    )
    assert (
        m["end_date"] == (timezone.localdate() + timedelta(days=30)).isoformat()
        or m["state"] == "ACTIVE"
    )
    assert body["payment"]["receipt_no"] == 1107
    assert body["student"]["total_due"] == 250
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"student.created", "membership.created", "payment.created"} <= actions


def test_admission_is_all_or_nothing(staff_api, seats, shifts, day_plan):
    assert admit(staff_api, seat=seats[0], plan=day_plan).status_code == 201
    clash = admit(staff_api, name="Ravi Kumar", mobile="9876543211", seat=seats[0], plan=day_plan)
    assert clash.status_code == 400
    assert "Seat 1 is already given to Asha Kumari" in clash.json()["seat"][0]
    assert not Student.objects.filter(full_name="Ravi Kumar").exists()


def test_invalid_aadhaar_and_mobile_are_rejected(staff_api, seats, day_plan):
    response = admit(staff_api, mobile="12345", plan=day_plan, aadhaar="2345 6789 0123")
    assert response.status_code == 400
    errors = response.json()["student"]
    assert "mobile" in errors and "aadhaar" in errors


# --- students list ---------------------------------------------------------------------


def test_student_list_search_and_filters(staff_api, seats, shifts, day_plan):
    today = timezone.localdate()
    admit(staff_api, name="Asha Kumari", mobile="9876543210", seat=seats[0], plan=day_plan, pay=450)
    admit(
        staff_api,
        name="Ravi Kumar",
        mobile="9876543211",
        seat=seats[1],
        plan=day_plan,
        start=today - timedelta(days=27),
    )
    admit(
        staff_api,
        name="Sonu Kumar",
        mobile="9876543212",
        seat=seats[2],
        plan=day_plan,
        start=today - timedelta(days=90),
    )

    def names(query):
        response = staff_api.get(f"/api/admin/students/?{query}")
        assert response.status_code == 200
        return [s["full_name"] for s in response.json()["results"]]

    assert names("q=ravi") == ["Ravi Kumar"]
    assert names("q=9876543212") == ["Sonu Kumar"]
    assert names("q=1") == ["Asha Kumari"]
    assert names("expiring_within=7") == ["Ravi Kumar"]
    assert names("has_due=true") == ["Ravi Kumar", "Sonu Kumar"]
    assert names("without_membership=true") == ["Sonu Kumar"]
    listed = staff_api.get("/api/admin/students/?q=asha").json()["results"][0]
    assert listed["current_membership"]["seat_number"] == "1"
    assert listed["total_due"] == 0


def test_only_the_owner_sees_the_full_aadhaar(owner_api, staff_api, seats, day_plan):
    student_id = admit(staff_api, plan=day_plan, aadhaar=valid_aadhaar()).json()["student"]["id"]
    url = f"/api/admin/students/{student_id}/reveal-aadhaar/"
    assert staff_api.post(url).status_code == 403
    response = owner_api.post(url)
    assert response.status_code == 200
    number = valid_aadhaar()
    assert response.json()["aadhaar"] == f"{number[:4]}-{number[4:8]}-{number[8:]}"
    assert AuditLog.objects.filter(
        action="student.aadhaar_viewed", entity_id=str(student_id)
    ).exists()


def test_staff_cannot_delete_or_change_setup(staff_api, owner_api, seats, shifts, day_plan):
    student_id = admit(staff_api, plan=day_plan).json()["student"]["id"]
    assert staff_api.delete(f"/api/admin/students/{student_id}/").status_code == 403
    assert (
        staff_api.post(
            "/api/admin/shifts/", {"name": "X", "start_time": "07:00", "end_time": "09:00"}
        ).status_code
        == 403
    )
    assert staff_api.patch(f"/api/admin/plans/{day_plan.id}/", {"price": 1}).status_code == 403
    assert staff_api.get("/api/admin/plans/").status_code == 200
    # The owner may not delete a student who has memberships or payments either: history stays.
    assert owner_api.delete(f"/api/admin/students/{student_id}/").status_code == 409


def test_student_edits_are_audited_without_aadhaar(staff_api, day_plan):
    student_id = admit(staff_api, plan=day_plan).json()["student"]["id"]
    response = staff_api.patch(
        f"/api/admin/students/{student_id}/",
        {"father_name": "Ramesh", "aadhaar": valid_aadhaar()},
        format="json",
    )
    assert response.status_code == 200
    entry = AuditLog.objects.filter(action="student.updated").latest("at")
    assert entry.after["father_name"] == "Ramesh"
    assert "aadhaar" not in entry.after and entry.after["aadhaar_last4"] == valid_aadhaar()[-4:]


# --- memberships ------------------------------------------------------------------------


def test_renew_with_payment_and_seat_change_conflict(staff_api, seats, shifts, day_plan):
    first = admit(staff_api, seat=seats[0], plan=day_plan, pay=450).json()["membership"]
    response = staff_api.post(
        f"/api/admin/memberships/{first['id']}/renew/",
        {"payment": {"amount": 450, "mode": "CASH"}},
        format="json",
    )
    assert response.status_code == 201, response.json()
    renewal = response.json()
    assert renewal["seat_number"] == "1" and renewal["due_total"] == 0
    assert renewal["start_date"] > first["end_date"]

    other = admit(
        staff_api, name="Ravi Kumar", mobile="9876543211", seat=seats[1], plan=day_plan
    ).json()["membership"]
    moved = staff_api.patch(
        f"/api/admin/memberships/{other['id']}/", {"seat": seats[0].id}, format="json"
    )
    assert moved.status_code == 400
    assert "Seat 1 is already given to Asha Kumari" in moved.json()["seat"][0]


def test_cancel_is_for_the_owner_and_frees_the_seat(owner_api, staff_api, seats, day_plan):
    m = admit(staff_api, seat=seats[0], plan=day_plan).json()["membership"]
    assert staff_api.post(f"/api/admin/memberships/{m['id']}/cancel/").status_code == 403
    assert (
        owner_api.post(f"/api/admin/memberships/{m['id']}/cancel/", {"reason": "left"}).json()[
            "state"
        ]
        == "CANCELLED"
    )
    assert (
        admit(
            staff_api, name="Ravi Kumar", mobile="9876543211", seat=seats[0], plan=day_plan
        ).status_code
        == 201
    )


def test_membership_filters(staff_api, seats, day_plan):
    today = timezone.localdate()
    admit(staff_api, seat=seats[0], plan=day_plan, pay=450)
    admit(
        staff_api,
        name="Ravi Kumar",
        mobile="9876543211",
        seat=seats[1],
        plan=day_plan,
        start=today + timedelta(days=3),
    )
    states = {
        m["student_name"]: m["state"]
        for m in staff_api.get("/api/admin/memberships/").json()["results"]
    }
    assert states == {"Asha Kumari": "ACTIVE", "Ravi Kumar": "UPCOMING"}
    due = staff_api.get("/api/admin/memberships/?has_due=true").json()["results"]
    assert [m["student_name"] for m in due] == ["Ravi Kumar"]


# --- seat map and dashboard ------------------------------------------------------------


def test_seat_map_and_dashboard(staff_api, seats, shifts, day_plan):
    admit(staff_api, seat=seats[0], plan=day_plan, pay=450)
    admit(
        staff_api,
        name="Ravi Kumar",
        mobile="9876543211",
        seat=seats[0],
        shift=shifts["morning"],
        plan=day_plan,
    )
    admit(staff_api, name="Sonu Kumar", mobile="9876543212", plan=day_plan, pay=100)

    seat_map = staff_api.get("/api/admin/seat-map/").json()
    assert seat_map["summary"] == {"seats": 5, "occupied": 1, "free": 4}
    first = seat_map["seats"][0]
    assert first["number"] == "1" and [b["student_name"] for b in first["bookings"]] == [
        "Ravi Kumar",
        "Asha Kumari",
    ]

    library = staff_api.get("/api/admin/overview/").json()["library"]
    assert library["active_members"] == 3
    assert library["occupancy_percent"] == 20
    assert library["outstanding_dues"] == 800
    assert library["collected_today"] == 550


def test_waitlist_positions(staff_api, shifts):
    student = Student.objects.create(
        branch_id=1, roll_no=99, full_name="Waiting One", mobile="9000000099"
    )
    first = staff_api.post(
        "/api/admin/waitlist/", {"student": student.id, "preferred_shift": shifts["day"].id}
    ).json()
    second = staff_api.post("/api/admin/waitlist/", {"student": student.id}).json()
    assert (first["position"], second["position"]) == (1, 2)
    assert staff_api.delete(f"/api/admin/waitlist/{first['id']}/").status_code == 403


def test_students_cannot_reach_the_admin_api(api, student):
    api.force_login(student)
    assert api.get("/api/admin/students/").status_code == 403
    assert api.get("/api/admin/seat-map/").status_code == 403


def test_memberships_list_hides_other_branches(staff_api, seats, day_plan):
    from library.models import Branch

    admit(staff_api, seat=seats[0], plan=day_plan)
    other = Branch.objects.create(name="Second", code="second")
    assert (
        staff_api.get("/api/admin/memberships/", HTTP_X_BRANCH_ID=str(other.id)).json()["count"]
        == 0
    )
    assert Membership.objects.count() == 1


def test_existing_student_gets_a_new_membership_with_payment(staff_api, seats, shifts, day_plan):
    student = Student.objects.create(
        branch_id=1, roll_no=50, full_name="From Waitlist", mobile="9000000098"
    )
    body = {
        "student": student.id,
        "plan": day_plan.id,
        "seat": seats[3].id,
        "start_date": timezone.localdate().isoformat(),
        "payment": {"amount": 450, "mode": "CASH"},
    }
    response = staff_api.post("/api/admin/memberships/", body, format="json")
    assert response.status_code == 201, response.json()
    assert response.json()["seat_number"] == "4" and response.json()["due_total"] == 0
    clash = staff_api.post("/api/admin/memberships/", {**body, "payment": None}, format="json")
    assert clash.status_code == 400 and "Seat 4" in clash.json()["seat"][0]
