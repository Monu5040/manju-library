"""
Is everything working? Each scheduled job records its runs (`tracked`), and the System
status page puts those next to live checks of the database, Redis and the background
worker, the free disk space, and what is still to do before launch.
"""

import functools
import os
import shutil
import time
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone

from .models import JobRun

KEEP_RUNS = 200

# Every scheduled job: how often it runs, and how long without a successful run is too long.
JOBS = {
    "login-code-cleanup": {
        "label": "Remove expired login codes",
        "schedule": "Every hour",
        "max_gap": timedelta(hours=2),
    },
    "reminders": {
        "label": "Reminders",
        "schedule": "Every hour, 8 AM to 8 PM",
        "max_gap": timedelta(hours=2),
        "daytime": (10, 21),  # judged only between 10 AM and 9 PM
    },
    "mark-students-left": {
        "label": "Mark students as left (if turned on)",
        "schedule": "Every night, 2:30 AM",
        "max_gap": timedelta(hours=26),
    },
    "import-cleanup": {
        "label": "Delete old import files",
        "schedule": "Every night, 2:40 AM",
        "max_gap": timedelta(hours=26),
    },
    "session-cleanup": {
        "label": "Clear expired sessions",
        "schedule": "Every night, 2:50 AM",
        "max_gap": timedelta(hours=26),
    },
}


def tracked(name: str):
    """Record every run of a scheduled job: when, how long, and what it did or why it failed."""

    def decorate(job):
        @functools.wraps(job)
        def run(*args, **kwargs):
            record = JobRun.objects.create(name=name, started_at=timezone.now())
            try:
                result = job(*args, **kwargs)
            except Exception as exc:
                record.summary = {"error": f"{type(exc).__name__}: {exc}"[:500]}
                raise
            else:
                record.ok = True
                record.summary = result if isinstance(result, dict) else {"result": result}
                return result
            finally:
                record.finished_at = timezone.now()
                record.save(update_fields=["finished_at", "ok", "summary"])
                old = JobRun.objects.filter(name=name).values_list("pk", flat=True)[KEEP_RUNS:]
                JobRun.objects.filter(pk__in=list(old)).delete()

        return run

    return decorate


def job_status(now=None) -> list[dict]:
    now = now or timezone.now()
    local_hour = timezone.localtime(now).hour
    rows = []
    for name, job in JOBS.items():
        last = JobRun.objects.filter(name=name).first()
        last_ok = JobRun.objects.filter(name=name, ok=True).first()
        if last is None:
            state = "waiting"
        elif last.finished_at is None and now - last.started_at < timedelta(minutes=30):
            state = "running"
        elif not last.ok:
            state = "failed"
        else:
            state = "ok"
        daytime = job.get("daytime")
        judged = daytime is None or daytime[0] <= local_hour < daytime[1]
        if state == "ok" and judged and now - last_ok.started_at > job["max_gap"]:
            state = "late"
        rows.append(
            {
                "name": name,
                "label": job["label"],
                "schedule": job["schedule"],
                "state": state,
                "last_run": last.started_at if last else None,
                "last_success": last_ok.started_at if last_ok else None,
                "summary": last.summary if last else {},
            }
        )
    return rows


def _check(label: str, probe) -> dict:
    started = time.monotonic()
    try:
        detail = probe()
        ok = True
    except Exception as exc:  # a status page reports problems, it never raises them
        detail, ok = f"{type(exc).__name__}: {exc}"[:200], False
    return {
        "label": label,
        "ok": ok,
        "detail": detail,
        "ms": round((time.monotonic() - started) * 1000),
    }


def _database() -> str:
    with connection.cursor() as cursor:
        cursor.execute("SHOW server_version")
        return f"PostgreSQL {cursor.fetchone()[0].split()[0]}"


def _redis() -> str:
    cache.set("status-check", "ok", 10)
    if cache.get("status-check") != "ok":
        raise RuntimeError("Redis did not return what was stored.")
    return "Cache, rate limits and the job queue are reachable."


def _worker() -> str:
    from config.celery import app

    replies = app.control.ping(timeout=1.5)
    if not replies:
        raise RuntimeError("No background worker answered. Reminders and nightly jobs stop.")
    return f"{len(replies)} worker{'s' if len(replies) > 1 else ''} answering"


def launch_checklist() -> list[dict]:
    sms_live = settings.SMS_BACKEND.endswith("Msg91SMSBackend") and bool(settings.MSG91_AUTH_KEY)
    return [
        {
            "key": "sms",
            "label": "Students get their login code by SMS (MSG91)",
            "done": sms_live,
        },
        {
            "key": "production",
            "label": "The server runs as production (ENVIRONMENT=production)",
            "done": settings.ENVIRONMENT == "production",
        },
        {
            "key": "backups",
            "label": "Nightly database backups to object storage",
            "done": bool(os.environ.get("BACKUP_BUCKET")),
        },
        {
            "key": "errors",
            "label": "Error alerts by email (Sentry)",
            "done": bool(settings.SENTRY_DSN),
        },
        {
            "key": "uptime",
            "label": "An uptime monitor checks /api/health/ every few minutes",
            "done": None,  # outside the app: confirm it yourself
        },
    ]


def system_status(quick: bool = False) -> dict:
    """`quick` skips the live checks (the worker ping takes a moment), for the Overview."""
    disk = shutil.disk_usage("/")
    checks = []
    if not quick:
        checks = [
            _check("Database", _database),
            _check("Redis", _redis),
            _check("Background worker", _worker),
        ]
    return {
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "checked_at": timezone.now(),
        "checks": checks,
        "jobs": job_status(),
        "disk": {
            "total_gb": round(disk.total / 1e9, 1),
            "free_gb": round(disk.free / 1e9, 1),
            "used_percent": round(100 * disk.used / disk.total),
        },
        "launch": launch_checklist(),
    }
