"""Payments with sequential receipt numbers. A payment is never deleted, only voided."""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from library.models import Branch
from members.models import Membership, Student


class Payment(models.Model):
    class Mode(models.TextChoices):
        CASH = "CASH", "Cash"
        UPI = "UPI", "UPI"
        CARD = "CARD", "Card"
        BANK = "BANK", "Bank transfer"
        OTHER = "OTHER", "Other"

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
