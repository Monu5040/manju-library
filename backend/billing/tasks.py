from celery import shared_task

from automation.monitoring import tracked

from . import online


@shared_task
@tracked("online-payments")
def check_online_payments():
    """Every 10 minutes: record online payments whose Razorpay webhook never arrived."""
    return online.check_open_payments()
