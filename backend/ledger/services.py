"""Ledger arithmetic: the day-by-day ledger, cash movements and the daily cash closing."""

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from billing.models import Payment
from library.models import Branch

from .models import CashClosing, LedgerCategory, LedgerEntry

ZERO = Decimal("0")
MAX_LEDGER_DAYS = 366


def parse_range(params, *, default_days: int | None = None) -> tuple[date, date]:
    """`from` and `to` query parameters (YYYY-MM-DD); defaults to this month so far."""
    today = timezone.localdate()
    try:
        start = date.fromisoformat(params.get("from")) if params.get("from") else None
        end = date.fromisoformat(params.get("to")) if params.get("to") else None
    except ValueError as exc:
        raise ValidationError({"from": "Use dates in the format YYYY-MM-DD."}) from exc
    end = end or today
    if start is None:
        start = end - timedelta(days=default_days - 1) if default_days else end.replace(day=1)
    if start > end:
        raise ValidationError({"from": "The start date is after the end date."})
    return start, end


def void_entry(entry: LedgerEntry, *, reason: str, by) -> LedgerEntry:
    if entry.is_void:
        raise ValidationError({"detail": "This entry is already void."})
    entry.is_void = True
    entry.void_reason = reason
    entry.voided_at = timezone.now()
    entry.voided_by = by
    entry.save(update_fields=["is_void", "void_reason", "voided_at", "voided_by", "updated_at"])
    return entry


# --- day by day -----------------------------------------------------------------------


def daily_ledger(branch: Branch, start: date, end: date) -> dict:
    """Every day in the range: fees, other income, expenses and the balance, with totals."""
    if (end - start).days + 1 > MAX_LEDGER_DAYS:
        raise ValidationError({"from": f"Pick at most {MAX_LEDGER_DAYS} days."})
    fees = {
        row["paid_on"]: row
        for row in Payment.objects.filter(branch=branch, is_void=False, paid_on__range=(start, end))
        .values("paid_on")
        .annotate(total=Sum("amount"), students=Count("student", distinct=True))
    }
    other = {}
    for row in (
        LedgerEntry.objects.filter(branch=branch, is_void=False, entry_date__range=(start, end))
        .values("entry_date", "category__kind")
        .annotate(total=Sum("amount"))
    ):
        other[(row["entry_date"], row["category__kind"])] = row["total"]

    rows = []
    totals = {"students": 0, "fees": ZERO, "other_income": ZERO, "expenses": ZERO}
    day = start
    while day <= end:
        fee = fees.get(day, {})
        row = {
            "day": day,
            "students": fee.get("students", 0),
            "fees": fee.get("total") or ZERO,
            "other_income": other.get((day, LedgerCategory.Kind.INCOME), ZERO),
            "expenses": other.get((day, LedgerCategory.Kind.EXPENSE), ZERO),
        }
        row["income"] = row["fees"] + row["other_income"]
        row["balance"] = row["income"] - row["expenses"]
        for key in totals:
            totals[key] += row[key]
        rows.append(row)
        day += timedelta(days=1)
    totals["income"] = totals["fees"] + totals["other_income"]
    totals["balance"] = totals["income"] - totals["expenses"]
    return {"from": start, "to": end, "days": rows, "totals": totals}


# --- cash -----------------------------------------------------------------------------


def cash_movements(branch: Branch, start: date, end: date) -> dict:
    """Cash that came in and went out of the drawer between two days (both included)."""
    fees = Payment.objects.filter(
        branch=branch, is_void=False, mode=Payment.Mode.CASH, paid_on__range=(start, end)
    ).aggregate(total=Sum("amount"), count=Count("id"))
    entries = LedgerEntry.objects.filter(
        branch=branch, is_void=False, mode=Payment.Mode.CASH, entry_date__range=(start, end)
    )
    income = entries.filter(category__kind=LedgerCategory.Kind.INCOME).aggregate(
        total=Sum("amount"), count=Count("id")
    )
    spent = entries.filter(category__kind=LedgerCategory.Kind.EXPENSE).aggregate(
        total=Sum("amount"), count=Count("id")
    )
    result = {
        "fees": fees["total"] or ZERO,
        "fee_count": fees["count"],
        "other_income": income["total"] or ZERO,
        "other_income_count": income["count"],
        "expenses": spent["total"] or ZERO,
        "expense_count": spent["count"],
    }
    result["cash_in"] = result["fees"] + result["other_income"]
    result["cash_out"] = result["expenses"]
    return result


def closing_preview(branch: Branch, day: date) -> dict:
    """What closing this day would record, and whether it can be closed now."""
    today = timezone.localdate()
    existing = CashClosing.objects.filter(branch=branch, day=day).first()
    previous = CashClosing.objects.filter(branch=branch, day__lt=day).order_by("-day").first()
    later = CashClosing.objects.filter(branch=branch, day__gt=day).exists()
    period_start = previous.day + timedelta(days=1) if previous else day
    moves = cash_movements(branch, period_start, day)
    opening = previous.counted if previous else None

    blocked = ""
    if existing:
        blocked = "This day is already closed."
    elif day > today:
        blocked = "A day can only be closed once it has started."
    elif later:
        blocked = "A later day is already closed. Days are closed in order."
    return {
        "day": day,
        "period_start": period_start,
        "previous_day": previous.day if previous else None,
        "opening": opening,
        **moves,
        "expected": (opening or ZERO) + moves["cash_in"] - moves["cash_out"],
        "can_close": not blocked,
        "blocked_reason": blocked,
        "closing": existing,
    }


@transaction.atomic
def close_day(
    *,
    branch: Branch,
    day: date,
    counted: Decimal,
    removed: Decimal = ZERO,
    note: str = "",
    opening: Decimal | None = None,
    by,
) -> CashClosing:
    # One closing at a time per branch, so two people cannot close overlapping periods.
    Branch.objects.select_for_update().get(pk=branch.pk)
    preview = closing_preview(branch, day)
    if not preview["can_close"]:
        raise ValidationError({"day": preview["blocked_reason"]})
    if preview["opening"] is not None:
        opening = preview["opening"]
    elif opening is None:
        raise ValidationError(
            {"opening": "This is the first closing: enter the cash the drawer started with."}
        )
    expected = opening + preview["cash_in"] - preview["cash_out"] - removed
    return CashClosing.objects.create(
        branch=branch,
        day=day,
        period_start=preview["period_start"],
        opening=opening,
        cash_in=preview["cash_in"],
        cash_out=preview["cash_out"],
        removed=removed,
        expected=expected,
        counted=counted,
        note=note,
        closed_by=by,
    )
