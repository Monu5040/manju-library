"""
Reminders: who needs one today, what it says, and sending it.

The job runs every hour from 8 AM to 8 PM, and again whenever someone opens the Reminders
page, so everything here is safe to repeat: a reminder is created only once, and one that
no longer applies (renewed, paid, seated) is closed by itself.
"""

import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from core.sms import SMSError, reminder_ready, send_reminder
from library.models import Branch, Shift
from members.filters import renewed_later
from members.models import Membership, Student, WaitlistEntry
from members.services import free_seats

from .models import AutomationSettings, Reminder

WAITLIST_REPEAT_DAYS = 7
WAITLIST_OFFER_DAYS = 3
DUES_LOOKBACK_DAYS = 30
PLACEHOLDER = re.compile(r"\{(\w+)\}")
PLACEHOLDERS = {
    "name": "First name",
    "full_name": "Full name",
    "library": "Library name",
    "phone": "Library phone",
    "seat": "Seat number",
    "shift": "Shift or time",
    "date": "Last day of the membership",
    "amount": "Amount due (₹)",
}


def render(text: str, values: dict) -> str:
    """Fill {name}-style placeholders. Unknown ones stay as typed; nothing else is evaluated."""
    return PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), m.group(0))), text)


def rupees(amount: Decimal) -> str:
    """1,25,000 in Indian digit grouping, without paise."""
    digits = str(abs(int(round(amount))))
    if len(digits) > 3:
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", digits[:-3])
        digits = f"{head},{digits[-3:]}"
    return f"-{digits}" if amount < 0 else digits


def placeholder_values(branch: Branch, student: Student, membership=None, **extra) -> dict:
    values = {
        "name": student.full_name.split()[0] if student.full_name.strip() else "",
        "full_name": student.full_name,
        "library": branch.name,
        "phone": branch.phone,
        "seat": "",
        "shift": "",
        "date": "",
        "amount": "",
    }
    if membership is not None:
        values["seat"] = membership.seat.number if membership.seat_id else ""
        values["shift"] = membership.shift.name if membership.shift_id else membership.time_label
        values["date"] = f"{membership.end_date.day} {membership.end_date:%b %Y}"
    values.update(extra)
    return values


def _create(conf, kind, student, today, *, membership=None, entry=None, values, details) -> int:
    try:
        with transaction.atomic():
            Reminder.objects.create(
                branch=conf.branch,
                student=student,
                membership=membership,
                waitlist_entry=entry,
                kind=kind,
                for_date=today,
                mobile=student.mobile,
                message=render(conf.text_for(kind), values),
                details={**details, "variables": values},
            )
    except IntegrityError:
        return 0  # another run made the same reminder a moment ago
    return 1


def build_reminders(branch: Branch, today: date | None = None) -> int:
    """Create today's reminders for this branch; returns how many are new."""
    today = today or timezone.localdate()
    conf = AutomationSettings.for_branch(branch)
    if not conf.reminders_enabled:
        return 0
    live = (
        Membership.objects.not_cancelled()
        .filter(branch=branch, student__status=Student.Status.ACTIVE)
        .select_related("student", "seat", "shift")
    )
    ending = live.filter(~renewed_later())
    created = 0

    def membership_details(m: Membership) -> dict:
        return {
            "seat": m.seat.number if m.seat_id else "",
            "shift": m.shift.name if m.shift_id else m.time_label,
            "end_date": m.end_date.isoformat(),
        }

    if conf.days_before_expiry:
        soon = ending.filter(
            end_date__gt=today, end_date__lte=today + timedelta(days=conf.days_before_expiry)
        ).exclude(reminders__kind=Reminder.Kind.EXPIRING_SOON)
        for m in soon:
            created += _create(
                conf,
                Reminder.Kind.EXPIRING_SOON,
                m.student,
                today,
                membership=m,
                values=placeholder_values(branch, m.student, m),
                details=membership_details(m),
            )

    if conf.remind_on_expiry_day:
        for m in ending.filter(end_date=today).exclude(reminders__kind=Reminder.Kind.EXPIRES_TODAY):
            created += _create(
                conf,
                Reminder.Kind.EXPIRES_TODAY,
                m.student,
                today,
                membership=m,
                values=placeholder_values(branch, m.student, m),
                details=membership_details(m),
            )

    if conf.dues_after_days:
        earlier = Reminder.objects.filter(membership=OuterRef("pk"), kind=Reminder.Kind.DUES)
        if conf.dues_repeat_days:
            earlier = earlier.filter(for_date__gt=today - timedelta(days=conf.dues_repeat_days))
        owing = (
            live.with_totals()
            .filter(
                due_total__gt=0,
                start_date__lte=today - timedelta(days=conf.dues_after_days),
                end_date__gte=today - timedelta(days=DUES_LOOKBACK_DAYS),
            )
            .filter(~Exists(earlier))
        )
        for m in owing:
            created += _create(
                conf,
                Reminder.Kind.DUES,
                m.student,
                today,
                membership=m,
                values=placeholder_values(branch, m.student, m, amount=rupees(m.due_total)),
                details={**membership_details(m), "amount": str(m.due_total)},
            )

    if conf.waitlist_alerts:
        created += _waitlist(conf, today)
    return created


def _waitlist(conf: AutomationSettings, today: date) -> int:
    """
    Offer free seats strictly in waiting-list order: with two seats free in a shift, only
    the first two people waiting for that shift hear about it, each about a different seat.
    """
    free = free_seats(conf.branch, today)
    shifts = {s.pk: s for s in Shift.objects.filter(branch=conf.branch, is_active=True)}
    offered: dict[int, int] = defaultdict(int)
    created = 0
    waiting = (
        WaitlistEntry.objects.filter(branch=conf.branch, status=WaitlistEntry.Status.WAITING)
        .select_related("student")
        .order_by("position", "created_at")
    )
    for entry in waiting:
        if entry.student.status != Student.Status.ACTIVE:
            continue
        shift_id = entry.preferred_shift_id
        if shift_id is None and free:
            shift_id = max(free, key=lambda pk: len(free[pk]) - offered[pk])
        options = free.get(shift_id, [])
        if shift_id is None or len(options) <= offered[shift_id]:
            continue
        seat = options[offered[shift_id]]
        offered[shift_id] += 1  # this seat is theirs to take, even if told recently
        recent = Reminder.objects.filter(
            waitlist_entry=entry,
            kind=Reminder.Kind.WAITLIST,
            for_date__gt=today - timedelta(days=WAITLIST_REPEAT_DAYS),
        ).exists()
        if recent:
            continue
        shift = shifts[shift_id]
        created += _create(
            conf,
            Reminder.Kind.WAITLIST,
            entry.student,
            today,
            entry=entry,
            values=placeholder_values(conf.branch, entry.student, seat=seat, shift=shift.name),
            details={"seat": seat, "shift": shift.name, "position": entry.position},
        )
    return created


def _no_longer_needed(reminder: Reminder, today: date) -> str:
    if reminder.student.status == Student.Status.LEFT:
        return "The student has left."
    m = reminder.membership
    if reminder.kind == Reminder.Kind.WAITLIST:
        entry = reminder.waitlist_entry
        if entry is None or entry.status != WaitlistEntry.Status.WAITING:
            return "No longer on the waiting list."
        if reminder.for_date < today - timedelta(days=WAITLIST_OFFER_DAYS):
            return "The seat offer is more than 3 days old."
        return ""
    if m is None or m.status == Membership.Status.CANCELLED:
        return "The membership was cancelled."
    if reminder.kind in (Reminder.Kind.EXPIRING_SOON, Reminder.Kind.EXPIRES_TODAY):
        if (
            Membership.objects.not_cancelled()
            .filter(student=m.student_id, start_date__gt=m.end_date)
            .exists()
        ):
            return "Renewed."
        if m.end_date < today:
            return "The membership has ended."
    if reminder.kind == Reminder.Kind.DUES:
        due = Membership.objects.with_totals().get(pk=m.pk).due_total
        if due <= 0:
            return "Paid."
    return ""


def tidy_reminders(branch: Branch, today: date | None = None) -> int:
    """Close reminders that no longer apply; returns how many were closed."""
    today = today or timezone.localdate()
    closed = 0
    for reminder in Reminder.objects.filter(
        branch=branch, status__in=[Reminder.Status.PENDING, Reminder.Status.FAILED]
    ).select_related("student", "membership", "waitlist_entry"):
        reason = _no_longer_needed(reminder, today)
        if reason:
            reminder.status = Reminder.Status.SKIPPED
            reminder.note = reason
            reminder.save(update_fields=["status", "note"])
            closed += 1
    return closed


def send_by_sms(branch: Branch, today: date | None = None) -> dict:
    """Send today's waiting reminders by SMS, where the settings and a template allow it."""
    today = today or timezone.localdate()
    conf = AutomationSettings.for_branch(branch)
    result = {"sent": 0, "failed": 0}
    if not conf.send_sms:
        return result
    for reminder in Reminder.objects.filter(
        branch=branch, status=Reminder.Status.PENDING, for_date=today
    ):
        if not reminder_ready(reminder.kind):
            continue  # no approved template: it stays on the list for WhatsApp
        try:
            send_reminder(
                reminder.mobile,
                reminder.kind,
                reminder.message,
                reminder.details.get("variables", {}),
            )
        except SMSError as exc:
            reminder.status = Reminder.Status.FAILED
            reminder.note = str(exc)[:200]
            result["failed"] += 1
        else:
            reminder.status = Reminder.Status.SENT
            reminder.channel = Reminder.Channel.SMS
            reminder.sent_at = timezone.now()
            result["sent"] += 1
        reminder.save(update_fields=["status", "channel", "sent_at", "note"])
    return result


def refresh(branch: Branch) -> dict:
    """Close what no longer applies and add what is due now. Sends nothing."""
    return {"closed": tidy_reminders(branch), "created": build_reminders(branch)}
