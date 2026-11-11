from django.conf import settings
from django.db import models

from library.models import Branch


class ImportJob(models.Model):
    class Status(models.TextChoices):
        CHECKED = "CHECKED", "Checked"
        IMPORTED = "IMPORTED", "Imported"
        UNDONE = "UNDONE", "Undone"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="import_jobs")
    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, db_index=True)
    file_format = models.CharField(max_length=10)
    # The uploaded file, kept so the check can be re-run with other settings; purged later.
    content = models.BinaryField(null=True, blank=True)
    sheet = models.CharField(max_length=120, blank=True)
    header_row = models.PositiveIntegerField(default=0)
    mapping = models.JSONField(default=dict)
    options = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CHECKED)
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


class ImportRow(models.Model):
    class Result(models.TextChoices):
        READY = "READY", "Ready to import"
        ERROR = "ERROR", "Has errors"
        IMPORTED = "IMPORTED", "Imported"
        SKIPPED = "SKIPPED", "Skipped"

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField(help_text="Row number as shown in the spreadsheet.")
    raw = models.JSONField(default=dict, help_text="The row as it read in the file.")
    values = models.JSONField(default=dict, help_text="Clean values, ready to save.")
    result = models.CharField(max_length=10, choices=Result.choices)
    errors = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    created = models.JSONField(default=dict, help_text="Records this row created, for undo.")

    class Meta:
        ordering = ["row_number"]

    def __str__(self) -> str:
        return f"Row {self.row_number}: {self.result}"
