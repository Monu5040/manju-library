from django.contrib import admin

from .models import ImportJob


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ("file_name", "status", "created_by", "created_at", "imported_at")
    list_filter = ("status",)
    exclude = ("content",)
    readonly_fields = ("summary", "mapping", "options")
