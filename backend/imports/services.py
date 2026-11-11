"""
Student import: check every row (dry run, nothing saved), import in one transaction, undo.

One row of the Admission Sheet becomes a student, and when the row has dates and a shift,
a membership (seat optional), a payment for the amount paid, and a waiting-list entry for
seats like "W7".
"""

import hashlib
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from billing.models import Payment
from billing.services import record_payment
from library.models import Branch, Seat, Shift, format_minutes, minute_range, ranges_overlap
from members.models import Membership, Student, WaitlistEntry
from members.services import (
    create_student,
    default_end_date,
    describe_conflict,
    save_membership,
    seat_conflicts,
)

from . import parsing as p
from .columns import auto_mapping, describe_columns, detect_header_row
from .models import ImportJob, ImportRow
from .reader import Table, display, read_table

UNDO_WINDOW = timedelta(days=7)
PLAN_MONTHS = {1, 2, 3, 6, 12}


def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def default_options() -> dict:
    return {"create_missing": True, "day_first": True}


def setup_job(*, branch: Branch, file_name: str, content: bytes, by) -> tuple[ImportJob, Table]:
    table = read_table(content)
    header_row = detect_header_row(table.rows)
    header = table.rows[header_row] if table.rows else []
    job = ImportJob.objects.create(
        branch=branch,
        file_name=file_name[:255],
        file_hash=file_hash(content),
        file_format=table.file_format,
        content=content,
        sheet=table.sheet,
        header_row=header_row,
        mapping=auto_mapping(header),
        options=default_options(),
        created_by=by,
    )
    return job, table


def job_table(job: ImportJob) -> Table:
    return read_table(bytes(job.content), job.sheet or None)


def columns_for(job: ImportJob, table: Table) -> list[dict]:
    header = table.rows[job.header_row] if len(table.rows) > job.header_row else []
    return describe_columns(header, job.mapping)


# ---------------------------------------------------------------------------
# Checking (dry run)
# ---------------------------------------------------------------------------


@dataclass
class RowPlan:
    row_number: int
    raw: dict
    values: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _iso(value):
    return value.isoformat() if isinstance(value, (date, time)) else value


def _shift_label(start: time, end: time) -> str:
    s, e = minute_range(start, end)
    return f"{format_minutes(s)} – {format_minutes(e)}"


def plan_rows(job: ImportJob, table: Table) -> list[RowPlan]:
    branch = job.branch
    options = {**default_options(), **job.options}
    day_first = options["day_first"]
    mapping = job.mapping
    header = table.rows[job.header_row] if len(table.rows) > job.header_row else []
    headers = [display(h) or f"Column {i + 1}" for i, h in enumerate(header)]

    taken_rolls = set(Student.objects.filter(branch=branch).values_list("roll_no", flat=True))
    taken_receipts = set(Payment.objects.filter(branch=branch).values_list("receipt_no", flat=True))
    seats = {s.number: s for s in Seat.objects.filter(branch=branch)}
    shifts = list(Shift.objects.filter(branch=branch))
    file_rolls: dict[int, int] = {}
    file_receipts: set[int] = set()
    file_bookings: dict[str, list[tuple]] = {}

    plans: list[RowPlan] = []
    for offset, row in enumerate(table.rows[job.header_row + 1 :]):
        row_number = job.header_row + 2 + offset

        def cell(key, row=row):
            index = mapping.get(key)
            return row[index] if index is not None and index < len(row) else None

        if all(p.blank(v) for v in row):
            continue
        plan = RowPlan(
            row_number, {h: display(v) for h, v in zip(headers, row, strict=False) if display(v)}
        )
        v, err, warn = plan.values, plan.errors, plan.warnings

        def take(fn, *args, plan=plan):
            try:
                return fn(*args)
            except p.CellError as exc:
                plan.errors.append(str(exc))
                return None

        v["full_name"] = p.parse_text(cell("full_name"))
        if not v["full_name"]:
            # Rows with no name are leftovers (for example formula rows) unless they hold data.
            if all(p.blank(cell(k)) for k in ("mobile", "roll_no", "seat")):
                continue
            err.append("The name is empty.")

        roll = take(p.parse_int, cell("roll_no"), "Roll no.")
        if roll is not None:
            if roll in taken_rolls:
                err.append(f"Roll no. {roll} already belongs to a student in the app.")
            elif roll in file_rolls:
                err.append(
                    f"Roll no. {roll} is used twice in this file (also row {file_rolls[roll]})."
                )
            else:
                file_rolls[roll] = row_number
        v["roll_no"] = roll

        if p.blank(cell("mobile")):
            err.append("The mobile number is empty.")
        else:
            v["mobile"] = take(p.parse_mobile, cell("mobile"))

        aadhaar, aadhaar_warning = p.parse_aadhaar(cell("aadhaar"))
        v["aadhaar"] = aadhaar
        if aadhaar_warning:
            warn.append(aadhaar_warning)

        v["gender"] = p.parse_gender(cell("gender"))
        v["father_name"] = p.parse_text(cell("father_name"))
        v["notes"] = p.parse_text(cell("notes"))
        admission = take(p.parse_date, cell("admission_date"), "Admission date", day_first)
        start = (
            take(p.parse_date, cell("start_date"), "Start (renewed) date", day_first) or admission
        )
        end = take(p.parse_date, cell("end_date"), "Expiry date", day_first)
        months = take(p.parse_int, cell("plan_months"), "Plan")
        if months is not None and months not in PLAN_MONTHS:
            warn.append(
                f"Plan '{months}' is not 1, 2, 3, 6 or 12 months; the expiry date is used instead."
            )
            months = None
        if end is None and start and months:
            end = default_end_date(start, months)
        if admission is None and start:
            warn.append("No admission date; the start date is used.")
            admission = start
        v["admission_date"] = _iso(admission)

        # Time slot: a shift ("10:15 AM - 06:30 PM" or a shift's name) or a custom time.
        shift_text = p.parse_text(cell("shift"))
        shift_times = take(p.parse_time_range, cell("shift"))
        custom_text = p.parse_text(cell("custom_shift"))
        try:
            custom_times = p.parse_time_range(cell("custom_shift"))
            if custom_text and custom_times is None:
                err.append(
                    f"Extra time '{custom_text}' is not a time range like 08:00 AM - 02:00 PM."
                )
        except p.CellError as exc:
            custom_times = None
            err.append(str(exc))
        shift = None
        if shift_times:
            shift = next((s for s in shifts if (s.start_time, s.end_time) == shift_times), None)
            if shift is None and not options["create_missing"]:
                err.append(
                    f"No shift runs {_shift_label(*shift_times)}. "
                    "Add it under Settings or allow new shifts."
                )
        elif shift_text:
            shift = next((s for s in shifts if s.name.lower() == shift_text.lower()), None)
            if shift is None:
                err.append(
                    f"Shift '{shift_text}' is not a time range and no shift has that name. "
                    "Add it under Settings first."
                )
        if shift is not None:
            v["shift_id"] = shift.id
            minutes = shift.minute_range
        elif shift_times:
            v["shift_times"] = [_iso(t) for t in shift_times]
            minutes = minute_range(*shift_times)
        else:
            minutes = None
        if custom_times and not shift_times and shift is None:
            v["custom_times"] = [_iso(t) for t in custom_times]
            minutes = minute_range(*custom_times)
        elif custom_times:
            # A second daily slot (for example morning + evening). A membership has one slot,
            # so the second is kept in its notes instead of being lost.
            extra = _shift_label(*custom_times)
            v["extra_slot_note"] = f"Also studies {extra} (Additional Shift in the old sheet)."
            warn.append(f"Has a second time slot ({extra}); it is kept in the membership notes.")

        seat = take(p.parse_seat, cell("seat"))
        price = take(p.parse_money, cell("price"), "Fee")
        paid = take(p.parse_money, cell("paid"), "Amount paid")

        has_membership = bool(start and end and minutes)
        if start and end and end < start:
            err.append("The expiry date is before the start date.")
            has_membership = False
        if has_membership:
            if price is None:
                warn.append("No fee given; the membership is recorded with a ₹0 fee.")
                price = Decimal("0")
            v["membership"] = {"start": _iso(start), "end": _iso(end), "price": str(price)}
        elif start or end or seat:
            warn.append(
                "No membership created: the row needs start and expiry dates and a shift or time."
            )

        if seat and seat[0] == "waitlist":
            v["waitlist_position"] = seat[1]
            if len(seat) == 3:
                v["waitlist_note"] = f"Waiting list code {seat[2]} in the old sheet"
        elif seat:
            number = seat[1]
            v["seat_number"] = number
            if number not in seats and not options["create_missing"]:
                err.append(
                    f"Seat {number} does not exist. Add it under Settings or allow new seats."
                )
            if has_membership and minutes:
                window = (start, end, minutes)
                for (
                    other_start,
                    other_end,
                    other_minutes,
                    other_row,
                    other_name,
                ) in file_bookings.get(number, []):
                    sharing = branch.allow_seat_sharing
                    if (
                        start <= other_end
                        and other_start <= end
                        and (not sharing or ranges_overlap(minutes, other_minutes))
                    ):
                        err.append(
                            f"Seat {number} is also given to {other_name} "
                            f"(row {other_row}) for the same time."
                        )
                        break
                if number in seats:
                    clashes = seat_conflicts(
                        seat=seats[number], start_date=start, end_date=end, minutes=minutes
                    )
                    if clashes:
                        err.append(describe_conflict(seats[number], clashes[0]))
                file_bookings.setdefault(number, []).append((*window, row_number, v["full_name"]))

        if paid:
            receipt = take(p.parse_int, cell("receipt_no"), "Receipt no.")
            if receipt is not None and (receipt in taken_receipts or receipt in file_receipts):
                warn.append(
                    f"Receipt no. {receipt} is already used; the payment gets the next free number."
                )
                receipt = None
            if receipt is not None:
                file_receipts.add(receipt)
            paid_on = (
                take(p.parse_date, cell("paid_on"), "Paid date", day_first) or start or admission
            )
            v["payment"] = {"amount": str(paid), "paid_on": _iso(paid_on), "receipt_no": receipt}
            if has_membership and price is not None and paid > price:
                warn.append(f"Paid ₹{paid} is more than the fee ₹{price}.")
        plans.append(plan)
    return plans


def check(job: ImportJob, table: Table | None = None) -> ImportJob:
    table = table or job_table(job)
    plans = plan_rows(job, table)
    with transaction.atomic():
        job.rows.all().delete()
        ImportRow.objects.bulk_create(
            ImportRow(
                job=job,
                row_number=plan.row_number,
                raw=plan.raw,
                values=plan.values,
                result=ImportRow.Result.ERROR if plan.errors else ImportRow.Result.READY,
                errors=plan.errors,
                warnings=plan.warnings,
            )
            for plan in plans
        )
        job.summary = summarize(job)
        job.status = ImportJob.Status.CHECKED
        job.save(update_fields=["summary", "status"])
    return job


def summarize(job: ImportJob) -> dict:
    rows = list(job.rows.all())
    values = [r.values for r in rows if r.result != ImportRow.Result.ERROR]
    return {
        "rows": len(rows),
        "ready": sum(r.result == ImportRow.Result.READY for r in rows),
        "errors": sum(r.result == ImportRow.Result.ERROR for r in rows),
        "with_warnings": sum(bool(r.warnings) for r in rows),
        "imported": sum(r.result == ImportRow.Result.IMPORTED for r in rows),
        "skipped": sum(r.result == ImportRow.Result.SKIPPED for r in rows),
        "memberships": sum("membership" in v for v in values),
        "payments": sum("payment" in v for v in values),
        "waiting_list": sum("waitlist_position" in v for v in values),
        "amount_paid": str(
            sum(
                (Decimal(v["payment"]["amount"]) for v in values if "payment" in v),
                start=Decimal("0"),
            )
        ),
    }


# ---------------------------------------------------------------------------
# Importing
# ---------------------------------------------------------------------------


def _time(text: str) -> time:
    return time.fromisoformat(text)


def _ensure_setup(job: ImportJob, rows: list[ImportRow]) -> tuple[dict, dict]:
    """Create the shifts and seats the file needs (when allowed); return lookups."""
    branch = job.branch
    shifts = {(s.start_time, s.end_time): s for s in Shift.objects.filter(branch=branch)}
    seats = {s.number: s for s in Seat.objects.filter(branch=branch)}
    for row in rows:
        values = row.values
        if "shift_times" in values:
            key = tuple(_time(t) for t in values["shift_times"])
            if key not in shifts:
                shifts[key] = Shift.objects.create(
                    branch=branch,
                    name=_shift_label(*key),
                    start_time=key[0],
                    end_time=key[1],
                    sort_order=key[0].hour * 60 + key[0].minute,
                )
        number = values.get("seat_number")
        if number and number not in seats:
            seats[number] = Seat.objects.create(branch=branch, number=number)
    return shifts, seats


def _import_row(job: ImportJob, row: ImportRow, shifts: dict, seats: dict, by) -> dict:
    values, branch = row.values, job.branch
    created: dict = {}
    mobile = values["mobile"]
    new_account = not User.objects.filter(mobile=mobile).exists()
    student = create_student(
        branch=branch,
        by=by,
        roll_no=values.get("roll_no"),
        full_name=values["full_name"],
        mobile=mobile,
        aadhaar=values.get("aadhaar", ""),
        gender=values.get("gender", ""),
        father_name=values.get("father_name", ""),
        admission_date=values.get("admission_date"),
        notes=values.get("notes", ""),
    )
    created["student"] = student.pk
    if new_account and student.account_id:
        created["account"] = student.account_id

    shift = None
    if values.get("shift_id"):
        shift = Shift.objects.get(pk=values["shift_id"], branch=branch)
    elif values.get("shift_times"):
        shift = shifts[tuple(_time(t) for t in values["shift_times"])]

    membership = None
    if values.get("membership"):
        m = values["membership"]
        custom = values.get("custom_times")
        membership = save_membership(
            Membership(
                branch=branch,
                student=student,
                shift=shift,
                custom_start_time=_time(custom[0]) if custom else None,
                custom_end_time=_time(custom[1]) if custom else None,
                seat=seats.get(values.get("seat_number")) if values.get("seat_number") else None,
                start_date=date.fromisoformat(m["start"]),
                end_date=date.fromisoformat(m["end"]),
                price=Decimal(m["price"]),
                notes=" ".join(
                    filter(None, [f"Imported from {job.file_name}.", values.get("extra_slot_note")])
                ),
                created_by=by,
            )
        )
        created["membership"] = membership.pk

    if values.get("waitlist_position"):
        entry = WaitlistEntry.objects.create(
            branch=branch,
            student=student,
            preferred_shift=shift,
            position=values["waitlist_position"],
            note=values.get("waitlist_note", ""),
        )
        created["waitlist"] = entry.pk

    if values.get("payment"):
        pay = values["payment"]
        payment = record_payment(
            student=student,
            membership=membership,
            amount=Decimal(pay["amount"]),
            paid_on=date.fromisoformat(pay["paid_on"])
            if pay.get("paid_on")
            else timezone.localdate(),
            receipt_no=pay.get("receipt_no"),
            notes="Imported",
            by=by,
        )
        created["payment"] = payment.pk
    return created


def _message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(exc.messages)
    return "The database refused this row (for example a seat clash)."


@transaction.atomic
def commit(job: ImportJob, *, by, skip_errors: bool = False) -> ImportJob:
    job = ImportJob.objects.select_for_update().get(pk=job.pk)
    if job.status != ImportJob.Status.CHECKED:
        raise ValidationError(
            "This file was already imported or undone. Upload it again to re-import."
        )
    errors = job.rows.filter(result=ImportRow.Result.ERROR).count()
    if errors and not skip_errors:
        raise ValidationError(
            f"{errors} row{'s have' if errors > 1 else ' has'} errors. Fix them in the file, "
            "or choose to skip those rows."
        )
    rows = list(job.rows.filter(result=ImportRow.Result.READY))
    shifts, seats = _ensure_setup(job, rows)
    for row in rows:
        savepoint = transaction.savepoint()
        try:
            row.created = _import_row(job, row, shifts, seats, by)
            row.result = ImportRow.Result.IMPORTED
            transaction.savepoint_commit(savepoint)
        except (ValidationError, IntegrityError) as exc:
            transaction.savepoint_rollback(savepoint)
            if not skip_errors:
                raise ValidationError(f"Row {row.row_number}: {_message(exc)}") from exc
            row.result = ImportRow.Result.SKIPPED
            row.errors = [*row.errors, _message(exc)]
        row.save(update_fields=["created", "result", "errors"])
    job.rows.filter(result=ImportRow.Result.ERROR).update(result=ImportRow.Result.SKIPPED)
    job.status = ImportJob.Status.IMPORTED
    job.imported_at = timezone.now()
    job.summary = summarize(job)
    job.save(update_fields=["status", "imported_at", "summary"])
    return job


@transaction.atomic
def undo(job: ImportJob, *, by) -> ImportJob:
    job = ImportJob.objects.select_for_update().get(pk=job.pk)
    if job.status != ImportJob.Status.IMPORTED:
        raise ValidationError("Only an imported file can be undone.")
    if timezone.now() - job.imported_at > UNDO_WINDOW:
        raise ValidationError("Imports can be undone for 7 days only.")
    rows = list(job.rows.filter(result=ImportRow.Result.IMPORTED).order_by("-row_number"))
    student_ids = [r.created["student"] for r in rows if "student" in r.created]
    ours_m = {r.created["membership"] for r in rows if "membership" in r.created}
    ours_p = {r.created["payment"] for r in rows if "payment" in r.created}
    changed = (
        Membership.objects.filter(student_id__in=student_ids).exclude(pk__in=ours_m).exists()
        or Payment.objects.filter(student_id__in=student_ids).exclude(pk__in=ours_p).exists()
    )
    if changed:
        raise ValidationError(
            "Some imported students have new memberships or payments since the import, "
            "so it cannot be undone automatically."
        )
    for row in rows:
        created = row.created
        Payment.objects.filter(pk=created.get("payment")).delete()
        WaitlistEntry.objects.filter(pk=created.get("waitlist")).delete()
        Membership.objects.filter(pk=created.get("membership")).delete()
        Student.objects.filter(pk=created.get("student")).delete()
        if created.get("account"):
            User.objects.filter(
                pk=created["account"], last_login__isnull=True, student_profiles__isnull=True
            ).delete()
    job.status = ImportJob.Status.UNDONE
    job.undone_at = timezone.now()
    job.save(update_fields=["status", "undone_at"])
    return job
