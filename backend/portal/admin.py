from django.contrib import admin

from .models import Notice


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ("title", "branch", "starts_on", "ends_on", "is_pinned")
    list_filter = ("branch", "is_pinned")
