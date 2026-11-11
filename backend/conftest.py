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
