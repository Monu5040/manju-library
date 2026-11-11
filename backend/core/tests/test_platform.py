import pytest
from rest_framework.test import APIClient

from core.checks import deployment_settings_check


@pytest.mark.django_db
def test_health(api):
    response = api.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_login_endpoints_require_the_csrf_token(student):
    client = APIClient(enforce_csrf_checks=True)
    response = client.post("/api/auth/otp/request/", {"mobile": student.mobile}, format="json")
    assert response.status_code == 403
    assert "Security check failed" in response.json()["detail"]

    client.get("/api/auth/csrf/")
    token = client.cookies["csrftoken"].value
    response = client.post(
        "/api/auth/otp/request/",
        {"mobile": student.mobile},
        format="json",
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 202


def test_deployment_checks_catch_unsafe_settings(settings):
    settings.IS_DEPLOYED = True
    settings.DEBUG = False
    settings.FIELD_ENCRYPTION_KEYS = []
    settings.SMS_BACKEND = "core.sms.ConsoleSMSBackend"
    ids = {error.id for error in deployment_settings_check(None)}
    assert ids == {"core.E001", "core.E003"}


def test_deployment_checks_pass_with_safe_settings(settings):
    from core.crypto import generate_key

    settings.IS_DEPLOYED = True
    settings.DEBUG = False
    settings.FIELD_ENCRYPTION_KEYS = [generate_key()]
    settings.SMS_BACKEND = "core.sms.SomeProviderBackend"
    assert deployment_settings_check(None) == []


def test_local_environments_skip_deployment_checks(settings):
    settings.IS_DEPLOYED = False
    settings.FIELD_ENCRYPTION_KEYS = []
    assert deployment_settings_check(None) == []


def test_console_sms_is_allowed_in_staging_only_by_opt_in(settings):
    from core.crypto import generate_key

    settings.IS_DEPLOYED = True
    settings.DEBUG = False
    settings.FIELD_ENCRYPTION_KEYS = [generate_key()]
    settings.SMS_BACKEND = "core.sms.ConsoleSMSBackend"
    settings.SMS_CONSOLE_ALLOWED = True

    settings.ENVIRONMENT = "staging"
    assert deployment_settings_check(None) == []

    settings.ENVIRONMENT = "production"
    assert {error.id for error in deployment_settings_check(None)} == {"core.E003"}
