from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from automation import monitoring, tasks
from automation.models import JobRun

pytestmark = pytest.mark.django_db


def test_every_job_run_is_recorded_with_its_result():
    tasks.clear_expired_sessions()
    run = JobRun.objects.get(name="session-cleanup")
    assert run.ok and run.finished_at and run.summary == {"done": True}

    with mock.patch("automation.tasks.call_command", side_effect=RuntimeError("disk full")):
        with pytest.raises(RuntimeError):
            tasks.clear_expired_sessions()
    failed = JobRun.objects.filter(name="session-cleanup").first()
    assert not failed.ok and failed.summary == {"error": "RuntimeError: disk full"}


def test_only_recent_runs_are_kept():
    with mock.patch.object(monitoring, "KEEP_RUNS", 3):
        for _ in range(5):
            tasks.clear_expired_sessions()
    assert JobRun.objects.filter(name="session-cleanup").count() == 3


def test_job_states():
    now = timezone.now().replace(hour=12)  # in the day, so daytime jobs are judged too

    def record(name, hours_ago, ok=True):
        started = now - timedelta(hours=hours_ago)
        JobRun.objects.create(name=name, started_at=started, finished_at=started, ok=ok)

    record("login-code-cleanup", 1)
    record("reminders", 3)  # due every hour in the day: three hours is too long
    record("import-cleanup", 2, ok=False)
    states = {row["name"]: row["state"] for row in monitoring.job_status(now)}
    assert states == {
        "login-code-cleanup": "ok",
        "reminders": "late",
        "mark-students-left": "waiting",
        "import-cleanup": "failed",
        "session-cleanup": "waiting",
    }


def test_the_status_page_is_for_the_super_admin(owner_api, staff_api):
    assert staff_api.get("/api/admin/system/").status_code == 403
    with mock.patch.object(monitoring, "_worker", return_value="1 worker answering"):
        status = owner_api.get("/api/admin/system/").json()
    checks = {c["label"]: c for c in status["checks"]}
    assert checks["Database"]["ok"] and checks["Database"]["detail"].startswith("PostgreSQL")
    assert checks["Redis"]["ok"] and checks["Background worker"]["ok"]
    assert status["version"] == "dev" and status["environment"] == "test"
    launch = {item["key"]: item["done"] for item in status["launch"]}
    assert launch == {
        "sms": False,
        "production": False,
        "backups": False,
        "errors": False,
        "uptime": None,
    }
    assert {row["name"] for row in status["jobs"]} == set(monitoring.JOBS)


def test_a_failing_check_is_reported_not_raised(owner_api):
    with mock.patch.object(
        monitoring, "_worker", side_effect=RuntimeError("No background worker answered.")
    ):
        status = owner_api.get("/api/admin/system/").json()
    worker = next(c for c in status["checks"] if c["label"] == "Background worker")
    assert worker == {
        **worker,
        "ok": False,
        "detail": "RuntimeError: No background worker answered.",
    }


def test_health_fails_when_redis_does(api):
    assert api.get("/api/health/").json() == {"status": "ok"}
    with mock.patch("core.views.cache.set", side_effect=ConnectionError("refused")):
        response = api.get("/api/health/")
    assert response.status_code == 503 and response.json()["cache"] == "unavailable"


def test_the_quick_check_skips_the_live_checks(owner_api):
    with mock.patch.object(monitoring, "_worker") as worker:
        status = owner_api.get("/api/admin/system/?quick=1").json()
    worker.assert_not_called()
    assert status["checks"] == [] and len(status["jobs"]) == len(monitoring.JOBS)
