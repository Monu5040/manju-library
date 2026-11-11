"""
Numbers for the owner's analytics page, computed from the live tables on every request (a
library has hundreds of students, not millions), so they are never out of date.

A range is `start`–`end`, both days included. Figures that describe one moment (members,
occupancy, the mix) are taken on the range's last day, or today if that is earlier. Dues
and memberships expiring soon are always as of today.
"""

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from django.utils import timezone

from billing.models import Payment
from ledger.models import LedgerCategory, LedgerEntry
from library.models import MINUTES_PER_DAY, Branch, Seat, Shift
from members.filters import renewed_later
from members.models import Membership, Student
from members.services import add_months

ZERO = Decimal("0")
RENEWAL_GRACE_DAYS = 15
DAYS_PER_MONTH = 30.44
DUE_BUCKETS = [("0–7 days", 0, 7), ("8–30 days", 8, 30), ("Over 30 days", 31, None)]
GENDERS = {"F": "Female", "M": "Male", "O": "Other", "": "Not recorded"}
TRUNC = {"day": TruncDay, "month": TruncMonth, "year": TruncYear}


# --- ranges ----------------------------------------------------------------------------


def previous_range(start: date, end: date) -> tuple[date, date]:
    """The same number of days just before the range, for comparisons."""
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    return prev_end - timedelta(days=length - 1), prev_end


def moment(end: date) -> date:
    return min(end, timezone.localdate())


def pick_grain(start: date, end: date, requested: str | None = None) -> str:
    if requested in TRUNC:
        return requested
    days = (end - start).days + 1
    return "day" if days <= 62 else "month" if days <= 3 * 366 else "year"


def periods(start: date, end: date, grain: str) -> list[date]:
    """The first day of every day, month or year that the range touches."""
    if grain == "day":
        return [start + timedelta(days=n) for n in range((end - start).days + 1)]
    if grain == "year":
        return [date(y, 1, 1) for y in range(start.year, end.year + 1)]
    result, current = [], start.replace(day=1)
    while current <= end:
        result.append(current)
        current = (current + timedelta(days=32)).replace(day=1)
    return result


def period_label(day: date, grain: str) -> str:
    if grain == "day":
        return f"{day.day} {day:%b %Y}"
    return f"{day:%b %Y}" if grain == "month" else str(day.year)


# --- money -----------------------------------------------------------------------------


def money_totals(branch: Branch, start: date, end: date) -> dict:
    fees = (
        Payment.objects.filter(branch=branch, is_void=False, paid_on__range=(start, end)).aggregate(
            total=Sum("amount")
        )["total"]
        or ZERO
    )
    entries = LedgerEntry.objects.filter(
        branch=branch, is_void=False, entry_date__range=(start, end)
    )
    by_kind = dict(entries.values_list("category__kind").annotate(total=Sum("amount")))
    other = by_kind.get(LedgerCategory.Kind.INCOME) or ZERO
    expenses = by_kind.get(LedgerCategory.Kind.EXPENSE) or ZERO
    return {
        "fees": fees,
        "other_income": other,
        "income": fees + other,
        "expenses": expenses,
        "profit": fees + other - expenses,
    }


def revenue(branch: Branch, start: date, end: date, grain: str) -> list[dict]:
    trunc = TRUNC[grain]
    fees = dict(
        Payment.objects.filter(branch=branch, is_void=False, paid_on__range=(start, end))
        .annotate(period=trunc("paid_on"))
        .values_list("period")
        .annotate(total=Sum("amount"))
    )
    other: dict[tuple, Decimal] = {}
    for period, kind, total in (
        LedgerEntry.objects.filter(branch=branch, is_void=False, entry_date__range=(start, end))
        .annotate(period=trunc("entry_date"))
        .values_list("period", "category__kind")
        .annotate(total=Sum("amount"))
    ):
        other[(period, kind)] = total
    rows = []
    for period in periods(start, end, grain):
        fee = fees.get(period) or ZERO
        extra = other.get((period, LedgerCategory.Kind.INCOME)) or ZERO
        spent = other.get((period, LedgerCategory.Kind.EXPENSE)) or ZERO
        rows.append(
            {
                "period": period,
                "label": period_label(period, grain),
                "fees": fee,
                "other_income": extra,
                "income": fee + extra,
                "expenses": spent,
                "profit": fee + extra - spent,
            }
        )
    return rows


def outstanding_dues(branch: Branch) -> list[tuple[date, Decimal]]:
    """(start date, amount due) of every membership that still owes money."""
    return list(
        Membership.objects.not_cancelled()
        .filter(branch=branch)
        .with_totals()
        .filter(due_total__gt=0)
        .values_list("start_date", "due_total")
    )


def collections(branch: Branch, start: date, end: date) -> dict:
    today = timezone.localdate()
    buckets = [{"label": label, "amount": ZERO, "count": 0} for label, _, _ in DUE_BUCKETS]
    for started, due in outstanding_dues(branch):
        age = max((today - started).days, 0)
        for bucket, (_, low, high) in zip(buckets, DUE_BUCKETS, strict=True):
            if age >= low and (high is None or age <= high):
                bucket["amount"] += due
                bucket["count"] += 1
                break
    modes = [
        {
            "mode": row["mode"],
            "label": Payment.Mode(row["mode"]).label,
            "amount": row["total"],
            "count": row["count"],
        }
        for row in Payment.objects.filter(branch=branch, is_void=False, paid_on__range=(start, end))
        .values("mode")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    ]
    return {"dues_by_age": buckets, "payment_modes": modes}


# --- seats -----------------------------------------------------------------------------


def circular_overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Minutes two daily time ranges share. Ranges are [start, end) and may pass midnight."""
    total = sum(
        max(0, min(a[1], b[1] + shift) - max(a[0], b[0] + shift))
        for shift in (-MINUTES_PER_DAY, 0, MINUTES_PER_DAY)
    )
    return min(total, a[1] - a[0], b[1] - b[0])


def opening_hours(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The union of the shifts' hours as separate pieces within one day."""
    pieces = []
    for start, end in ranges:
        if end <= MINUTES_PER_DAY:
            pieces.append((start, end))
        else:
            pieces += [(start, MINUTES_PER_DAY), (0, end - MINUTES_PER_DAY)]
    merged: list[list[int]] = []
    for start, end in sorted(pieces):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def occupancy(branch: Branch, day: date) -> dict:
    """
    Every active seat in every active shift on one day: taken (booked for the whole shift),
    partly (booked for part of it, for example a custom time) or free. The percentage is
    seat-hours sold out of seat-hours open, so seats shared by shifts count fairly.
    """
    shifts = list(Shift.objects.filter(branch=branch, is_active=True))
    seats = list(Seat.objects.filter(branch=branch, is_active=True).order_by("sort_key", "number"))
    bookings: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for seat_id, start, end in (
        Membership.objects.current(day)
        .filter(branch=branch, seat__isnull=False)
        .values_list("seat_id", "start_minute", "end_minute")
    ):
        bookings[seat_id].append((start, end))

    hours = opening_hours([s.minute_range for s in shifts])
    open_minutes = sum(end - start for start, end in hours)
    stats = [{"taken": 0, "partly": 0, "free_seats": []} for _ in shifts]
    grid, sold = [], 0
    for seat in seats:
        booked = bookings.get(seat.id, [])
        cells = []
        for shift, stat in zip(shifts, stats, strict=True):
            window = shift.minute_range
            covered = sum(circular_overlap(window, b) for b in booked)
            if covered >= window[1] - window[0]:
                state = "taken"
                stat["taken"] += 1
            elif covered > 0:
                state = "partly"
                stat["partly"] += 1
            else:
                state = "free"
                stat["free_seats"].append(seat.number)
            cells.append(state)
        sold += sum(circular_overlap(piece, b) for b in booked for piece in hours)
        grid.append({"seat": seat.number, "cells": cells})

    capacity = len(seats) * open_minutes
    return {
        "date": day,
        "percent": round(100 * sold / capacity) if capacity else 0,
        "seats_total": len(seats),
        "seats_in_use": sum(1 for seat in seats if bookings.get(seat.id)),
        "shifts": [
            {
                "id": shift.id,
                "name": shift.name,
                "time_label": shift.time_label,
                "taken": stat["taken"],
                "partly": stat["partly"],
                "free": len(stat["free_seats"]),
                "free_seats": stat["free_seats"],
            }
            for shift, stat in zip(shifts, stats, strict=True)
        ],
        "grid": grid,
    }


# --- people ----------------------------------------------------------------------------


def plan_months(m: Membership) -> int | None:
    if m.plan_id:
        return m.plan.duration_months
    months = round(((m.end_date - m.start_date).days + 1) / DAYS_PER_MONTH)
    return months if months in {1, 2, 3, 6, 12} else None


def mix(branch: Branch, day: date) -> dict:
    live = list(
        Membership.objects.current(day)
        .filter(branch=branch)
        .select_related("shift", "plan", "student")
        .order_by("shift__sort_order", "start_minute")
    )
    shifts = Counter(m.shift.name if m.shift_id else "Custom time" for m in live)
    plans = Counter(plan_months(m) for m in live)
    students = {m.student_id: m.student for m in live}
    genders = Counter(GENDERS.get(s.gender, "Not recorded") for s in students.values())

    def ranked(counter: Counter) -> list[dict]:
        return [{"label": label, "count": count} for label, count in counter.most_common()]

    plan_rows = [
        {"label": f"{months} month{'s' if months > 1 else ''}" if months else "Other", "count": n}
        for months, n in sorted(plans.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
    ]
    return {
        "date": day,
        "by_shift": ranked(shifts),
        "by_plan": plan_rows,
        "by_gender": ranked(genders),
    }


def retention(branch: Branch, start: date, end: date) -> dict:
    """
    Memberships that ended in the range: renewed (another membership carries on within
    15 days), left, or still undecided (ended under 15 days ago). Plus how long the students
    who left had stayed, and how many students from each month's admissions are still here.
    """
    today = timezone.localdate()
    grace = timedelta(days=RENEWAL_GRACE_DAYS)
    last = min(end, today - timedelta(days=1))
    ended = list(
        Membership.objects.not_cancelled()
        .filter(branch=branch, end_date__range=(start, last))
        .select_related("student")
    )
    terms: dict[int, list[tuple[int, date, date]]] = defaultdict(list)
    for pk, student_id, s, e in (
        Membership.objects.not_cancelled()
        .filter(student_id__in={m.student_id for m in ended})
        .values_list("pk", "student_id", "start_date", "end_date")
    ):
        terms[student_id].append((pk, s, e))

    renewed = left = undecided = 0
    stays = []
    for m in ended:
        others = [t for t in terms[m.student_id] if t[0] != m.pk]
        if any(s <= m.end_date + grace and e > m.end_date for _, s, e in others):
            renewed += 1
        elif m.end_date + grace >= today:
            undecided += 1
        else:
            left += 1
            first = min(
                [s for _, s, _ in terms[m.student_id]] + [m.student.admission_date or m.start_date]
            )
            stays.append((m.end_date - first).days / DAYS_PER_MONTH)
    decided = renewed + left
    return {
        "ended": len(ended),
        "renewed": renewed,
        "left": left,
        "undecided": undecided,
        "renewal_rate": round(100 * renewed / decided) if decided else None,
        "average_stay_months": round(sum(stays) / len(stays), 1) if stays else None,
        "cohorts": cohorts(branch, end),
    }


def cohorts(branch: Branch, end: date) -> list[dict]:
    """Students admitted in each of the 12 months up to `end`, and how many are still members."""
    day = moment(end)
    first = add_months(end.replace(day=1), -11)
    active = Exists(Membership.objects.current(day).filter(student=OuterRef("pk")))
    counts = {
        row["month"]: row
        for row in Student.objects.filter(branch=branch, admission_date__range=(first, end))
        .annotate(month=TruncMonth("admission_date"), active=active)
        .values("month")
        .annotate(joined=Count("id"), still=Count("id", filter=Q(active=True)))
    }
    rows = []
    for month in periods(first, end, "month"):
        row = counts.get(month, {})
        joined, still = row.get("joined", 0), row.get("still", 0)
        rows.append(
            {
                "month": month,
                "label": period_label(month, "month"),
                "joined": joined,
                "still_members": still,
                "percent": round(100 * still / joined) if joined else None,
            }
        )
    return rows


# --- the page --------------------------------------------------------------------------


def key_numbers(branch: Branch, start: date, end: date, seats: dict) -> dict:
    today = timezone.localdate()
    day = moment(end)
    prev_start, prev_end = previous_range(start, end)
    now, before = money_totals(branch, start, end), money_totals(branch, prev_start, prev_end)

    def admissions(a, b):
        return Student.objects.filter(branch=branch, admission_date__range=(a, b)).count()

    expiring = (
        Membership.objects.not_cancelled()
        .filter(branch=branch, end_date__range=(today, today + timedelta(days=7)))
        .filter(~renewed_later())
        .count()
    )
    return {
        "income": {"value": now["income"], "previous": before["income"]},
        "fees": {"value": now["fees"], "previous": before["fees"]},
        "expenses": {"value": now["expenses"], "previous": before["expenses"]},
        "profit": {"value": now["profit"], "previous": before["profit"]},
        "new_admissions": {
            "value": admissions(start, end),
            "previous": admissions(prev_start, prev_end),
        },
        "active_members": {
            "value": Membership.objects.current(day)
            .filter(branch=branch)
            .values("student")
            .distinct()
            .count()
        },
        "occupancy_percent": {"value": seats["percent"]},
        "seats_in_use": {"value": seats["seats_in_use"], "of": seats["seats_total"]},
        "outstanding_dues": {"value": sum((due for _, due in outstanding_dues(branch)), ZERO)},
        "expiring_in_7_days": {"value": expiring},
    }


def report(branch: Branch, start: date, end: date, grain: str | None = None) -> dict:
    grain = pick_grain(start, end, grain)
    day = moment(end)
    seats = occupancy(branch, day)
    prev_start, prev_end = previous_range(start, end)
    return {
        "from": start,
        "to": end,
        "as_of": day,
        "previous": {"from": prev_start, "to": prev_end},
        "grain": grain,
        "kpis": key_numbers(branch, start, end, seats),
        "revenue": revenue(branch, start, end, grain),
        "occupancy": seats,
        "retention": retention(branch, start, end),
        "mix": mix(branch, day),
        "collections": collections(branch, start, end),
    }
