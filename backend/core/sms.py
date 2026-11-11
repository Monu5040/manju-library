"""
SMS behind a small backend interface, chosen by settings.SMS_BACKEND.

- ConsoleSMSBackend: development (and staging until a provider is set up). Logs the text.
- LocmemSMSBackend: tests. Keeps messages in `outbox`.
- Msg91SMSBackend: MSG91's Flow API. Indian SMS must use a DLT-approved template, so the
  login code is sent as a template variable rather than as free text.
"""

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class SMSError(Exception):
    """The provider did not accept the message."""


@dataclass(frozen=True)
class SMSMessage:
    mobile: str
    text: str


def login_code_text(code: str, minutes: int) -> str:
    return (
        f"{code} is your Manju Library login code. It expires in {minutes} minutes. "
        "Do not share it with anyone."
    )


class BaseSMSBackend:
    def send(self, message: SMSMessage) -> None:
        raise NotImplementedError

    def send_login_code(self, mobile: str, code: str, minutes: int) -> None:
        self.send(SMSMessage(mobile=mobile, text=login_code_text(code, minutes)))

    def can_send_reminder(self, kind: str) -> bool:
        """Whether reminders of this kind really reach the student (the console only logs)."""
        return False

    def send_reminder(self, mobile: str, kind: str, text: str, variables: dict) -> None:
        self.send(SMSMessage(mobile=mobile, text=text))


class ConsoleSMSBackend(BaseSMSBackend):
    def send(self, message: SMSMessage) -> None:
        logger.warning("DEV SMS to %s: %s", message.mobile, message.text)


class LocmemSMSBackend(BaseSMSBackend):
    outbox: list[SMSMessage] = []

    def send(self, message: SMSMessage) -> None:
        LocmemSMSBackend.outbox.append(message)

    def can_send_reminder(self, kind: str) -> bool:
        return True


class Msg91SMSBackend(BaseSMSBackend):
    """
    MSG91 Flow API: POST {"template_id", "recipients": [{"mobiles": "91XXXXXXXXXX", <var>: code}]}
    with the auth key in the `authkey` header. Settings:
      MSG91_AUTH_KEY, MSG91_OTP_TEMPLATE_ID   required
      MSG91_CODE_VARIABLE (default "otp")     the template's variable for the code
      MSG91_MINUTES_VARIABLE (optional)       the template's variable for the minutes
      MSG91_API_URL (default https://control.msg91.com/api/v5/flow/)
      MSG91_TEMPLATE_<KIND>                   reminder templates, see MSG91_REMINDER_TEMPLATES
    """

    def __init__(self):
        self.auth_key = settings.MSG91_AUTH_KEY
        self.template_id = settings.MSG91_OTP_TEMPLATE_ID
        if not (self.auth_key and self.template_id):
            raise ImproperlyConfigured("MSG91_AUTH_KEY and MSG91_OTP_TEMPLATE_ID must be set.")

    def send(self, message: SMSMessage) -> None:
        raise SMSError("Free text cannot be sent: Indian SMS needs an approved template.")

    def send_login_code(self, mobile: str, code: str, minutes: int) -> None:
        recipient = {"mobiles": f"91{mobile}", settings.MSG91_CODE_VARIABLE: code}
        if settings.MSG91_MINUTES_VARIABLE:
            recipient[settings.MSG91_MINUTES_VARIABLE] = str(minutes)
        self._flow(self.template_id, recipient)

    def can_send_reminder(self, kind: str) -> bool:
        return bool(settings.MSG91_REMINDER_TEMPLATES.get(kind))

    def send_reminder(self, mobile: str, kind: str, text: str, variables: dict) -> None:
        """The approved template holds the wording; the variables fill it in."""
        template = settings.MSG91_REMINDER_TEMPLATES.get(kind)
        if not template:
            raise SMSError("There is no approved SMS template for this kind of reminder.")
        self._flow(template, {"mobiles": f"91{mobile}", **variables})

    def _flow(self, template_id: str, recipient: dict) -> None:
        body = json.dumps(
            {"template_id": template_id, "short_url": "0", "recipients": [recipient]}
        ).encode()
        request = urllib.request.Request(  # noqa: S310 (fixed https URL from settings)
            settings.MSG91_API_URL,
            data=body,
            method="POST",
            headers={
                "authkey": self.auth_key,
                "accept": "application/json",
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                reply = json.loads(response.read() or b"{}")
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise SMSError(f"MSG91 could not be reached: {exc}") from exc
        if reply.get("type") != "success":
            raise SMSError(f"MSG91 refused the message: {reply.get('message', reply)}")


def get_backend() -> BaseSMSBackend:
    return import_string(settings.SMS_BACKEND)()


def send_sms(mobile: str, text: str) -> None:
    get_backend().send(SMSMessage(mobile=mobile, text=text))


def send_login_code(mobile: str, code: str, minutes: int) -> None:
    get_backend().send_login_code(mobile, code, minutes)


def reminder_ready(kind: str) -> bool:
    """Whether a reminder of this kind can go out by SMS without anyone's help."""
    try:
        return get_backend().can_send_reminder(kind)
    except ImproperlyConfigured:
        return False


def send_reminder(mobile: str, kind: str, text: str, variables: dict) -> None:
    get_backend().send_reminder(mobile, kind, text, variables)
