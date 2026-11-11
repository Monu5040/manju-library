import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthView(APIView):
    """Liveness and database check for Nginx, Docker and uptime monitoring."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            logger.exception("Health check: database unavailable")
            return Response({"status": "error", "database": "unavailable"}, status=503)
        # Redis holds the rate limits and the job queue: without it sign-ins fail.
        try:
            cache.set("health-check", "ok", 10)
            if cache.get("health-check") != "ok":
                raise RuntimeError("Redis did not return the stored value")
        except Exception:
            logger.exception("Health check: Redis unavailable")
            return Response({"status": "error", "cache": "unavailable"}, status=503)
        return Response({"status": "ok"})


def csrf_failure(request, reason=""):
    """JSON instead of Django's HTML page, so the React app can show a clear message."""
    logger.warning("CSRF check failed: %s", reason, extra={"path": request.path})
    return JsonResponse(
        {"detail": "Security check failed. Refresh the page and try again."}, status=403
    )
