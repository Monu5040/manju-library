import pytest
from django.core.cache import cache
from django_otp.oath import totp
from rest_framework.test import APIClient

from accounts.models import Role, User
from core.sms import LocmemSMSBackend

ADMIN_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(autouse=True)
def _isolate():
    cache.clear()
    LocmemSMSBackend.outbox.clear()
    yield
    cache.clear()
    LocmemSMSBackend.outbox.clear()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def student(db):
    return User.objects.create_user("9876543210", full_name="Asha Kumari")


@pytest.fixture
def super_admin(db):
    return User.objects.create_superuser(
        "9123456780", ADMIN_PASSWORD, full_name="Library Owner", email="owner@example.com"
    )


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        "9123456781",
        ADMIN_PASSWORD,
        full_name="Front Desk",
        email="desk@example.com",
        role=Role.STAFF,
    )


def current_totp(device) -> str:
    return f"{totp(device.bin_key, device.step, device.t0, device.digits, device.drift):06d}"


def wrong_totp(device) -> str:
    return f"{(int(current_totp(device)) + 1) % 1_000_000:06d}"


def last_sms_code() -> str:
    return LocmemSMSBackend.outbox[-1].text.split()[0]


# ---------------------------------------------------------------------------
# Library setup (Phase 1)
# ---------------------------------------------------------------------------

from datetime import time  # noqa: E402

from django_otp import DEVICE_ID_SESSION_KEY  # noqa: E402
from django_otp.plugins.otp_totp.models import TOTPDevice  # noqa: E402

from core.validators import verhoeff_check_digit  # noqa: E402


def valid_aadhaar(first_eleven: str = "23456789012") -> str:
    """A made-up number that passes the Aadhaar checksum (never a real person's)."""
    return first_eleven + verhoeff_check_digit(first_eleven)


def verified_client(user) -> APIClient:
    """A signed-in client that has passed the authenticator-app step."""
    device = TOTPDevice.objects.create(user=user, name="test app", confirmed=True)
    client = APIClient()
    client.force_login(user)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return client


@pytest.fixture
def branch(db):
    from library.models import Branch

    return Branch.objects.get(code="main")


@pytest.fixture
def shifts(branch):
    from library.models import Shift

    return {
        "morning": Shift.objects.create(
            branch=branch, name="Morning", start_time=time(6, 0), end_time=time(10, 0)
        ),
        "day": Shift.objects.create(
            branch=branch, name="Day", start_time=time(10, 15), end_time=time(18, 30)
        ),
        "evening": Shift.objects.create(
            branch=branch, name="Evening", start_time=time(18, 45), end_time=time(22, 45)
        ),
        "night": Shift.objects.create(
            branch=branch, name="Night", start_time=time(22, 45), end_time=time(6, 0)
        ),
    }


@pytest.fixture
def seats(branch):
    from library.models import Seat

    return [Seat.objects.create(branch=branch, number=str(n)) for n in range(1, 6)]


@pytest.fixture
def day_plan(branch, shifts):
    from library.models import Plan

    return Plan.objects.create(
        branch=branch, name="1 month · Day", duration_months=1, shift=shifts["day"], price=450
    )


@pytest.fixture
def owner_api(super_admin):
    return verified_client(super_admin)


@pytest.fixture
def staff_api(staff):
    return verified_client(staff)
