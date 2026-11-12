"""Payments with sequential receipt numbers. A payment is never deleted, only voided."""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from library.models import Branch, Plan
from members.models import Membership, Student


class Payment(models.Model):
    class Mode(models.TextChoices):
        CASH = "CASH", "Cash"
        UPI = "UPI", "UPI"
        CARD = "CARD", "Card"
        BANK = "BANK", "Bank transfer"
        OTHER = "OTHER", "Other"

    class Source(models.TextChoices):
        DESK = "DESK", "Front desk"
        ONLINE = "ONLINE", "Online (Razorpay)"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="payments")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="payments")
    membership = models.ForeignKey(
        Membership, on_delete=models.PROTECT, null=True, blank=True, related_name="payments"
    )
    receipt_no = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.CASH)
    paid_on = models.DateField(default=timezone.localdate)
    reference = models.CharField(max_length=80, blank=True, help_text="UPI or bank reference.")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.DESK)
    notes = models.CharField(max_length=200, blank=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    is_void = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=200, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-receipt_no"]
        indexes = [models.Index(fields=["paid_on"])]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "receipt_no"], name="unique_receipt_no_per_branch"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
        ]

    def __str__(self) -> str:
        return f"Receipt {self.receipt_no}: ₹{self.amount}"


class ReceiptSequence(models.Model):
    """The next receipt number for a branch, taken under a row lock so numbers never repeat."""

    branch = models.OneToOneField(Branch, on_delete=models.CASCADE, related_name="receipt_sequence")
    next_number = models.PositiveIntegerField(default=1)

    def __str__(self) -> str:
        return f"{self.branch}: next receipt {self.next_number}"


class OnlinePayment(models.Model):
    """
    One attempt by a student to pay online through a Razorpay payment link. When Razorpay
    confirms it, a normal Payment (with a receipt) is recorded and, for a renewal, the next
    membership is made. Kept even when abandoned, so the desk can see what happened.
    """

    class Purpose(models.TextChoices):
        DUES = "DUES", "Dues"
        RENEWAL = "RENEWAL", "Renewal"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Waiting for payment"
        PAID = "PAID", "Paid"
        # Razorpay took money that could not be matched (a different amount, say): not
        # recorded, left for the owner.
        FLAGGED = "FLAGGED", "Paid, needs checking"
        EXPIRED = "EXPIRED", "Not paid in time"
        CANCELLED = "CANCELLED", "Cancelled"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="online_payments")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="online_payments")
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    # Dues: the membership being paid for. Renewal: the membership being renewed.
    membership = models.ForeignKey(
        Membership, on_delete=models.PROTECT, related_name="online_payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # The renewal's terms, fixed when the student chose them (renewals only).
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    renewal_start = models.DateField(null=True, blank=True)
    renewal_end = models.DateField(null=True, blank=True)
    renewal_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    renewal_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    # Sent to Razorpay as the link's reference_id; unique across the Razorpay account.
    reference = models.CharField(max_length=40, unique=True)
    link_id = models.CharField(max_length=40, unique=True, null=True, blank=True)
    link_url = models.URLField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    gateway_payment_id = models.CharField(max_length=40, unique=True, null=True, blank=True)
    method = models.CharField(max_length=20, blank=True)
    payment = models.OneToOneField(
        Payment, on_delete=models.PROTECT, null=True, blank=True, related_name="online"
    )
    renewal = models.OneToOneField(
        Membership,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="paid_online_by",
    )
    # Set when the money arrived but something needs a person (for example the seat was
    # taken meanwhile). Cleared by the owner once sorted.
    problem = models.CharField(max_length=300, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="online_payment_amount_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"Online {self.get_purpose_display().lower()} ₹{self.amount} ({self.status})"
