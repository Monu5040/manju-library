"""One-time SMS login codes for students."""

import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import LoginCode, User


def _hash(user_id: int, code: str) -> str:
    message = f"{user_id}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def issue_code(user: User) -> str:
    """Create a fresh 6-digit code for the user and retire any earlier unused ones."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    with transaction.atomic():
        LoginCode.objects.filter(user=user, used_at__isnull=True).delete()
        LoginCode.objects.create(
            user=user,
            code_hash=_hash(user.pk, code),
            expires_at=timezone.now() + settings.LOGIN_CODE_TTL,
        )
    return code


def verify_code(user: User, code: str) -> bool:
    """
    True when `code` matches the user's latest live code. Each code allows a limited number
    of attempts and works once.
    """
    now = timezone.now()
    with transaction.atomic():
        login_code = (
            LoginCode.objects.select_for_update()
            .filter(user=user, used_at__isnull=True, expires_at__gt=now)
            .order_by("-created_at")
            .first()
        )
        if login_code is None or login_code.attempts >= settings.LOGIN_CODE_MAX_ATTEMPTS:
            return False
        login_code.attempts += 1
        matched = hmac.compare_digest(login_code.code_hash, _hash(user.pk, code))
        if matched:
            login_code.used_at = now
        login_code.save(update_fields=["attempts", "used_at"])
        return matched
