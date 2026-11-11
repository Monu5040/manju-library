import pytest
from django_otp.plugins.otp_totp.models import TOTPDevice

from audit.models import AuditLog
from conftest import ADMIN_PASSWORD, current_totp, wrong_totp

pytestmark = pytest.mark.django_db

LOGIN = "/api/auth/admin/login/"
SETUP = "/api/auth/admin/totp/setup/"
VERIFY = "/api/auth/admin/totp/verify/"


def test_first_login_connects_an_authenticator_app(api, super_admin):
    response = api.post(LOGIN, {"identifier": "owner@example.com", "password": ADMIN_PASSWORD})
    assert response.status_code == 200
    assert response.json() == {"next": "setup"}

    # Not signed in until the app is connected.
    assert api.get("/api/auth/me/").status_code == 403

    setup = api.get(SETUP)
    assert setup.status_code == 200
    assert setup.json()["otpauth_uri"].startswith("otpauth://totp/")
    assert len(setup.json()["secret"]) >= 16

    device = TOTPDevice.objects.get(user=super_admin)
    assert device.confirmed is False
    response = api.post(SETUP, {"token": current_totp(device)})
    assert response.status_code == 200
    assert response.json()["role"] == "SUPER_ADMIN"

    device.refresh_from_db()
    assert device.confirmed is True
    assert api.get("/api/auth/me/").status_code == 200
    overview = api.get("/api/admin/overview/")
    assert overview.status_code == 200
    assert overview.json() == {"users": {"students": 0, "staff": 0, "super_admins": 1}}
    assert AuditLog.objects.filter(action="auth.totp_connected", actor=super_admin).exists()


def test_later_logins_ask_for_the_app_code(api, staff):
    device = TOTPDevice.objects.create(user=staff, name="Authenticator app", confirmed=True)

    response = api.post(LOGIN, {"identifier": staff.mobile, "password": ADMIN_PASSWORD})
    assert response.json() == {"next": "verify"}

    assert api.post(VERIFY, {"token": wrong_totp(device)}).status_code == 400
    response = api.post(VERIFY, {"token": current_totp(device)})
    assert response.status_code == 200
    assert response.json()["role"] == "STAFF"
    assert api.get("/api/admin/overview/").status_code == 200


def test_setup_is_refused_once_an_app_is_connected(api, super_admin):
    TOTPDevice.objects.create(user=super_admin, name="Authenticator app", confirmed=True)
    api.post(LOGIN, {"identifier": "owner@example.com", "password": ADMIN_PASSWORD})
    assert api.get(SETUP).status_code == 409


def test_wrong_password_is_rejected_and_logged(api, super_admin):
    response = api.post(LOGIN, {"identifier": "owner@example.com", "password": "nope"})
    assert response.status_code == 400
    assert response.json() == {"non_field_errors": ["Wrong email/mobile or password."]}
    entry = AuditLog.objects.get(action="auth.password_failed")
    assert entry.metadata == {"identifier": "o***@example.com"}


def test_students_cannot_use_password_login(api, student):
    response = api.post(LOGIN, {"identifier": student.mobile, "password": "anything-at-all"})
    assert response.status_code == 400


def test_app_steps_need_the_password_step_first(api):
    assert api.get(SETUP).status_code == 403
    assert api.post(VERIFY, {"token": "123456"}).status_code == 403


def test_password_step_expires(api, super_admin):
    api.post(LOGIN, {"identifier": "owner@example.com", "password": ADMIN_PASSWORD})
    session = api.session
    session["pending_admin_login"]["started"] -= 3600
    session.save()
    assert api.get(SETUP).status_code == 403


def test_password_guesses_per_account_are_rate_limited(api, super_admin):
    for _ in range(10):
        api.post(LOGIN, {"identifier": "owner@example.com", "password": "wrong"})
    response = api.post(LOGIN, {"identifier": "owner@example.com", "password": ADMIN_PASSWORD})
    assert response.status_code == 429
