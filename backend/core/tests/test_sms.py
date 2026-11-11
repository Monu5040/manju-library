import json
import urllib.error
from unittest import mock

import pytest
from django.core.exceptions import ImproperlyConfigured

from core import sms
from core.checks import deployment_settings_check


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode()

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def msg91(settings):
    settings.SMS_BACKEND = "core.sms.Msg91SMSBackend"
    settings.MSG91_AUTH_KEY = "test-auth-key"
    settings.MSG91_OTP_TEMPLATE_ID = "tmpl-123"
    settings.MSG91_CODE_VARIABLE = "otp"
    settings.MSG91_MINUTES_VARIABLE = "minutes"
    return settings


def test_msg91_request_matches_the_flow_api(msg91):
    with mock.patch(
        "urllib.request.urlopen", return_value=FakeResponse({"type": "success"})
    ) as urlopen:
        sms.send_login_code("9876543210", "123456", 5)
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://control.msg91.com/api/v5/flow/"
    assert request.get_method() == "POST"
    assert request.get_header("Authkey") == "test-auth-key"
    assert json.loads(request.data) == {
        "template_id": "tmpl-123",
        "short_url": "0",
        "recipients": [{"mobiles": "919876543210", "otp": "123456", "minutes": "5"}],
    }


def test_msg91_failures_raise_sms_error(msg91):
    with mock.patch(
        "urllib.request.urlopen",
        return_value=FakeResponse({"type": "error", "message": "Template not approved"}),
    ):
        with pytest.raises(sms.SMSError, match="Template not approved"):
            sms.send_login_code("9876543210", "123456", 5)
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
        with pytest.raises(sms.SMSError, match="could not be reached"):
            sms.send_login_code("9876543210", "123456", 5)


def test_msg91_needs_its_keys(settings):
    settings.SMS_BACKEND = "core.sms.Msg91SMSBackend"
    settings.MSG91_AUTH_KEY = ""
    with pytest.raises(ImproperlyConfigured):
        sms.get_backend()
    settings.IS_DEPLOYED = True
    settings.DEBUG = False
    settings.FIELD_ENCRYPTION_KEYS = ["MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE="]
    assert {e.id for e in deployment_settings_check(None)} == {"core.E005"}


@pytest.mark.django_db
def test_student_sees_a_friendly_message_when_sms_fails(api, student, msg91):
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        response = api.post("/api/auth/otp/request/", {"mobile": student.mobile})
    assert response.status_code == 503
    assert "try again in a minute" in response.json()["detail"]
