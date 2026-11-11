"""
Money that is not a student's fee: expenses (rent, electricity, salaries...) and other
income, plus the daily cash closing. Student fees stay in billing.Payment; the ledger and
the analytics add the two together.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from billing.models import Payment
from library.models import Branch


class LedgerCategory(models.Model):
    class Kind(models.TextChoices):
        EXPENSE = "EXPENSE", "Expense"
        INCOME = "INCOME", "Other income"

    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    # Set on the categories the app itself relies on, such as the Balance Sheet import's.
    code = models.SlugField(max_length=30, unique=True, null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "sort_order", "name"]
        verbose_name_plural = "ledger categories"
        constraints = [
            models.UniqueConstraint(fields=["kind", "name"], name="unique_category_name_per_kind")
        ]

    def __str__(self) -> str:
        return self.name


class LedgerImport(models.Model):
    """One upload of the old Balance Sheet: checked first, then imported; undo within 7 days."""

    class Status(models.TextChoices):
        CHECKED = "CHECKED", "Checked"
        IMPORTED = "IMPORTED", "Imported"
        UNDONE = "UNDONE", "Undone"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="ledger_imports")
    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, db_index=True)
    sheet = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CHECKED)
    plan = models.JSONField(default=dict)
    summary = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    undone_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.file_name} ({self.get_status_display()})"


class LedgerEntry(models.Model):
    """One expense or one piece of other income. Never deleted once entered, only voided."""

    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Entered"
        BALANCE_SHEET = "BALANCE_SHEET", "Old Balance Sheet"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="ledger_entries")
    category = models.ForeignKey(LedgerCategory, on_delete=models.PROTECT, related_name="entries")
    entry_date = models.DateField(default=timezone.localdate)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=10, choices=Payment.Mode.choices, default=Payment.Mode.CASH)
    party = models.CharField(max_length=120, blank=True, help_text="Paid to, or received from.")
    details = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=80, blank=True, help_text="Bill no. or UPI reference.")
    source = models.CharField(max_length=15, choices=Source.choices, default=Source.MANUAL)
    import_batch = models.ForeignKey(
        LedgerImport, on_delete=models.SET_NULL, null=True, blank=True, related_name="entries"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    is_void = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=200, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-entry_date", "-id"]
        verbose_name_plural = "ledger entries"
        indexes = [models.Index(fields=["entry_date"])]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="ledger_amount_positive")
        ]

    def __str__(self) -> str:
        return f"{self.entry_date} {self.category}: ₹{self.amount}"


class CashClosing(models.Model):
    """
    The end-of-day count of the cash drawer. It covers every day since the previous closing,
    so a day without a closing (a holiday) is never lost. Figures are kept as they were.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="cash_closings")
    day = models.DateField()
    period_start = models.DateField(help_text="First day this closing covers.")
    opening = models.DecimalField(max_digits=12, decimal_places=2)
    cash_in = models.DecimalField(max_digits=12, decimal_places=2)
    cash_out = models.DecimalField(max_digits=12, decimal_places=2)
    removed = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Taken out of the drawer: a bank deposit, or handed to the owner.",
    )
    expected = models.DecimalField(max_digits=12, decimal_places=2)
    counted = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=200, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-day"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "day"], name="one_cash_closing_per_day"),
            models.CheckConstraint(
                condition=Q(counted__gte=0) & Q(removed__gte=0) & Q(opening__gte=0),
                name="cash_closing_amounts_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"Cash closing {self.day}"

    @property
    def difference(self):
        return self.counted - self.expected
