from django.contrib import admin

from .models import Payment, ReceiptSequence


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Read-only here: payments are recorded and voided through the app, never edited."""

    list_display = ("receipt_no", "student", "amount", "mode", "paid_on", "is_void")
    list_filter = ("branch", "mode", "is_void")
    search_fields = ("receipt_no", "student__full_name", "student__mobile")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReceiptSequence)
class ReceiptSequenceAdmin(admin.ModelAdmin):
    list_display = ("branch", "next_number")
