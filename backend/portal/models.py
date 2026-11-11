from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from library.models import Branch


class NoticeQuerySet(models.QuerySet):
    def live(self, day=None):
        day = day or timezone.localdate()
        return self.filter(starts_on__lte=day).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=day))


class Notice(models.Model):
    """A message for students on the portal: a holiday, a rule, a fee change."""

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="notices")
    title = models.CharField(max_length=120)
    body = models.TextField(max_length=2000)
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField(null=True, blank=True, help_text="Leave empty to keep showing it.")
    is_pinned = models.BooleanField(default=False, help_text="Shown first.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = NoticeQuerySet.as_manager()

    class Meta:
        ordering = ["-is_pinned", "-starts_on", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_on__isnull=True) | Q(ends_on__gte=models.F("starts_on")),
                name="notice_ends_after_start",
            )
        ]

    def __str__(self) -> str:
        return self.title
