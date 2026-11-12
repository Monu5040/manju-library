"""Branches, shifts, seats and plans: how a library is set up."""

import re
from datetime import time

from django.db import models

MINUTES_PER_DAY = 24 * 60


def minutes_of(value: time) -> int:
    return value.hour * 60 + value.minute


def minute_range(start: time, end: time) -> tuple[int, int]:
    """
    A shift's time of day as [start, end) minutes after midnight. An end at or before the
    start means the shift runs past midnight, so the end moves to the next day (+1440).
    """
    start_minute, end_minute = minutes_of(start), minutes_of(end)
    if end_minute <= start_minute:
        end_minute += MINUTES_PER_DAY
    return start_minute, end_minute


def ranges_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    """True when two daily time ranges overlap, including across midnight."""
    for shift in (0, MINUTES_PER_DAY, -MINUTES_PER_DAY):
        if a[0] < b[1] + shift and b[0] + shift < a[1]:
            return True
    return False


def format_minutes(minute: int) -> str:
    minute %= MINUTES_PER_DAY
    hour, minute = divmod(minute, 60)
    suffix = "AM" if hour < 12 else "PM"
    return f"{(hour % 12) or 12}:{minute:02d} {suffix}"


class Branch(models.Model):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=20, unique=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    allow_seat_sharing = models.BooleanField(
        default=True,
        help_text="Let one seat go to different students in shifts that do not overlap.",
    )
    allow_online_payments = models.BooleanField(
        default=False,
        help_text="Let students renew and pay dues online through Razorpay.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "branches"

    def __str__(self) -> str:
        return self.name


class Shift(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="shifts")
    name = models.CharField(max_length=60)
    start_time = models.TimeField()
    end_time = models.TimeField(help_text="Earlier than the start time for overnight shifts.")
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "start_time"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "name"], name="unique_shift_name_per_branch")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.time_label})"

    @property
    def minute_range(self) -> tuple[int, int]:
        return minute_range(self.start_time, self.end_time)

    @property
    def hours(self) -> float:
        start, end = self.minute_range
        return round((end - start) / 60, 2)

    @property
    def time_label(self) -> str:
        start, end = self.minute_range
        return f"{format_minutes(start)} – {format_minutes(end)}"


class Seat(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="seats")
    number = models.CharField(max_length=10)
    label = models.CharField(max_length=60, blank=True)
    sort_key = models.PositiveIntegerField(default=0, editable=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_key", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "number"], name="unique_seat_number_per_branch"
            )
        ]

    def __str__(self) -> str:
        return f"Seat {self.number}"

    def save(self, *args, **kwargs):
        digits = re.sub(r"\D", "", self.number)
        self.sort_key = int(digits) if digits else 0
        super().save(*args, **kwargs)


class Plan(models.Model):
    DURATION_CHOICES = [
        (1, "1 month"),
        (2, "2 months"),
        (3, "3 months"),
        (6, "6 months"),
        (12, "12 months"),
    ]

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="plans")
    name = models.CharField(max_length=80)
    duration_months = models.PositiveSmallIntegerField(choices=DURATION_CHOICES)
    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="plans",
        help_text="Leave empty for a plan that fits any shift.",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["duration_months", "price"]

    def __str__(self) -> str:
        return f"{self.name} (₹{self.price})"
