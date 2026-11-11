from django.contrib import admin

from .models import CashClosing, LedgerCategory, LedgerEntry, LedgerImport


@admin.register(LedgerCategory)
class LedgerCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "code", "sort_order", "is_active")
    list_filter = ("kind", "is_active")


class ReadOnlyAdmin(admin.ModelAdmin):
    """Entered, voided and closed through the app (with the audit log), never edited here."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(ReadOnlyAdmin):
    list_display = ("entry_date", "category", "amount", "mode", "source", "is_void")
    list_filter = ("branch", "category__kind", "source", "is_void")
    search_fields = ("details", "party", "reference")


@admin.register(CashClosing)
class CashClosingAdmin(ReadOnlyAdmin):
    list_display = ("day", "opening", "cash_in", "cash_out", "removed", "expected", "counted")
    list_filter = ("branch",)


@admin.register(LedgerImport)
class LedgerImportAdmin(ReadOnlyAdmin):
    list_display = ("file_name", "status", "created_at", "imported_at", "undone_at")
    exclude = ("plan",)
