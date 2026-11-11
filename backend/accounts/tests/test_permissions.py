from types import SimpleNamespace

import pytest

from accounts.models import Role, User
from accounts.permissions import CanExport

pytestmark = pytest.mark.django_db


def test_anonymous_visitors_see_nothing_private(api):
    assert api.get("/api/auth/me/").status_code == 403
    assert api.get("/api/admin/overview/").status_code == 403


def test_students_cannot_open_the_admin_area(api, student):
    api.force_login(student)
    assert api.get("/api/auth/me/").status_code == 200
    assert api.get("/api/admin/overview/").status_code == 403


def test_admin_session_without_the_app_step_is_refused(api, staff):
    # A session made without the authenticator step (for example by a bug elsewhere)
    # must not reach admin data.
    api.force_login(staff)
    assert api.get("/api/admin/overview/").status_code == 403
    assert api.get("/api/auth/me/").status_code == 403


def test_logout_ends_the_session(api, student):
    api.force_login(student)
    assert api.post("/api/auth/logout/").status_code == 204
    assert api.get("/api/auth/me/").status_code == 403


@pytest.mark.parametrize(
    ("role", "can_export", "expected"),
    [
        (Role.SUPER_ADMIN, False, True),
        (Role.STAFF, True, True),
        (Role.STAFF, False, False),
        (Role.STUDENT, True, False),
    ],
)
def test_export_permission(role, can_export, expected):
    user = User(mobile="9000000009", full_name="X", role=role, can_export=can_export)
    user.is_verified = lambda: True
    request = SimpleNamespace(user=user)
    assert CanExport().has_permission(request, None) is expected
