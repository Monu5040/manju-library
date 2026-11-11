from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from automation.monitoring import tracked

from .models import LoginCode


@shared_task
@tracked("login-code-cleanup")
def purge_expired_login_codes() -> dict:
    """Delete login codes that expired more than a day ago."""
    cutoff = timezone.now() - timedelta(days=1)
    deleted, _ = LoginCode.objects.filter(expires_at__lt=cutoff).delete()
    return {"deleted": deleted}
