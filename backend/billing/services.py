"""Recording and voiding payments, with gap-free receipt numbers per branch."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from library.models import Branch

from .models import Payment, ReceiptSequence


def next_receipt_number(branch: Branch) -> int:
    """Take the next receipt number under a row lock, so concurrent payments never collide."""
    sequence, _ = ReceiptSequence.objects.select_for_update().get_or_create(branch=branch)
    highest = Payment.objects.filter(branch=branch).aggregate(top=Max("receipt_no"))["top"] or 0
    number = max(sequence.next_number, highest + 1)
    sequence.next_number = number + 1
    sequence.save(update_fields=["next_number"])
    return number


@transaction.atomic
def record_payment(
    *,
    student,
    amount,
    by=None,
    membership=None,
    receipt_no: int | None = None,
    check_closed_days: bool = True,
    **fields,
) -> Payment:
    """
    Save a payment. `receipt_no` keeps a number from the old records when importing; it is
    used only if still free, otherwise the next number is taken.
    """
    if amount is None or amount <= 0:
        raise ValidationError({"amount": "Enter an amount above zero."})
    if membership is not None and membership.student_id != student.pk:
        raise ValidationError({"membership": "This membership belongs to another student."})
    if check_closed_days:  # imports bring in old payments on purpose and skip this
        from ledger.services import ensure_cash_day_open

        ensure_cash_day_open(
            student.branch,
            fields.get("paid_on") or timezone.localdate(),
            fields.get("mode", Payment.Mode.CASH),
        )
    branch = student.branch
    if not receipt_no or Payment.objects.filter(branch=branch, receipt_no=receipt_no).exists():
        receipt_no = next_receipt_number(branch)
    payment = Payment(
        branch=branch,
        student=student,
        membership=membership,
        amount=amount,
        collected_by=by,
        receipt_no=receipt_no,
        **fields,
    )
    payment.save()
    return payment


@transaction.atomic
def void_payment(payment: Payment, *, reason: str, by=None) -> Payment:
    if payment.is_void:
        raise ValidationError({"detail": "This payment is already void."})
    if not reason.strip():
        raise ValidationError({"reason": "Say why the payment is being voided."})
    payment.is_void = True
    payment.void_reason = reason.strip()
    payment.voided_by = by
    payment.voided_at = timezone.now()
    payment.save(update_fields=["is_void", "void_reason", "voided_by", "voided_at"])
    return payment
