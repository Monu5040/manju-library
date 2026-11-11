from django.contrib import admin

from .models import Branch, Plan, Seat, Shift


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "allow_seat_sharing", "is_active")


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("name", "branch", "start_time", "end_time", "is_active")
    list_filter = ("branch", "is_active")


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ("number", "branch", "label", "is_active")
    list_filter = ("branch", "is_active")


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "branch", "duration_months", "shift", "price", "is_active")
    list_filter = ("branch", "duration_months", "is_active")
