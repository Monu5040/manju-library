from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import LoginCode


@shared_task
def purge_expired_login_codes() -> int:
    """Delete login codes that expired more than a day ago."""
    cutoff = timezone.now() - timedelta(days=1)
    deleted, _ = LoginCode.objects.filter(expires_at__lt=cutoff).delete()
    return deleted
