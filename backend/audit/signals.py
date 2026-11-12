"""Back-office (Django admin) sign-ins go to the audit log too; the API audits its own."""

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from . import services as audit

BACKOFFICE = "/backoffice/"


def _from_backoffice(request) -> bool:
    return request is not None and request.path.startswith(BACKOFFICE)


def _masked(identifier: str) -> str:
    identifier = str(identifier or "")
    if "@" in identifier:
        name, _, domain = identifier.partition("@")
        return f"{name[:1]}***@{domain}"
    digits = "".join(ch for ch in identifier if ch.isdigit())
    return f"{digits[:2]}XXXXXX{digits[-2:]}" if len(digits) >= 4 else "unknown"


@receiver(user_logged_in)
def backoffice_login(sender, request, user, **kwargs):
    if _from_backoffice(request):
        audit.record(request, "backoffice.login", actor=user, entity="user", entity_id=user.pk)


@receiver(user_login_failed)
def backoffice_login_failed(sender, credentials, request=None, **kwargs):
    if _from_backoffice(request):
        audit.record(
            request,
            "backoffice.login_failed",
            metadata={"identifier": _masked(credentials.get("username", ""))},
        )
