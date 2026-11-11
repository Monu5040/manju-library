# ruff: noqa: S311 - `random` here is for spreading out simulated clicks, never for anything secret.
"""
Load test a running server from a DEVELOPMENT database:

    uv run python manage.py seed_demo --students 400
    uv run python manage.py loadtest --url http://127.0.0.1:8017 --students 30 --admins 3

Students and the first Super Admin are signed in by writing sessions straight into this
database (it must be the one the server uses), then many threads use the site at once the
way people do: students open their portal, admins move between the busiest admin pages.
Prints response times per endpoint; the sessions are deleted afterwards.
"""

import random
import re
import statistics
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts.models import Role, User
from accounts.views import AUTH_BACKEND
from billing.models import Payment
from members.models import Student


class Command(BaseCommand):
    help = "Send realistic concurrent traffic to a running server (development only)."

    def add_arguments(self, parser):
        parser.add_argument("--url", default="http://127.0.0.1:8017")
        parser.add_argument("--students", type=int, default=30, help="students at once")
        parser.add_argument("--admins", type=int, default=3, help="admin screens at once")
        parser.add_argument("--seconds", type=int, default=60)
        parser.add_argument("--think", type=float, default=0.5, help="seconds between clicks")

    def handle(self, *args, url, students, admins, seconds, think, **options):
        if settings.ENVIRONMENT != "development":
            raise CommandError("loadtest only runs against a development database.")
        people = list(
            Student.objects.filter(full_name__startswith="Demo Student", account__isnull=False)
            .select_related("account")
            .order_by("?")[:students]
        )
        owner = User.objects.filter(role=Role.SUPER_ADMIN, is_active=True).order_by("id").first()
        if not people or owner is None:
            raise CommandError("Run seed_dev and seed_demo first.")
        # A signed-in admin needs a verified authenticator; borrow a temporary one if none.
        device = TOTPDevice.objects.filter(user=owner, confirmed=True).first()
        temporary = device is None
        if temporary:
            device = TOTPDevice.objects.create(user=owner, name="load test", confirmed=True)

        sessions: list[str] = []

        def sign_in(user, otp_device=None) -> str:
            session = SessionStore()
            session[SESSION_KEY] = str(user.pk)
            session[BACKEND_SESSION_KEY] = AUTH_BACKEND
            session[HASH_SESSION_KEY] = user.get_session_auth_hash()
            if otp_device is not None:
                session[DEVICE_ID_SESSION_KEY] = otp_device.persistent_id
            session.create()
            sessions.append(session.session_key)
            return session.session_key

        today = timezone.localdate()
        month_ago = today - timedelta(days=30)
        year_ago = today - timedelta(days=364)
        receipts = dict(Payment.objects.filter(student__in=people).values_list("student_id", "pk"))
        admin_pages = [
            "/api/auth/me/",
            "/api/admin/overview/",
            "/api/admin/students/?status=ACTIVE&page_size=25",
            "/api/admin/students/?q=Demo&page_size=25",
            "/api/admin/payments/?page_size=50",
            "/api/admin/seat-map/",
            "/api/admin/reminders/?open=1&page_size=200",
            f"/api/admin/analytics/?from={month_ago}&to={today}",
            f"/api/admin/analytics/?from={year_ago}&to={today}",
            f"/api/admin/ledger/daily/?from={month_ago}&to={today}",
        ]
        users = [
            (
                sign_in(person.account),
                [
                    "/api/auth/me/",
                    "/api/portal/home/",
                    f"/api/portal/students/{person.pk}/",
                    *(
                        [f"/api/portal/receipts/{receipts[person.pk]}/"]
                        if person.pk in receipts
                        else []
                    ),
                ],
            )
            for person in people
        ]
        users += [(sign_in(owner, device), admin_pages) for _ in range(admins)]

        timings: dict[str, list[float]] = defaultdict(list)
        errors: dict[str, int] = defaultdict(int)
        lock = threading.Lock()
        deadline = time.monotonic() + seconds
        cookie_name = settings.SESSION_COOKIE_NAME

        def visit(session_key: str, pages: list[str]) -> None:
            position = random.randrange(len(pages))
            while time.monotonic() < deadline:
                path = pages[position % len(pages)]
                position += 1
                request = urllib.request.Request(  # noqa: S310 - the developer's own --url
                    url + path, headers={"Cookie": f"{cookie_name}={session_key}"}
                )
                started = time.monotonic()
                try:
                    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                        response.read()
                        failed = response.status >= 400
                except (urllib.error.URLError, TimeoutError):
                    failed = True
                elapsed = time.monotonic() - started
                key = re.sub(r"\d+", "N", path.split("?")[0]) + (
                    " (year)" if str(year_ago) in path else ""
                )
                with lock:
                    timings[key].append(elapsed)
                    if failed:
                        errors[key] += 1
                time.sleep(random.uniform(0, 2 * think))

        self.stdout.write(
            f"{len(people)} students and {admins} admin screens for {seconds} s against {url}…"
        )
        try:
            with ThreadPoolExecutor(max_workers=len(users)) as pool:
                for session_key, pages in users:
                    pool.submit(visit, session_key, pages)
        finally:
            SessionStore().model.objects.filter(session_key__in=sessions).delete()
            if temporary:
                device.delete()

        total = sum(len(t) for t in timings.values())
        self.stdout.write(
            f"\n{'endpoint':52} {'n':>5} {'err':>4} {'p50':>6} {'p95':>6} {'max':>6}  (ms)"
        )
        for key in sorted(timings, key=lambda k: -statistics.median(timings[k])):
            values = sorted(timings[key])
            p95 = values[min(len(values) - 1, int(len(values) * 0.95))]
            self.stdout.write(
                f"{key:52} {len(values):5} {errors[key]:4} {statistics.median(values) * 1000:6.0f} "
                f"{p95 * 1000:6.0f} {values[-1] * 1000:6.0f}"
            )
        self.stdout.write(
            f"\n{total} requests, {total / seconds:.1f} per second, {sum(errors.values())} errors."
        )
