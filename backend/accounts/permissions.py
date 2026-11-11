"""
Role checks for API views. Admin and staff sessions only exist after the authenticator-app
step, and these checks also confirm that step (is_verified) on every request.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Role


def _verified(user) -> bool:
    is_verified = getattr(user, "is_verified", None)
    return bool(is_verified and is_verified())


class IsStudent(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.STUDENT)


class IsAdminOrStaff(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin_role and _verified(user))


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.role == Role.SUPER_ADMIN and _verified(user)
        )


class CanExport(BasePermission):
    """Super Admins, and staff who have been given export rights."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.may_export and _verified(user))


class AdminArea(BasePermission):
    """
    The admin panel: Super Admins may do everything. Staff may read everything and perform
    only the actions a view lists in `staff_actions` (for example create or renew).
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_admin_role and _verified(user)):
            return False
        if user.role == Role.SUPER_ADMIN:
            return True
        if request.method in SAFE_METHODS:
            return True
        action = getattr(view, "action", None)
        if action is not None:
            return action in getattr(view, "staff_actions", set())
        return request.method in getattr(view, "staff_methods", set())
