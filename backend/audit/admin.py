from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("at", "action", "actor", "entity", "entity_id", "ip")
    list_filter = ("action", "entity")
    search_fields = ("action", "entity", "entity_id", "actor__full_name", "actor__mobile")
    date_hierarchy = "at"
    list_select_related = ("actor",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
