"""
SMS sending behind a small backend interface, configured by settings.SMS_BACKEND.

- ConsoleSMSBackend: development only. Logs the message so a developer can read the code.
- LocmemSMSBackend: tests. Keeps messages in `outbox`.
- A provider backend (MSG91, Gupshup) is added once the DLT-registered sender ID and
  templates are approved. Deployed environments refuse to start with the console backend.
"""

import logging
from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SMSMessage:
    mobile: str
    text: str


class BaseSMSBackend:
    def send(self, message: SMSMessage) -> None:
        raise NotImplementedError


class ConsoleSMSBackend(BaseSMSBackend):
    def send(self, message: SMSMessage) -> None:
        logger.warning("DEV SMS to %s: %s", message.mobile, message.text)


class LocmemSMSBackend(BaseSMSBackend):
    outbox: list[SMSMessage] = []

    def send(self, message: SMSMessage) -> None:
        LocmemSMSBackend.outbox.append(message)


def get_backend() -> BaseSMSBackend:
    return import_string(settings.SMS_BACKEND)()


def send_sms(mobile: str, text: str) -> None:
    get_backend().send(SMSMessage(mobile=mobile, text=text))
