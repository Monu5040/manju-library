from django.contrib import admin

from .models import AutomationSettings, Reminder


@admin.register(AutomationSettings)
class AutomationSettingsAdmin(admin.ModelAdmin):
    list_display = ("branch", "reminders_enabled", "send_sms", "mark_left_after_days", "updated_at")


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    """Read-only: reminders are made by the scheduled job and handled in the app."""

    list_display = ("for_date", "kind", "student", "status", "channel", "sent_at")
    list_filter = ("branch", "kind", "status", "channel")
    search_fields = ("student__full_name", "mobile")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
