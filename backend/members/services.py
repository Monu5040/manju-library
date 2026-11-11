"""Rules for students and memberships: roll numbers, seat conflicts, admissions, renewals."""

import calendar
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from accounts.models import Role, User
from core.validators import format_aadhaar, normalize_aadhaar, validate_aadhaar
from library.models import Branch, Seat, Shift, format_minutes, ranges_overlap

from .models import Membership, Student, WaitlistEntry


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return day.replace(
        year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1])
    )


def default_end_date(start: date, months: int) -> date:
    """The library's rule: a 1-month plan from 28 Jul runs to 27 Aug (inclusive)."""
    return add_months(start, months) - timedelta(days=1)


def next_roll_no(branch: Branch) -> int:
    # Lock the branch row so two admissions at once cannot take the same roll number.
    Branch.objects.select_for_update().get(pk=branch.pk)
    highest = Student.objects.filter(branch=branch).aggregate(top=Max("roll_no"))["top"]
    return (highest or 0) + 1


def set_aadhaar(student: Student, raw: str) -> None:
    digits = normalize_aadhaar(raw)
    if not digits:
        student.aadhaar, student.aadhaar_last4 = "", ""
        return
    validate_aadhaar(digits)
    student.aadhaar = format_aadhaar(digits)
    student.aadhaar_last4 = digits[-4:]


def ensure_login_account(student: Student) -> None:
    """
    Link the student to the portal login for their mobile, creating it if needed.

    A staff or admin login never gets student profiles. If the mobile belongs to one, the
    student is left unlinked, which also drops any link to their previous number.
    """
    account = User.objects.filter(mobile=student.mobile).first()
    if account is None:
        account = User.objects.create_user(student.mobile, full_name=student.full_name)
    student.account = account if account.role == Role.STUDENT else None


def seat_conflicts(
    *,
    seat: Seat,
    start_date: date,
    end_date: date,
    minutes: tuple[int, int],
    exclude_id: int | None = None,
) -> list[Membership]:
    """Live memberships on this seat that clash with the given dates and time of day."""
    overlapping = (
        Membership.objects.not_cancelled()
        .filter(seat=seat, start_date__lte=end_date, end_date__gte=start_date)
        .select_related("student")
    )
    if exclude_id:
        overlapping = overlapping.exclude(pk=exclude_id)
    sharing = seat.branch.allow_seat_sharing
    return [
        m
        for m in overlapping
        if not sharing or ranges_overlap(minutes, (m.start_minute, m.end_minute))
    ]


def describe_conflict(seat: Seat, other: Membership) -> str:
    when = f"{format_minutes(other.start_minute)} – {format_minutes(other.end_minute)}"
    return (
        f"Seat {seat.number} is already given to {other.student.full_name} "
        f"(roll {other.student.roll_no}) for {when}, {other.start_date:%d %b %Y} to "
        f"{other.end_date:%d %b %Y}."
    )


def validate_membership(membership: Membership) -> None:
    errors = {}
    branch_id = membership.branch_id
    if membership.shift_id is None and not (
        membership.custom_start_time and membership.custom_end_time
    ):
        errors["shift"] = "Choose a shift or enter a custom start and end time."
    for field in ("shift", "seat", "plan"):
        related = getattr(membership, field)
        if related is not None and related.branch_id != branch_id:
            errors[field] = f"This {field} belongs to another branch."
    if membership.student.branch_id != branch_id:
        errors["student"] = "This student belongs to another branch."
    if membership.end_date < membership.start_date:
        errors["end_date"] = "The end date is before the start date."
    if membership.discount > membership.price:
        errors["discount"] = "The discount is larger than the fee."
    if membership.seat is not None and membership.seat.is_active is False:
        errors["seat"] = f"Seat {membership.seat.number} is switched off."
    if errors:
        raise ValidationError(errors)

    if membership.seat is not None and membership.status != Membership.Status.CANCELLED:
        clashes = seat_conflicts(
            seat=membership.seat,
            start_date=membership.start_date,
            end_date=membership.end_date,
            minutes=membership.compute_minute_range(),
            exclude_id=membership.pk,
        )
        if clashes:
            raise ValidationError({"seat": describe_conflict(membership.seat, clashes[0])})


def save_membership(membership: Membership) -> Membership:
    validate_membership(membership)
    is_new = membership.pk is None
    try:
        with transaction.atomic():
            membership.save()
            if is_new and membership.status != Membership.Status.CANCELLED:
                welcome_back(membership)
    except IntegrityError as exc:
        if "no_double_booked_seat" in str(exc):
            # Someone else booked the seat between our check and the save.
            raise ValidationError({"seat": "This seat was just taken. Pick another."}) from exc
        raise
    return membership


def welcome_back(membership: Membership) -> None:
    """A new membership makes a student current again, and a seat ends their wait."""
    student = membership.student
    if student.status == Student.Status.LEFT:
        student.status = Student.Status.ACTIVE
        student.save(update_fields=["status", "updated_at"])
    if membership.seat_id:
        WaitlistEntry.objects.filter(student=student, status=WaitlistEntry.Status.WAITING).update(
            status=WaitlistEntry.Status.SEATED
        )


def free_seats(branch: Branch, start: date, days: int = 30) -> dict[int, list[str]]:
    """
    For every active shift, the seats nobody has booked in that shift's hours from `start`
    for `days` days: what can be offered to someone waiting. Follows the branch's
    seat-sharing setting, like a new booking would.
    """
    end = start + timedelta(days=days - 1)
    booked: dict[int, list[tuple[int, int]]] = {}
    for seat_id, first, last in (
        Membership.objects.not_cancelled()
        .filter(branch=branch, seat__isnull=False, start_date__lte=end, end_date__gte=start)
        .values_list("seat_id", "start_minute", "end_minute")
    ):
        booked.setdefault(seat_id, []).append((first, last))
    seats = list(Seat.objects.filter(branch=branch, is_active=True).order_by("sort_key", "number"))
    result = {}
    for shift in Shift.objects.filter(branch=branch, is_active=True):
        window = shift.minute_range
        result[shift.pk] = [
            seat.number
            for seat in seats
            if not any(
                not branch.allow_seat_sharing or ranges_overlap(window, slot)
                for slot in booked.get(seat.pk, [])
            )
        ]
    return result


@transaction.atomic
def create_student(*, branch: Branch, by=None, aadhaar: str = "", **fields) -> Student:
    roll_no = fields.pop("roll_no", None) or next_roll_no(branch)
    student = Student(branch=branch, roll_no=roll_no, created_by=by, **fields)
    set_aadhaar(student, aadhaar)
    ensure_login_account(student)
    student.full_clean(exclude=["account", "created_by", "aadhaar"])
    student.save()
    return student


def renewal_start(previous: Membership, today: date | None = None) -> date:
    """Continue straight after the old end date, or from today if it already lapsed."""
    today = today or timezone.localdate()
    return max(previous.end_date + timedelta(days=1), today)


@transaction.atomic
def renew_membership(previous: Membership, *, by=None, **overrides) -> Membership:
    plan = overrides.get("plan", previous.plan)
    start = overrides.get("start_date") or renewal_start(previous)
    months = plan.duration_months if plan else 1
    renewal = Membership(
        branch=previous.branch,
        student=previous.student,
        plan=plan,
        shift=overrides.get("shift", previous.shift),
        custom_start_time=overrides.get("custom_start_time", previous.custom_start_time),
        custom_end_time=overrides.get("custom_end_time", previous.custom_end_time),
        seat=overrides.get("seat", previous.seat),
        start_date=start,
        end_date=overrides.get("end_date") or default_end_date(start, months),
        price=overrides.get("price", plan.price if plan else previous.price),
        discount=overrides.get("discount", previous.discount),
        renewed_from=previous,
        notes=overrides.get("notes", ""),
        created_by=by,
    )
    return save_membership(renewal)
