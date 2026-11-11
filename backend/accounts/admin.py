from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import LoginCode, User


class UserCreateForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("mobile", "full_name", "email", "role")


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreateForm
    list_display = ("full_name", "mobile", "email", "role", "is_active", "last_login")
    list_filter = ("role", "is_active")
    search_fields = ("full_name", "mobile", "email")
    ordering = ("full_name",)
    readonly_fields = ("last_login", "date_joined")
    filter_horizontal = ()
    fieldsets = (
        (None, {"fields": ("mobile", "password")}),
        ("Profile", {"fields": ("full_name", "email")}),
        ("Access", {"fields": ("role", "can_export", "is_active")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "mobile",
                    "full_name",
                    "email",
                    "role",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(LoginCode)
class LoginCodeAdmin(admin.ModelAdmin):
    """Read-only, for support questions such as "I never got my code"."""

    list_display = ("user", "created_at", "expires_at", "attempts", "used_at")
    search_fields = ("user__mobile", "user__full_name")
    exclude = ("code_hash",)
    list_select_related = ("user",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
