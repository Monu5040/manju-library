import csv
import io
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from openpyxl import load_workbook

from analytics.services import (
    circular_overlap,
    opening_hours,
    periods,
    pick_grain,
    previous_range,
)
from audit.models import AuditLog
from billing.services import record_payment
from ledger.models import LedgerCategory, LedgerEntry
from members.models import Membership
from members.services import create_student, save_membership

pytestmark = pytest.mark.django_db

URL = "/api/admin/analytics/"


def today() -> date:
    return timezone.localdate()


def days_ago(n: int) -> date:
    return today() - timedelta(days=n)


def member(student, *, start, end, shift=None, seat=None, custom=None, plan=None, price=450):
    m = Membership(
        branch=student.branch,
        student=student,
        shift=shift,
        seat=seat,
        plan=plan,
        start_date=start,
        end_date=end,
        price=Decimal(price),
    )
    if custom:
        m.custom_start_time, m.custom_end_time = custom
    return save_membership(m)


def student(branch, name, mobile, **fields):
    return create_student(branch=branch, full_name=name, mobile=mobile, **fields)


def entry(branch, code, amount, day=None):
    return LedgerEntry.objects.create(
        branch=branch,
        category=LedgerCategory.objects.get(code=code),
        amount=Decimal(amount),
        entry_date=day or today(),
    )


def test_only_the_super_admin_sees_analytics(owner_api, staff_api):
    assert staff_api.get(URL).status_code == 403
    assert staff_api.get(f"{URL}export/?section=kpis").status_code == 403
    data = owner_api.get(URL).json()
    assert data["to"] == today().isoformat() and data["from"] == today().replace(day=1).isoformat()


def test_time_helpers():
    night, after_midnight = (1365, 1800), (0, 120)  # 10:45 PM – 6 AM, and 12 – 2 AM
    assert circular_overlap(night, after_midnight) == 120
    assert circular_overlap(night, (1380, 1500)) == 120  # 11 PM – 1 AM
    assert circular_overlap((360, 600), (615, 1110)) == 0
    shifts = [(360, 600), (615, 1110), (1125, 1365), (1365, 1800)]
    assert opening_hours(shifts) == [(0, 600), (615, 1110), (1125, 1440)]
    assert previous_range(date(2026, 11, 1), date(2026, 11, 30)) == (
        date(2026, 10, 2),
        date(2026, 10, 31),
    )
    assert pick_grain(date(2026, 1, 1), date(2026, 2, 28)) == "day"
    assert pick_grain(date(2025, 4, 1), date(2026, 3, 31)) == "month"
    assert periods(date(2026, 1, 15), date(2026, 3, 2), "month") == [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
    ]


def test_key_numbers_compare_with_the_previous_period(owner_api, branch):
    asha = student(branch, "Asha Kumari", "9876543210", admission_date=today())
    student(branch, "Ravi Kumar", "9876500001", admission_date=days_ago(12))
    record_payment(student=asha, amount=Decimal("500"))
    record_payment(student=asha, amount=Decimal("300"), paid_on=days_ago(12))
    entry(branch, "rent", "200")
    entry(branch, "other-income", "100")

    data = owner_api.get(f"{URL}?from={days_ago(9)}&to={today()}").json()
    assert data["previous"] == {"from": days_ago(19).isoformat(), "to": days_ago(10).isoformat()}
    k = data["kpis"]
    assert k["income"] == {"value": 600, "previous": 300}
    assert (k["expenses"]["value"], k["profit"]["value"], k["profit"]["previous"]) == (
        200,
        400,
        300,
    )
    assert k["new_admissions"] == {"value": 1, "previous": 1}
    assert data["grain"] == "day" and len(data["revenue"]) == 10
    assert data["revenue"][0]["income"] == 0  # quiet days are filled in
    last = data["revenue"][-1]
    assert (last["fees"], last["other_income"], last["expenses"], last["profit"]) == (
        500,
        100,
        200,
        400,
    )


def test_occupancy_grid_counts_partial_and_overnight_bookings(owner_api, branch, shifts, seats):
    start, end = days_ago(5), today() + timedelta(days=20)
    member(
        student(branch, "A", "9876500011"), start=start, end=end, shift=shifts["day"], seat=seats[0]
    )
    member(
        student(branch, "B", "9876500012"),
        start=start,
        end=end,
        custom=(time(10, 15), time(14, 0)),
        seat=seats[1],
    )
    member(
        student(branch, "C", "9876500013"),
        start=start,
        end=end,
        shift=shifts["night"],
        seat=seats[2],
    )

    occ = owner_api.get(URL).json()["occupancy"]
    by_name = {s["name"]: s for s in occ["shifts"]}
    assert [s["name"] for s in occ["shifts"]] == ["Morning", "Day", "Evening", "Night"]
    assert (by_name["Day"]["taken"], by_name["Day"]["partly"], by_name["Day"]["free"]) == (1, 1, 3)
    assert by_name["Day"]["free_seats"] == ["3", "4", "5"]
    assert by_name["Night"]["taken"] == 1 and by_name["Morning"]["free"] == 5
    assert occ["grid"][1] == {"seat": "2", "cells": ["free", "partly", "free", "free"]}
    assert (occ["seats_in_use"], occ["seats_total"]) == (3, 5)
    # Seat-hours sold: 495 + 225 + 435 minutes of 5 seats × 1,410 open minutes.
    assert occ["percent"] == 16


def test_retention_sorts_ended_memberships(owner_api, branch, shifts):
    day = shifts["day"]
    a = student(branch, "Renewed", "9876500021")
    member(a, start=days_ago(70), end=days_ago(40), shift=day)
    member(a, start=days_ago(39), end=today() + timedelta(days=20), shift=day)
    b = student(branch, "Left", "9876500022", admission_date=days_ago(120))
    member(b, start=days_ago(60), end=days_ago(30), shift=day)
    c = student(branch, "Undecided", "9876500023")
    member(c, start=days_ago(35), end=days_ago(5), shift=day)

    r = owner_api.get(f"{URL}?from={days_ago(89)}&to={today()}").json()["retention"]
    assert (r["ended"], r["renewed"], r["left"], r["undecided"]) == (3, 1, 1, 1)
    assert r["renewal_rate"] == 50
    assert r["average_stay_months"] == 3.0  # admitted 120 days ago, left 30 days ago
    assert len(r["cohorts"]) == 12
    joined = {row["label"]: row for row in r["cohorts"]}
    assert joined[f"{days_ago(120):%b %Y}"]["joined"] >= 1


def test_mix_and_collections(owner_api, branch, shifts, day_plan):
    asha = student(branch, "Asha Kumari", "9876543210", gender="F")
    ravi = student(branch, "Ravi Kumar", "9876500001", gender="M")
    m = member(
        asha,
        start=days_ago(10),
        end=days_ago(10) + timedelta(days=29),
        plan=day_plan,
        shift=shifts["day"],
    )
    member(
        ravi,
        start=days_ago(2),
        end=days_ago(2) + timedelta(days=89),
        custom=(time(7, 0), time(9, 0)),
    )
    record_payment(student=asha, membership=m, amount=Decimal("300"))

    data = owner_api.get(URL).json()
    mix = data["mix"]
    assert mix["by_shift"] == [{"label": "Day", "count": 1}, {"label": "Custom time", "count": 1}]
    assert mix["by_plan"] == [{"label": "1 month", "count": 1}, {"label": "3 months", "count": 1}]
    assert {row["label"] for row in mix["by_gender"]} == {"Female", "Male"}
    dues = {row["label"]: row for row in data["collections"]["dues_by_age"]}
    assert dues["8–30 days"] == {"label": "8–30 days", "amount": 150, "count": 1}
    assert dues["0–7 days"]["amount"] == 450  # Ravi has not paid yet
    assert data["collections"]["payment_modes"] == [
        {"mode": "CASH", "label": "Cash", "amount": 300, "count": 1}
    ]
    assert data["kpis"]["outstanding_dues"]["value"] == 600


def test_every_table_exports(owner_api, branch, shifts, seats):
    record_payment(student=student(branch, "Asha Kumari", "9876543210"), amount=Decimal("450"))
    response = owner_api.get(f"{URL}export/?section=kpis&file_type=csv")
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][:2] == ["Measure", "This period"]
    assert rows[1][:2] == ["Income (fees and other income)", "450"]

    response = owner_api.get(f"{URL}export/?section=all")
    book = load_workbook(io.BytesIO(response.content))
    assert book.sheetnames == [
        "Key numbers",
        "Income and expenses",
        "Occupancy",
        "Free slots",
        "Renewals",
        "Cohorts",
        "Member mix",
        "Dues by age",
        "Payment modes",
    ]
    assert [c.value for c in book["Occupancy"][1]][:2] == ["Seat", "Morning (6:00 AM – 10:00 AM)"]
    assert owner_api.get(f"{URL}export/?section=all&file_type=csv").status_code == 400
    assert owner_api.get(f"{URL}export/?section=nope").status_code == 400
    assert AuditLog.objects.filter(action="export.analytics").count() == 2


def test_ranges_are_checked(owner_api):
    assert owner_api.get(f"{URL}?from=2026-02-01&to=2026-01-01").status_code == 400
    assert owner_api.get(f"{URL}?from=2024-01-01&to=2026-01-01&grain=day").status_code == 400
    assert owner_api.get(f"{URL}?from=2025-04-01&to=2026-03-31").json()["grain"] == "month"
    assert LedgerCategory.objects.filter(code="past-fees").exists()
