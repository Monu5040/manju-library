from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """
    Who did what, when, from where, with the values before and after. Rows are only ever
    added: nothing in the app updates or deletes them.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    action = models.CharField(max_length=64, db_index=True)
    entity = models.CharField(max_length=64, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=256, blank=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-at"]
        indexes = [models.Index(fields=["entity", "entity_id"])]

    def __str__(self) -> str:
        return f"{self.at:%Y-%m-%d %H:%M} {self.action}"
