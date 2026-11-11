"""Students, their memberships (seat + shift + dates + fee) and the waiting list."""

from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import (
    DateRangeField,
    IntegerRangeField,
    RangeBoundary,
    RangeOperators,
)
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Func, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import mobile_validator
from core.fields import EncryptedTextField
from core.validators import mask_aadhaar
from library.models import Branch, Plan, Seat, Shift, format_minutes, minute_range

MONEY = DecimalField(max_digits=12, decimal_places=2)


class DateRange(Func):
    function = "DATERANGE"
    output_field = DateRangeField()


class MinuteRange(Func):
    function = "INT4RANGE"
    output_field = IntegerRangeField()


class Student(models.Model):
    class Gender(models.TextChoices):
        FEMALE = "F", "Female"
        MALE = "M", "Male"
        OTHER = "O", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        LEFT = "LEFT", "Left the library"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="students")
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profiles",
        help_text="Login account for the student portal; siblings may share one mobile.",
    )
    roll_no = models.PositiveIntegerField()
    full_name = models.CharField(max_length=150)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    father_name = models.CharField(max_length=150, blank=True)
    mobile = models.CharField(max_length=10, validators=[mobile_validator])
    alt_mobile = models.CharField(max_length=10, blank=True, validators=[mobile_validator])
    aadhaar = EncryptedTextField(blank=True, default="")
    aadhaar_last4 = models.CharField(max_length=4, blank=True)
    address = models.TextField(blank=True)
    admission_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["roll_no"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "roll_no"], name="unique_roll_no_per_branch")
        ]
        indexes = [models.Index(fields=["mobile"]), models.Index(fields=["full_name"])]

    def __str__(self) -> str:
        return f"{self.full_name} (roll {self.roll_no})"

    @property
    def aadhaar_masked(self) -> str:
        return mask_aadhaar(self.aadhaar_last4)


class MembershipQuerySet(models.QuerySet):
    def with_totals(self):
        paid = Coalesce(
            Sum("payments__amount", filter=Q(payments__is_void=False)),
            Value(Decimal("0")),
            output_field=MONEY,
        )
        return self.annotate(paid_total=paid).annotate(
            due_total=ExpressionWrapper(
                F("price") - F("discount") - F("paid_total"), output_field=MONEY
            )
        )

    def not_cancelled(self):
        return self.exclude(status=Membership.Status.CANCELLED)

    def current(self, on=None):
        on = on or timezone.localdate()
        return self.not_cancelled().filter(start_date__lte=on, end_date__gte=on)


class Membership(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CANCELLED = "CANCELLED", "Cancelled"

    class State(models.TextChoices):
        UPCOMING = "UPCOMING", "Starts later"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="memberships")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="memberships")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, null=True, blank=True)
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, null=True, blank=True)
    custom_start_time = models.TimeField(
        null=True, blank=True, help_text="For a custom time slot instead of a shift."
    )
    custom_end_time = models.TimeField(null=True, blank=True)
    start_minute = models.PositiveIntegerField(editable=False)
    end_minute = models.PositiveIntegerField(editable=False)
    seat = models.ForeignKey(
        Seat, on_delete=models.PROTECT, null=True, blank=True, related_name="memberships"
    )
    start_date = models.DateField()
    end_date = models.DateField(help_text="Last day of the membership (the expiry date).")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    renewed_from = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="renewals"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = MembershipQuerySet.as_manager()

    class Meta:
        ordering = ["-start_date", "-id"]
        indexes = [models.Index(fields=["end_date"]), models.Index(fields=["start_date"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")), name="membership_ends_after_start"
            ),
            models.CheckConstraint(
                condition=Q(price__gte=0) & Q(discount__gte=0) & Q(discount__lte=F("price")),
                name="membership_amounts_valid",
            ),
            # The database itself refuses two live memberships on one seat whose dates and
            # times of day overlap. Overnight wrap-around is checked in members.services.
            ExclusionConstraint(
                name="no_double_booked_seat",
                expressions=[
                    ("seat", RangeOperators.EQUAL),
                    (
                        DateRange("start_date", "end_date", RangeBoundary(inclusive_upper=True)),
                        RangeOperators.OVERLAPS,
                    ),
                    (MinuteRange("start_minute", "end_minute"), RangeOperators.OVERLAPS),
                ],
                condition=Q(seat__isnull=False) & ~Q(status="CANCELLED"),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student.full_name}: {self.start_date} to {self.end_date}"

    def save(self, *args, **kwargs):
        self.start_minute, self.end_minute = self.compute_minute_range()
        super().save(*args, **kwargs)

    def compute_minute_range(self) -> tuple[int, int]:
        if self.custom_start_time and self.custom_end_time:
            return minute_range(self.custom_start_time, self.custom_end_time)
        if self.shift_id:
            return self.shift.minute_range
        raise ValueError("A membership needs a shift or a custom time slot.")

    @property
    def time_label(self) -> str:
        start, end = self.compute_minute_range()
        return f"{format_minutes(start)} – {format_minutes(end)}"

    def state_on(self, day=None) -> str:
        day = day or timezone.localdate()
        if self.status == self.Status.CANCELLED:
            return self.State.CANCELLED
        if day < self.start_date:
            return self.State.UPCOMING
        if day > self.end_date:
            return self.State.EXPIRED
        return self.State.ACTIVE

    @property
    def state(self) -> str:
        return self.state_on()

    @property
    def days_left(self) -> int:
        return (self.end_date - timezone.localdate()).days

    @property
    def net_fee(self) -> Decimal:
        return self.price - self.discount


class WaitlistEntry(models.Model):
    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        SEATED = "SEATED", "Given a seat"
        REMOVED = "REMOVED", "Removed"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="waitlist")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="waitlist_entries")
    preferred_shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WAITING)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at"]
        verbose_name_plural = "waiting list entries"

    def __str__(self) -> str:
        return f"W{self.position}: {self.student.full_name}"
