from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import LoginCode
from audit.models import AuditLog
from conftest import last_sms_code
from core.sms import LocmemSMSBackend

pytestmark = pytest.mark.django_db

REQUEST = "/api/auth/otp/request/"
VERIFY = "/api/auth/otp/verify/"


def test_registered_student_gets_a_code_and_signs_in(api, student):
    response = api.post(REQUEST, {"mobile": "+91 98765 43210"})
    assert response.status_code == 202
    assert LocmemSMSBackend.outbox[-1].mobile == "9876543210"

    response = api.post(VERIFY, {"mobile": "9876543210", "code": last_sms_code()})
    assert response.status_code == 200
    assert response.json() == {
        "id": student.pk,
        "full_name": "Asha Kumari",
        "mobile": "98XXXXXX10",
        "email": None,
        "role": "STUDENT",
        "can_export": False,
    }

    me = api.get("/api/auth/me/")
    assert me.status_code == 200
    assert me.json()["full_name"] == "Asha Kumari"
    assert AuditLog.objects.filter(action="auth.login", actor=student).exists()


def test_unknown_number_gets_the_same_answer_and_no_sms(api):
    response = api.post(REQUEST, {"mobile": "9999999999"})
    assert response.status_code == 202
    assert LocmemSMSBackend.outbox == []


def test_only_a_hash_of_the_code_is_stored(api, student):
    api.post(REQUEST, {"mobile": student.mobile})
    stored = LoginCode.objects.get(user=student)
    assert last_sms_code() not in stored.code_hash
    assert len(stored.code_hash) == 64


def test_attempts_are_limited_per_code(api, student, settings):
    api.post(REQUEST, {"mobile": student.mobile})
    code = last_sms_code()
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(settings.LOGIN_CODE_MAX_ATTEMPTS):
        assert api.post(VERIFY, {"mobile": student.mobile, "code": wrong}).status_code == 400
    # Even the right code fails once the attempts are used up.
    assert api.post(VERIFY, {"mobile": student.mobile, "code": code}).status_code == 400


def test_expired_code_is_rejected(api, student):
    api.post(REQUEST, {"mobile": student.mobile})
    LoginCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    response = api.post(VERIFY, {"mobile": student.mobile, "code": last_sms_code()})
    assert response.status_code == 400
    assert "code" in response.json()


def test_code_works_only_once(api, student):
    api.post(REQUEST, {"mobile": student.mobile})
    code = last_sms_code()
    assert api.post(VERIFY, {"mobile": student.mobile, "code": code}).status_code == 200
    api.post("/api/auth/logout/")
    assert api.post(VERIFY, {"mobile": student.mobile, "code": code}).status_code == 400


def test_a_new_code_replaces_the_previous_one(api, student):
    api.post(REQUEST, {"mobile": student.mobile})
    first = last_sms_code()
    api.post(REQUEST, {"mobile": student.mobile})
    second = last_sms_code()
    if first != second:
        assert api.post(VERIFY, {"mobile": student.mobile, "code": first}).status_code == 400
    assert api.post(VERIFY, {"mobile": student.mobile, "code": second}).status_code == 200


def test_staff_cannot_use_sms_login(api, staff):
    assert api.post(REQUEST, {"mobile": staff.mobile}).status_code == 202
    assert LocmemSMSBackend.outbox == []


def test_invalid_mobile_is_rejected(api):
    response = api.post(REQUEST, {"mobile": "12345"})
    assert response.status_code == 400
    assert "mobile" in response.json()


def test_codes_per_number_are_rate_limited(api, student):
    for _ in range(5):
        assert api.post(REQUEST, {"mobile": student.mobile}).status_code == 202
    assert api.post(REQUEST, {"mobile": student.mobile}).status_code == 429
