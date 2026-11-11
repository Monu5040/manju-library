import pytest
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts.models import Role, User
from conftest import ADMIN_PASSWORD

pytestmark = pytest.mark.django_db


def test_owner_creates_staff_with_a_strong_password(owner_api, staff_api):
    body = {
        "full_name": "New Desk",
        "mobile": "9123456799",
        "email": "",
        "role": "STAFF",
        "password": "short",
    }
    assert owner_api.post("/api/admin/staff/", body).status_code == 400
    body["password"] = "a-long-enough-password-42"
    created = owner_api.post("/api/admin/staff/", body)
    assert created.status_code == 201, created.json()
    assert "password" not in created.json()
    user = User.objects.get(mobile="9123456799")
    assert user.role == Role.STAFF and user.email is None and user.check_password(body["password"])
    assert staff_api.get("/api/admin/staff/").status_code == 403


def test_owner_cannot_lock_themselves_out(owner_api, super_admin):
    url = f"/api/admin/staff/{super_admin.id}/"
    assert owner_api.patch(url, {"is_active": False}).status_code == 400
    assert owner_api.patch(url, {"role": "STAFF"}).status_code == 400


def test_reset_authenticator_and_export_rights(owner_api, staff):
    TOTPDevice.objects.create(user=staff, name="old phone", confirmed=True)
    response = owner_api.post(f"/api/admin/staff/{staff.id}/reset-authenticator/")
    assert response.status_code == 200
    assert not TOTPDevice.objects.filter(user=staff).exists()
    assert (
        owner_api.patch(f"/api/admin/staff/{staff.id}/", {"can_export": True}).json()["can_export"]
        is True
    )


def test_change_own_password(staff_api, staff):
    url = "/api/auth/password/"
    assert (
        staff_api.post(
            url, {"current_password": "wrong", "new_password": "another-long-password-1"}
        ).status_code
        == 400
    )
    assert (
        staff_api.post(
            url, {"current_password": ADMIN_PASSWORD, "new_password": "password"}
        ).status_code
        == 400
    )
    ok = staff_api.post(
        url, {"current_password": ADMIN_PASSWORD, "new_password": "another-long-password-1"}
    )
    assert ok.status_code == 200
    staff.refresh_from_db()
    assert staff.check_password("another-long-password-1")
    assert staff_api.get("/api/auth/me/").status_code == 200  # still signed in
