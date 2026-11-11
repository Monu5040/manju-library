from django.contrib import admin

from .models import Membership, Student, WaitlistEntry


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("roll_no", "full_name", "mobile", "status", "admission_date")
    list_filter = ("branch", "status", "gender")
    search_fields = ("full_name", "mobile", "father_name", "roll_no")
    exclude = ("aadhaar",)
    readonly_fields = ("aadhaar_last4", "account", "created_by")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("student", "seat", "shift", "start_date", "end_date", "price", "status")
    list_filter = ("branch", "status", "shift")
    search_fields = ("student__full_name", "student__mobile")
    raw_id_fields = ("student", "renewed_from")


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("position", "student", "preferred_shift", "status")
    list_filter = ("branch", "status")
