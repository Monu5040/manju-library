"""
Role checks for API views. Admin and staff sessions only exist after the authenticator-app
step, and these checks also confirm that step (is_verified) on every request.
"""

from rest_framework.permissions import BasePermission

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
