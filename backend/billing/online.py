"""
Online payments through Razorpay payment links.

1. A student starts a payment (dues on a membership, or a renewal). The amount always comes
   from the server: the membership's balance, or the chosen plan's fee.
2. They pay on Razorpay's page and come back to /portal/pay/return.
3. The payment is recorded only after Razorpay confirms it: a signed webhook, or the app
   asking Razorpay's API (on the student's return, and every few minutes from a job).
   Nothing the browser says is trusted on its own.
4. Recording is idempotent, so the webhook, the return page and the job can all report the
   same payment. Money that arrives when something changed meanwhile (the seat was taken,
   the desk already renewed) is still recorded, with a note for the desk to sort out.
"""

import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from audit import services as audit
from audit.mixins import snapshot
from library.models import Plan
from members.models import Membership, Student
from members.services import default_end_date, renew_membership, renewal_start, seat_conflicts

from . import razorpay
from .models import OnlinePayment, Payment
from .services import record_payment

logger = logging.getLogger(__name__)

LINK_MINUTES = 20  # Razorpay needs a link to stay open at least 15 minutes
RENEW_GRACE_DAYS = 30  # after this long without a membership, renew at the desk
METHOD_TO_MODE = {
    "upi": Payment.Mode.UPI,
    "card": Payment.Mode.CARD,
    "netbanking": Payment.Mode.BANK,
    "emandate": Payment.Mode.BANK,
    "nach": Payment.Mode.BANK,
    "bank_transfer": Payment.Mode.BANK,
}
UNAVAILABLE = "Online payment is not available right now. Please pay at the front desk."


def is_open(branch, student: Student | None = None) -> bool:
    """
    Online payments are on for this branch (and, given a student, for them). On a deployed
    server in Razorpay test mode only RAZORPAY_TEST_MOBILES can pay: test money must never
    give a real student a receipt or a renewal.
    """
    if not (razorpay.configured() and branch.allow_online_payments):
        return False
    if student is not None and razorpay.test_mode() and settings.IS_DEPLOYED:
        return student.mobile in test_mobiles()
    return True


def test_mobiles() -> set[str]:
    return {"".join(c for c in m if c.isdigit())[-10:] for m in settings.RAZORPAY_TEST_MOBILES}


class AlreadyPaid(Exception):
    """An earlier link for the same thing turned out to be paid; no new one is opened."""

    def __init__(self, online: "OnlinePayment"):
        super().__init__(f"Online payment {online.pk} is already paid")
        self.online = online


def paise(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1")))


def _rupees(amount: Decimal) -> str:
    return f"₹{amount:,.0f}" if amount == amount.to_integral() else f"₹{amount:,.2f}"


# ---------------------------------------------------------------------------
# What a student can pay
# ---------------------------------------------------------------------------


def latest_membership(student: Student) -> Membership | None:
    return (
        Membership.objects.not_cancelled()
        .filter(student=student)
        .select_related("seat", "shift", "plan", "branch")
        .order_by("-end_date", "-pk")
        .first()
    )


def renewal_options(student: Student, today=None) -> dict | None:
    """
    The plans this student can renew into online: same seat and shift as their latest
    membership, from the day after it ends (or today if it has lapsed). Mirrors what the
    desk's Renew button does, including carrying the student's discount forward.
    """
    today = today or timezone.localdate()
    previous = latest_membership(student)
    if previous is None or previous.state_on(today) == Membership.State.UPCOMING:
        return None  # never joined, or already renewed
    if previous.end_date < today - timedelta(days=RENEW_GRACE_DAYS):
        return None  # away for a while: the desk sorts out a seat
    start = renewal_start(previous, today)
    plans = Plan.objects.filter(branch=student.branch, is_active=True).select_related("shift")
    plans = (
        plans.filter(shift=previous.shift) | plans.filter(shift__isnull=True)
        if previous.shift_id
        else plans.filter(shift__isnull=True)
    )
    options = []
    for plan in plans.order_by("duration_months", "price"):
        end = default_end_date(start, plan.duration_months)
        discount = min(previous.discount, plan.price)
        amount = plan.price - discount
        if amount <= 0:
            continue
        options.append(
            {
                "plan": plan,
                "start_date": start,
                "end_date": end,
                "price": plan.price,
                "discount": discount,
                "amount": amount,
                "reason": _seat_problem(previous, start, end),
            }
        )
    return {"membership": previous, "options": options} if options else None


def _seat_problem(previous: Membership, start, end) -> str:
    """Why the seat cannot be kept for these dates, without naming anyone else."""
    seat = previous.seat
    if seat is None:
        return ""
    if not seat.is_active:
        return f"Seat {seat.number} is no longer in use. Please renew at the front desk."
    clashes = seat_conflicts(
        seat=seat, start_date=start, end_date=end, minutes=previous.compute_minute_range()
    )
    if clashes:
        first = min(c.start_date for c in clashes)
        return (
            f"Seat {seat.number} is booked from {max(first, start):%d %b %Y}. "
            "Please renew at the front desk."
        )
    return ""


# ---------------------------------------------------------------------------
# Starting a payment
# ---------------------------------------------------------------------------


def _describe(online: OnlinePayment) -> str:
    library = online.branch.name
    if online.purpose == OnlinePayment.Purpose.RENEWAL:
        seat = online.membership.seat
        where = f", seat {seat.number}" if seat else ""
        return (
            f"{library}: renewal, {online.plan.name} "
            f"({online.renewal_start:%d %b %Y} to {online.renewal_end:%d %b %Y}){where}"
        )
    m = online.membership
    return f"{library}: fees for {m.start_date:%d %b %Y} to {m.end_date:%d %b %Y}"


def _customer(student: Student) -> dict:
    customer = {"name": student.full_name[:100]}
    if student.mobile:
        customer["contact"] = f"+91{student.mobile}"
    return customer


def start_payment(
    *,
    student: Student,
    purpose: str,
    membership_id: int,
    plan_id: int | None = None,
    user=None,
    callback_url: str,
) -> OnlinePayment:
    if not is_open(student.branch, student):
        raise ValidationError({"detail": UNAVAILABLE})
    # One start at a time per student (two quick taps), without holding a database lock
    # while Razorpay answers.
    key = f"online-payment-start:{student.pk}"
    if not cache.add(key, 1, timeout=60):
        raise ValidationError({"detail": "A payment is already being started. Please wait."})
    try:
        earlier = _settle_earlier(student, purpose, membership_id)
        online = _new_attempt(student, purpose, membership_id, plan_id, user)
        expires = timezone.now() + timedelta(minutes=LINK_MINUTES)
        try:
            link = razorpay.create_payment_link(
                amount_paise=paise(online.amount),
                reference=online.reference,
                description=_describe(online),
                customer=_customer(student),
                callback_url=callback_url,
                expire_by=int(expires.timestamp()),
                notes={
                    "online_payment": str(online.pk),
                    "roll_no": str(student.roll_no),
                    "purpose": purpose,
                },
            )
        except razorpay.RazorpayError as exc:
            logger.warning("Could not create a Razorpay payment link: %s", exc)
            online.delete()  # no link was ever offered
            raise ValidationError(
                {
                    "detail": "Razorpay could not start the payment. Please try again in a "
                    "minute, or pay at the front desk."
                }
            ) from exc
        online.link_id = link["id"]
        online.link_url = link["short_url"]
        online.expires_at = expires
        online.save(update_fields=["link_id", "link_url", "expires_at"])
    finally:
        cache.delete(key)

    # Only the newest link should stay payable.
    for old in earlier:
        try:
            razorpay.cancel_payment_link(old.link_id)
        except razorpay.RazorpayError as exc:
            logger.info("Old payment link %s not cancelled: %s", old.link_id, exc)
            continue
        OnlinePayment.objects.filter(pk=old.pk, status=OnlinePayment.Status.PENDING).update(
            status=OnlinePayment.Status.CANCELLED
        )
    return online


def _settle_earlier(student: Student, purpose: str, membership_id: int) -> list[OnlinePayment]:
    """
    Ask Razorpay about this student's unfinished links first. One may have been paid
    without the student getting back here (a UPI app that never returned); it is recorded
    now, and a second payment for the same thing is refused. Returns the links still open.
    """
    still_open = []
    pending = OnlinePayment.objects.filter(
        student=student, status=OnlinePayment.Status.PENDING
    ).exclude(link_id=None)
    for attempt in pending:
        try:
            attempt = check(attempt)
        except razorpay.RazorpayError as exc:
            logger.warning("Could not check online payment %s: %s", attempt.pk, exc)
            raise ValidationError(
                {"detail": "Razorpay could not be reached. Please try again in a minute."}
            ) from exc
        same = attempt.purpose == purpose and attempt.membership_id == membership_id
        if same and attempt.status in {OnlinePayment.Status.PAID, OnlinePayment.Status.FLAGGED}:
            raise AlreadyPaid(attempt)
        if same and attempt.status == OnlinePayment.Status.PENDING:
            still_open.append(attempt)
    return still_open


def _new_attempt(student, purpose, membership_id, plan_id, user) -> OnlinePayment:
    """The attempt row, with the amount worked out here, never taken from the browser."""
    terms = {}
    if purpose == OnlinePayment.Purpose.DUES:
        membership = (
            Membership.objects.not_cancelled()
            .with_totals()
            .filter(student=student, pk=membership_id)
            .first()
        )
        if membership is None:
            raise ValidationError({"membership": "Choose one of your memberships."})
        amount = membership.due_total
        if amount <= 0:
            raise ValidationError({"detail": "Nothing is due on this membership."})
    elif purpose == OnlinePayment.Purpose.RENEWAL:
        choices = renewal_options(student)
        if choices is None or choices["membership"].pk != membership_id:
            raise ValidationError(
                {"detail": "This membership cannot be renewed online. Please ask at the desk."}
            )
        option = next((o for o in choices["options"] if o["plan"].pk == plan_id), None)
        if option is None:
            raise ValidationError({"plan": "Choose one of the plans shown."})
        if option["reason"]:
            raise ValidationError({"detail": option["reason"]})
        membership = choices["membership"]
        amount = option["amount"]
        terms = {
            "plan": option["plan"],
            "renewal_start": option["start_date"],
            "renewal_end": option["end_date"],
            "renewal_price": option["price"],
            "renewal_discount": option["discount"],
        }
    else:
        raise ValidationError({"purpose": "Choose dues or renewal."})
    return OnlinePayment.objects.create(
        branch=student.branch,
        student=student,
        purpose=purpose,
        membership=membership,
        amount=amount,
        reference=f"ml{secrets.token_hex(10)}",
        started_by=user,
        **terms,
    )


# ---------------------------------------------------------------------------
# Recording a confirmed payment
# ---------------------------------------------------------------------------


def complete(online_id: int, *, payment: dict) -> OnlinePayment:
    """
    Record a payment Razorpay reported: `payment` has its id, amount (paise), currency,
    status, method and created_at (Unix time). Does nothing until it is captured, and
    nothing the second time.
    """
    with transaction.atomic():
        online = (
            OnlinePayment.objects.select_for_update(of=("self",))
            .select_related("student__branch", "membership__seat", "plan", "branch")
            .get(pk=online_id)
        )
        if online.payment_id is not None or online.status == OnlinePayment.Status.FLAGGED:
            return online  # recorded already, or left for a person to sort out
        if payment.get("status") != "captured":
            return online
        problem = _mismatch(online, payment)
        if problem:
            # Never record money that cannot be accounted for: a person looks at it, and it
            # leaves the queue the checking job works through.
            logger.error("Online payment %s not recorded: %s", online.pk, problem)
            online.status = OnlinePayment.Status.FLAGGED
            online.gateway_payment_id = payment.get("id") or None
            online.problem = problem[:300]
            online.save(update_fields=["status", "gateway_payment_id", "problem"])
            return online

        notes = []
        if online.status != OnlinePayment.Status.PENDING:
            notes.append(
                f"This payment link had been closed ({online.status.lower()}) but was paid."
            )
        # Locked so a renewal at the desk and this one cannot both be made at once.
        membership = Membership.objects.select_for_update().get(pk=online.membership_id)
        target, renewal = online.membership, None
        if membership.status == Membership.Status.CANCELLED:
            target = None
            notes.append(
                "The membership was cancelled while the student was paying, so the money is "
                "kept as an advance: refund it, or use it for a new membership."
            )
        elif online.purpose == OnlinePayment.Purpose.RENEWAL:
            target, renewal, note = _renew(online)
            if note:
                notes.append(note)

        method = (payment.get("method") or "").lower()
        created = payment.get("created_at")
        paid_on = (
            timezone.localdate(datetime.fromtimestamp(int(created), tz=UTC))
            if created
            else timezone.localdate()
        )
        recorded = record_payment(
            student=online.student,
            membership=target,
            amount=online.amount,
            mode=METHOD_TO_MODE.get(method, Payment.Mode.OTHER),
            paid_on=min(paid_on, timezone.localdate()),
            reference=payment["id"],
            source=Payment.Source.ONLINE,
            notes=f"Paid online through Razorpay ({method or 'online'})",
        )
        if online.purpose == OnlinePayment.Purpose.DUES and target is not None:
            balance = Membership.objects.with_totals().get(pk=online.membership_id).due_total
            if balance < 0:
                notes.append(
                    f"{_rupees(-balance)} more than the fee was paid (paid twice?). Refund it "
                    "or keep it as credit."
                )

        online.status = OnlinePayment.Status.PAID
        online.paid_at = timezone.now()
        online.gateway_payment_id = payment["id"]
        online.method = method[:20]
        online.payment = recorded
        online.renewal = renewal
        online.problem = " ".join(notes)[:300]
        online.save()
        audit.record(
            None,
            "payment.online",
            entity="payment",
            entity_id=recorded.pk,
            after=snapshot(recorded),
            metadata={
                "online_payment": online.pk,
                "razorpay_payment": payment["id"],
                "purpose": online.purpose,
                "renewal": renewal.pk if renewal else None,
            },
        )
    return online


def _mismatch(online: OnlinePayment, payment: dict) -> str:
    if not payment.get("id"):
        return "Razorpay reported a payment without its id."
    expected = paise(online.amount)
    if payment.get("currency", "INR") != "INR":
        return f"Razorpay reported a payment in {payment.get('currency')}, not rupees."
    if int(payment.get("amount") or 0) != expected:
        got = Decimal(int(payment.get("amount") or 0)) / 100
        return f"Razorpay received {_rupees(got)}, but {_rupees(online.amount)} was asked for."
    taken = (
        OnlinePayment.objects.filter(gateway_payment_id=payment["id"]).exclude(pk=online.pk).first()
    )
    if taken is None and Payment.objects.filter(reference=payment["id"]).exists():
        return f"Razorpay payment {payment['id']} is already on a receipt."
    if taken:
        return f"Razorpay payment {payment['id']} is already recorded (attempt {taken.pk})."
    return ""


def _renew(online: OnlinePayment) -> tuple[Membership | None, Membership | None, str]:
    """Make the paid-for renewal. Returns (membership to pay into, new renewal, note)."""
    previous = online.membership
    existing = Membership.objects.not_cancelled().filter(renewed_from=previous).first()
    if existing is not None:
        return (
            existing,
            None,
            "The desk had already renewed this membership; the payment was added to that "
            "renewal. Check it was not paid twice.",
        )
    try:
        renewal = renew_membership(
            previous,
            plan=online.plan,
            start_date=online.renewal_start,
            end_date=online.renewal_end,
            price=online.renewal_price,
            discount=online.renewal_discount,
            notes="Renewed online",
        )
    except ValidationError as exc:
        reason = " ".join(str(m) for m in exc.messages)
        return (
            None,
            None,
            f"Paid, but the renewal could not be made ({reason}) The money is kept as an "
            "advance: renew at the desk, then move the payment to it.",
        )
    return renewal, renewal, ""


# ---------------------------------------------------------------------------
# Hearing back from Razorpay
# ---------------------------------------------------------------------------


def check(online: OnlinePayment) -> OnlinePayment:
    """Ask Razorpay how this payment link stands, and record the payment if it was paid."""
    if online.payment_id is not None or not online.link_id:
        return online
    link = razorpay.fetch_payment_link(online.link_id)
    captured = [p for p in link.get("payments") or [] if p.get("status") == "captured"]
    if captured:
        paid = captured[0]
        return complete(
            online.pk,
            payment={
                "id": paid.get("payment_id"),
                "amount": paid.get("amount"),
                "currency": link.get("currency", "INR"),
                "status": "captured",
                "method": paid.get("method", ""),
                "created_at": paid.get("created_at"),
            },
        )
    closed = {"expired": OnlinePayment.Status.EXPIRED, "cancelled": OnlinePayment.Status.CANCELLED}
    if link.get("status") in closed:
        OnlinePayment.objects.filter(pk=online.pk, status=OnlinePayment.Status.PENDING).update(
            status=closed[link["status"]]
        )
        online.refresh_from_db()
    return online


def confirm_from_callback(*, user, params) -> OnlinePayment:
    """The student is back from Razorpay's page with the link's details in the address."""
    link_id = str(params.get("razorpay_payment_link_id", ""))
    reference = str(params.get("razorpay_payment_link_reference_id", ""))
    status = str(params.get("razorpay_payment_link_status", ""))
    payment_id = str(params.get("razorpay_payment_id", ""))
    online = OnlinePayment.objects.filter(
        link_id=link_id, reference=reference, student__account=user
    ).first()
    if online is None or not link_id:
        raise ValidationError({"detail": "This payment was not found."})
    if online.payment_id is not None or status != "paid":
        return online
    if not razorpay.callback_signature_valid(
        link_id=link_id,
        reference=reference,
        status=status,
        payment_id=payment_id,
        signature=str(params.get("razorpay_signature", "")),
    ):
        logger.warning("Bad Razorpay callback signature for online payment %s", online.pk)
        raise ValidationError({"detail": "This payment could not be verified."})
    try:
        return check(online)
    except razorpay.RazorpayError as exc:
        # The webhook or the checking job will record it; the page keeps asking meanwhile.
        logger.warning("Could not confirm online payment %s yet: %s", online.pk, exc)
        return online


def handle_webhook(body: bytes, signature: str) -> str:
    if not razorpay.webhook_signature_valid(body, signature):
        raise PermissionDenied("Bad Razorpay webhook signature.")
    event = json.loads(body)
    kind = event.get("event", "")
    payload = event.get("payload") or {}
    link = (payload.get("payment_link") or {}).get("entity") or {}
    online = OnlinePayment.objects.filter(link_id=link.get("id")).first() if link else None
    if kind == "payment_link.paid":
        if online is None:
            logger.warning("Razorpay webhook for an unknown payment link %s", link.get("id"))
            return "unknown link"
        paid = (payload.get("payment") or {}).get("entity") or {}
        complete(
            online.pk,
            payment={
                "id": paid.get("id"),
                "amount": paid.get("amount"),
                "currency": paid.get("currency"),
                "status": paid.get("status"),
                "method": paid.get("method", ""),
                "created_at": paid.get("created_at"),
            },
        )
        return "paid"
    if kind in {"payment_link.expired", "payment_link.cancelled"} and online is not None:
        new_status = (
            OnlinePayment.Status.EXPIRED
            if kind.endswith("expired")
            else OnlinePayment.Status.CANCELLED
        )
        OnlinePayment.objects.filter(pk=online.pk, status=OnlinePayment.Status.PENDING).update(
            status=new_status
        )
        return kind
    return "ignored"


def check_open_payments() -> dict:
    """For the job: ask Razorpay about every link still waiting (a missed webhook)."""
    if not razorpay.configured():
        return {"skipped": "Razorpay is not set up"}
    give_up_before = timezone.now() - timedelta(days=2)
    waiting = list(
        OnlinePayment.objects.filter(
            status=OnlinePayment.Status.PENDING, link_id__isnull=False
        ).order_by("created_at")
    )
    paid = errors = expired = 0
    for online in waiting:
        try:
            online = check(online)
        except razorpay.RazorpayError as exc:
            errors += 1
            logger.warning("Could not check online payment %s: %s", online.pk, exc)
            continue
        if online.status == OnlinePayment.Status.PAID:
            paid += 1
        elif online.status == OnlinePayment.Status.PENDING and online.created_at < give_up_before:
            # Razorpay just said it is not paid, and links last 20 minutes: close it.
            OnlinePayment.objects.filter(pk=online.pk, status=OnlinePayment.Status.PENDING).update(
                status=OnlinePayment.Status.EXPIRED
            )
            expired += 1
    if waiting and errors == len(waiting):
        raise razorpay.RazorpayError(f"Razorpay could not be reached for {errors} payments.")
    return {"checked": len(waiting), "paid": paid, "errors": errors, "expired": expired}
