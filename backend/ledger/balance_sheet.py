"""
Import the old Excel "Balance Sheet": an INCOME LEDGER (Date, No. of students, Daily
Collection Amount, Remarks) and an EXPENSE LEDGER (Date, Details, Amount, Remarks) that sit
side by side on one sheet.

- Each day's collection becomes past income. Excel kept only every student's latest
  payment, so part of a day may already be in the app as imported payments; only the part
  not yet recorded is added, so nothing is counted twice.
- Days and expense lines imported before are skipped, so importing a newer copy of the
  workbook adds only what is new.
- Like the student import: check first (nothing saved), then import, undo within 7 days.
"""

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from billing.models import Payment
from imports.parsing import CellError, blank, parse_date, parse_int, parse_money, parse_text
from imports.reader import Table, read_table
from library.models import Branch

from .models import LedgerCategory, LedgerEntry, LedgerImport

UNDO_DAYS = 7
HEADER_SCAN_ROWS = 25

COUNT_HEADERS = ("no. of students", "no of students", "students", "receipts", "count")
AMOUNT_HEADERS = ("daily collection amount", "collection amount", "collection", "amount")
DETAIL_HEADERS = ("details", "detail", "particulars", "purpose", "description", "item", "paid to")
REMARK_HEADERS = ("remarks", "remark", "notes", "note")

EXPENSE_KEYWORDS = [
    ("rent", ("rent", "kiraya")),
    ("electricity", ("electric", "bijli", "light bill", "power bill")),
    ("internet", ("wifi", "wi-fi", "internet", "broadband")),
    ("salaries", ("salary", "salaries", "wages")),
    ("cleaning", ("clean", "safai", "sweeper")),
    ("repairs", ("repair", "maintenance", "plumber", "electrician", "carpenter")),
    ("water", ("water", "pani")),
    ("newspapers", ("newspaper", "news paper", "magazine", "akhbar")),
    ("stationery", ("stationery", "printing", "xerox", "photocopy")),
]


def _header(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower().rstrip(":").strip()


def _find(headers: dict[int, str], names: tuple[str, ...]) -> int | None:
    for name in names:
        for col, text in headers.items():
            if text == name:
                return col
    for name in names:
        for col, text in headers.items():
            if name in text:
                return col
    return None


@dataclass
class Block:
    kind: str
    date_col: int
    amount_col: int
    count_col: int | None = None
    details_col: int | None = None
    remarks_col: int | None = None


@dataclass
class Layout:
    header_row: int
    blocks: list[Block] = field(default_factory=list)


def find_layout(rows: list[list]) -> Layout | None:
    """The header row and the income/expense tables in it, or None if this is not one."""
    for index, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        headers = {col: _header(v) for col, v in enumerate(row) if not blank(v)}
        date_cols = [col for col, text in headers.items() if text == "date"]
        if not date_cols:
            continue
        blocks = []
        for n, start in enumerate(date_cols):
            end = date_cols[n + 1] if n + 1 < len(date_cols) else len(row)
            own = {c: t for c, t in headers.items() if start < c < end}
            amount = _find(own, AMOUNT_HEADERS)
            if amount is None:
                continue
            titles = " ".join(
                _header(r[c]) for r in rows[:index] for c in range(start, min(end, len(r)))
            )
            count, details = _find(own, COUNT_HEADERS), _find(own, DETAIL_HEADERS)
            if "expense" in titles:
                kind = LedgerCategory.Kind.EXPENSE
            elif "income" in titles or "collection" in headers.get(amount, ""):
                kind = LedgerCategory.Kind.INCOME
            elif details is not None:
                kind = LedgerCategory.Kind.EXPENSE
            elif count is not None or not blocks:
                kind = LedgerCategory.Kind.INCOME
            else:
                kind = LedgerCategory.Kind.EXPENSE
            blocks.append(
                Block(
                    kind=kind,
                    date_col=start,
                    amount_col=amount,
                    count_col=count,
                    details_col=details,
                    remarks_col=_find(own, REMARK_HEADERS),
                )
            )
        if blocks:
            return Layout(header_row=index, blocks=blocks)
    return None


def read_balance_sheet(content: bytes) -> tuple[Table, Layout]:
    """Open the file on its Balance Sheet (by name, or the first sheet that looks like one)."""
    table = read_table(content)
    by_name = [s for s in table.sheets if "balance" in s.lower()]
    candidates = by_name + [s for s in table.sheets if s not in by_name]
    for name in candidates:
        sheet = table if name == table.sheet else read_table(content, name)
        layout = find_layout(sheet.rows)
        if layout:
            return sheet, layout
    raise ValidationError(
        {
            "file": "No Balance Sheet found. The sheet needs a header row with Date and "
            "Daily Collection Amount (income) or Date, Details and Amount (expenses)."
        }
    )


def _cell(row: list, col: int | None):
    return row[col] if col is not None and col < len(row) else None


def parse_items(table: Table, layout: Layout) -> tuple[list[dict], list[dict]]:
    """Every filled line of both ledgers, plus the lines that could not be read."""
    items, errors = [], []
    for index in range(layout.header_row + 1, len(table.rows)):
        row = table.rows[index]
        for block in layout.blocks:
            side = "Income" if block.kind == LedgerCategory.Kind.INCOME else "Expense"
            raw_amount = _cell(row, block.amount_col)
            text_cols = (block.count_col, block.details_col, block.remarks_col)
            if blank(raw_amount) and all(blank(_cell(row, c)) for c in text_cols):
                continue  # an empty day: only the date is filled in
            try:
                day = parse_date(_cell(row, block.date_col), "Date")
                amount = parse_money(raw_amount, "Amount")
                students = parse_int(_cell(row, block.count_col), "No. of students")
            except CellError as exc:
                errors.append({"row": index + 1, "side": side, "message": str(exc)})
                continue
            if day is None:
                errors.append({"row": index + 1, "side": side, "message": "The date is empty."})
                continue
            if not amount or amount <= 0:
                continue
            items.append(
                {
                    "row": index + 1,
                    "kind": block.kind,
                    "day": day.isoformat(),
                    "amount": str(amount),
                    "students": students or 0,
                    "details": parse_text(_cell(row, block.details_col))[:150],
                    "remarks": parse_text(_cell(row, block.remarks_col))[:150],
                }
            )
    return items, errors


def guess_category(details: str) -> str:
    text = details.lower()
    for code, words in EXPENSE_KEYWORDS:
        if any(word in text for word in words):
            return code
    return "other-expense"


def plan(branch: Branch, items: list[dict]) -> dict:
    """What importing would do now: checked again at import time, as data may have changed."""
    by_day: dict[str, dict] = defaultdict(
        lambda: {"amount": Decimal("0"), "students": 0, "rows": [], "remarks": []}
    )
    expenses = []
    for item in items:
        if item["kind"] == LedgerCategory.Kind.INCOME:
            day = by_day[item["day"]]
            day["amount"] += Decimal(item["amount"])
            day["students"] += item["students"]
            day["rows"].append(item["row"])
            if item["remarks"]:
                day["remarks"].append(item["remarks"])
        else:
            expenses.append(item)

    imported_days = set(
        LedgerEntry.objects.filter(
            branch=branch,
            source=LedgerEntry.Source.BALANCE_SHEET,
            category__code="past-fees",
            is_void=False,
        ).values_list("entry_date", flat=True)
    )
    days = [date.fromisoformat(d) for d in by_day]
    payments = {
        row["paid_on"]: row["total"]
        for row in Payment.objects.filter(branch=branch, is_void=False, paid_on__in=days)
        .values("paid_on")
        .annotate(total=Sum("amount"))
    }

    income = []
    for iso in sorted(by_day):
        day, values = date.fromisoformat(iso), by_day[iso]
        recorded = payments.get(day, Decimal("0"))
        to_add = max(values["amount"] - recorded, Decimal("0"))
        if day in imported_days:
            status, to_add = "already", Decimal("0")
        elif to_add > 0:
            status = "add"
        else:
            status = "covered"
        income.append(
            {
                "day": iso,
                "rows": values["rows"],
                "students": values["students"],
                "sheet_amount": str(values["amount"]),
                "recorded": str(recorded),
                "to_add": str(to_add),
                "remarks": "; ".join(values["remarks"])[:150],
                "status": status,
            }
        )

    existing = set(
        LedgerEntry.objects.filter(
            branch=branch, source=LedgerEntry.Source.BALANCE_SHEET, is_void=False
        )
        .exclude(category__code="past-fees")
        .values_list("entry_date", "amount", "details")
    )
    categories = dict(LedgerCategory.objects.filter(code__isnull=False).values_list("code", "name"))
    expense_plan = []
    for item in expenses:
        details = item["details"] or item["remarks"] or "Expense from the old Balance Sheet"
        key = (date.fromisoformat(item["day"]), Decimal(item["amount"]), details[:200])
        code = guess_category(f"{item['details']} {item['remarks']}")
        expense_plan.append(
            {
                **item,
                "details": details,
                "category": code,
                "category_name": categories.get(code, code),
                "status": "already" if key in existing else "add",
            }
        )

    to_add = [d for d in income if d["status"] == "add"]
    new_expenses = [e for e in expense_plan if e["status"] == "add"]
    summary = {
        "first_day": min(by_day) if by_day else None,
        "last_day": max(by_day) if by_day else None,
        "income_days": len(income),
        "sheet_income": str(sum((Decimal(d["sheet_amount"]) for d in income), Decimal("0"))),
        "days_to_add": len(to_add),
        "income_to_add": str(sum((Decimal(d["to_add"]) for d in to_add), Decimal("0"))),
        "days_covered": sum(1 for d in income if d["status"] == "covered"),
        "days_already": sum(1 for d in income if d["status"] == "already"),
        "expense_lines": len(expense_plan),
        "expenses_to_add": len(new_expenses),
        "expense_total_to_add": str(
            sum((Decimal(e["amount"]) for e in new_expenses), Decimal("0"))
        ),
        "expenses_already": len(expense_plan) - len(new_expenses),
    }
    return {"income": income, "expenses": expense_plan, "summary": summary}


def check(*, branch: Branch, file_name: str, content: bytes, by) -> LedgerImport:
    table, layout = read_balance_sheet(content)
    items, errors = parse_items(table, layout)
    result = plan(branch, items)
    return LedgerImport.objects.create(
        branch=branch,
        file_name=file_name[:255],
        file_hash=hashlib.sha256(content).hexdigest(),
        sheet=table.sheet,
        plan={"items": items, "errors": errors, **result},
        summary={**result["summary"], "errors": len(errors)},
        created_by=by,
    )


@transaction.atomic
def commit(job: LedgerImport, *, by) -> LedgerImport:
    job = LedgerImport.objects.select_for_update().get(pk=job.pk)
    if job.status != LedgerImport.Status.CHECKED:
        raise ValidationError({"detail": "This file has already been imported or undone."})
    result = plan(job.branch, job.plan.get("items", []))
    categories = {c.code: c for c in LedgerCategory.objects.filter(code__isnull=False)}
    created = 0
    for day in result["income"]:
        if day["status"] != "add":
            continue
        recorded = Decimal(day["recorded"])
        note = f"{day['students']} students" if day["students"] else "Daily collection"
        note += f", ₹{Decimal(day['sheet_amount']):,.0f} in the old Balance Sheet"
        if recorded:
            note += f" (₹{recorded:,.0f} already recorded as payments)"
        if day["remarks"]:
            note += f". {day['remarks']}"
        LedgerEntry.objects.create(
            branch=job.branch,
            category=categories["past-fees"],
            entry_date=date.fromisoformat(day["day"]),
            amount=Decimal(day["to_add"]),
            mode=Payment.Mode.OTHER,
            details=note[:200],
            source=LedgerEntry.Source.BALANCE_SHEET,
            import_batch=job,
            created_by=by,
        )
        created += 1
    for line in result["expenses"]:
        if line["status"] != "add":
            continue
        LedgerEntry.objects.create(
            branch=job.branch,
            category=categories.get(line["category"]) or categories["other-expense"],
            entry_date=date.fromisoformat(line["day"]),
            amount=Decimal(line["amount"]),
            mode=Payment.Mode.OTHER,
            details=line["details"][:200],
            reference=(line["remarks"] if line["remarks"] != line["details"] else "")[:80],
            source=LedgerEntry.Source.BALANCE_SHEET,
            import_batch=job,
            created_by=by,
        )
        created += 1
    job.plan = {**job.plan, "income": result["income"], "expenses": result["expenses"]}
    job.summary = {**job.summary, **result["summary"], "created": created}
    job.status = LedgerImport.Status.IMPORTED
    job.imported_at = timezone.now()
    job.save()
    return job


@transaction.atomic
def undo(job: LedgerImport, *, by) -> LedgerImport:
    job = LedgerImport.objects.select_for_update().get(pk=job.pk)
    if job.status != LedgerImport.Status.IMPORTED:
        raise ValidationError({"detail": "Only an imported file can be undone."})
    if timezone.now() - job.imported_at > timedelta(days=UNDO_DAYS):
        raise ValidationError({"detail": f"Imports can be undone for {UNDO_DAYS} days only."})
    entries = list(job.entries.all())
    changed = [e for e in entries if e.is_void or e.updated_at > job.imported_at]
    if changed:
        raise ValidationError(
            {"detail": f"{len(changed)} imported entries were changed since. Fix them by hand."}
        )
    LedgerEntry.objects.filter(pk__in=[e.pk for e in entries]).delete()
    job.status = LedgerImport.Status.UNDONE
    job.undone_at = timezone.now()
    job.summary = {**job.summary, "removed": len(entries)}
    job.save()
    return job
