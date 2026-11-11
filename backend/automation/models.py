"""
Reminders to students (membership ending, fees due, a seat free for someone waiting) and
the settings for every scheduled job. A reminder is either sent automatically by SMS, or
sent by the front desk from their own WhatsApp with the message already written.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from library.models import Branch
from members.models import Membership, Student, WaitlistEntry

# Written to read well for every student: a seat is optional, so only the waiting-list
# message (which is always about one particular seat) mentions a seat number.
DEFAULT_TEXTS = {
    "EXPIRING_SOON": (
        "Hello {name}, your {shift} membership at {library} ends on {date}. "
        "Please renew at the front desk to keep your place. Thank you!"
    ),
    "EXPIRES_TODAY": (
        "Hello {name}, your membership at {library} ends today, {date}. "
        "Please renew today to keep your place. Thank you!"
    ),
    "DUES": (
        "Hello {name}, ₹{amount} of your fees at {library} is still due. "
        "Please pay at the front desk. Thank you!"
    ),
    "WAITLIST": (
        "Hello {name}, good news: seat {seat} is now free in the {shift} shift at {library}. "
        "Visit the front desk soon to take it."
    ),
}


class AutomationSettings(models.Model):
    """One row per branch, created with these defaults the first time it is needed."""

    branch = models.OneToOneField(Branch, on_delete=models.CASCADE, related_name="automation")
    reminders_enabled = models.BooleanField(default=True)
    days_before_expiry = models.PositiveSmallIntegerField(
        default=3, help_text="Remind this many days before a membership ends; 0 turns it off."
    )
    remind_on_expiry_day = models.BooleanField(default=True)
    dues_after_days = models.PositiveSmallIntegerField(
        default=3, help_text="Remind about unpaid fees this many days after the start; 0 = off."
    )
    dues_repeat_days = models.PositiveSmallIntegerField(
        default=7, help_text="Remind again this many days later while fees are still due."
    )
    waitlist_alerts = models.BooleanField(
        default=True, help_text="Tell the first students waiting when a seat is free."
    )
    send_sms = models.BooleanField(
        default=False, help_text="Send by SMS automatically where an approved template exists."
    )
    mark_left_after_days = models.PositiveSmallIntegerField(
        default=0,
        help_text="Mark students as left after this many days without a membership; 0 = never.",
    )
    text_expiring_soon = models.TextField(default=DEFAULT_TEXTS["EXPIRING_SOON"])
    text_expires_today = models.TextField(default=DEFAULT_TEXTS["EXPIRES_TODAY"])
    text_dues = models.TextField(default=DEFAULT_TEXTS["DUES"])
    text_waitlist = models.TextField(default=DEFAULT_TEXTS["WAITLIST"])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "automation settings"

    def __str__(self) -> str:
        return f"Automation for {self.branch}"

    @classmethod
    def for_branch(cls, branch: Branch) -> "AutomationSettings":
        found, _ = cls.objects.get_or_create(branch=branch)
        return found

    def text_for(self, kind: str) -> str:
        return {
            Reminder.Kind.EXPIRING_SOON: self.text_expiring_soon,
            Reminder.Kind.EXPIRES_TODAY: self.text_expires_today,
            Reminder.Kind.DUES: self.text_dues,
            Reminder.Kind.WAITLIST: self.text_waitlist,
        }[kind]


class Reminder(models.Model):
    class Kind(models.TextChoices):
        EXPIRING_SOON = "EXPIRING_SOON", "Ending soon"
        EXPIRES_TODAY = "EXPIRES_TODAY", "Ends today"
        DUES = "DUES", "Fees due"
        WAITLIST = "WAITLIST", "Seat free for a waiting student"

    class Status(models.TextChoices):
        PENDING = "PENDING", "To send"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "SMS failed"
        SKIPPED = "SKIPPED", "Skipped"

    class Channel(models.TextChoices):
        SMS = "SMS", "SMS"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        CALL = "CALL", "Phone call"
        OTHER = "OTHER", "In person or other"

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="reminders")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="reminders")
    membership = models.ForeignKey(
        Membership, on_delete=models.SET_NULL, null=True, blank=True, related_name="reminders"
    )
    waitlist_entry = models.ForeignKey(
        WaitlistEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name="reminders"
    )
    kind = models.CharField(max_length=15, choices=Kind.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    channel = models.CharField(max_length=10, choices=Channel.choices, blank=True)
    for_date = models.DateField(help_text="The day the reminder was due.")
    mobile = models.CharField(max_length=10)
    message = models.TextField()
    details = models.JSONField(default=dict, help_text="Seat, shift, end date or amount due.")
    note = models.CharField(max_length=200, blank=True, help_text="Why it was skipped or failed.")
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-for_date", "kind", "id"]
        indexes = [models.Index(fields=["branch", "status", "for_date"])]
        constraints = [
            # Each membership gets at most one "ending soon" and one "ends today" reminder.
            models.UniqueConstraint(
                fields=["membership", "kind"],
                condition=Q(kind__in=["EXPIRING_SOON", "EXPIRES_TODAY"]),
                name="one_expiry_reminder_per_membership",
            ),
            # The hourly job and someone opening the page can run at the same moment: the
            # database keeps them from making the same reminder twice on one day.
            models.UniqueConstraint(
                fields=["membership", "kind", "for_date"],
                condition=Q(membership__isnull=False),
                name="one_reminder_per_membership_per_day",
            ),
            models.UniqueConstraint(
                fields=["waitlist_entry", "kind", "for_date"],
                condition=Q(waitlist_entry__isnull=False),
                name="one_reminder_per_waitlist_entry_per_day",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} for {self.student} ({self.get_status_display()})"
