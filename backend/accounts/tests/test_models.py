from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import LoginCode, Role, User, normalize_mobile
from accounts.tasks import purge_expired_login_codes


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9876543210", "9876543210"),
        ("+91 98765 43210", "9876543210"),
        ("919876543210", "9876543210"),
        ("09876543210", "9876543210"),
        (9876543210, "9876543210"),
        ("98765-43210", "9876543210"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_mobile(raw, expected):
    assert normalize_mobile(raw) == expected


@pytest.mark.django_db
def test_roles_drive_back_office_access(super_admin, staff, student):
    assert super_admin.is_superuser and super_admin.is_staff
    assert not staff.is_superuser and not staff.is_staff
    assert not student.is_staff
    assert not student.has_usable_password()


@pytest.mark.django_db
def test_role_change_updates_superuser_flag(staff):
    staff.role = Role.SUPER_ADMIN
    staff.save()
    staff.refresh_from_db()
    assert staff.is_superuser


@pytest.mark.django_db
def test_blank_email_is_stored_as_null_so_many_students_can_have_none():
    User.objects.create_user("9000000011", full_name="A", email="")
    User.objects.create_user("9000000012", full_name="B", email="")
    assert User.objects.filter(email__isnull=True).count() == 2


@pytest.mark.django_db
def test_purge_task_removes_old_codes(student):
    old = LoginCode.objects.create(
        user=student, code_hash="x" * 64, expires_at=timezone.now() - timedelta(days=2)
    )
    fresh = LoginCode.objects.create(
        user=student, code_hash="y" * 64, expires_at=timezone.now() + timedelta(minutes=5)
    )
    assert purge_expired_login_codes() == 1
    assert not LoginCode.objects.filter(pk=old.pk).exists()
    assert LoginCode.objects.filter(pk=fresh.pk).exists()
