# ruff: noqa: S311 - `random` here is for made-up demo data, never for anything secret.
"""
Fill a DEVELOPMENT database with a made-up library for demos and load tests:

    uv run python manage.py seed_demo --students 400

Everything is invented (names "Demo Student 0001", mobiles 9000xxxxxx). It refuses to run on
staging or production, and refuses a database that already has demo students.
"""

import random
from datetime import time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from billing.services import record_payment
from ledger.models import LedgerCategory, LedgerEntry
from library.models import Branch, Seat, Shift
from members.models import Membership, Student, WaitlistEntry
from members.services import create_student, default_end_date, save_membership

FEE = Decimal("450")


class Command(BaseCommand):
    help = "Create a made-up library (development databases only)."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=300)
        parser.add_argument("--seed", type=int, default=7)

    def handle(self, *args, students, seed, **options):
        if settings.ENVIRONMENT not in {"development", "test"}:
            raise CommandError("seed_demo only runs on a development database.")
        if Student.objects.filter(full_name__startswith="Demo Student").exists():
            raise CommandError("This database already has demo students.")
        random.seed(seed)
        with transaction.atomic():
            created = self._seed(students)
        self.stdout.write(self.style.SUCCESS(created))

    def _seed(self, count: int) -> str:
        today = timezone.localdate()
        branch = Branch.objects.filter(is_active=True).order_by("id").first()
        shifts = list(Shift.objects.filter(branch=branch, is_active=True))
        if not shifts:
            for name, start, end in (("Morning", 6, 10), ("Day", 10, 18), ("Evening", 18, 22)):
                shifts.append(
                    Shift.objects.create(
                        branch=branch,
                        name=name,
                        start_time=time(start, 0),
                        end_time=time(end, 0),
                    )
                )
        for n in range(1, 101):
            Seat.objects.get_or_create(branch=branch, number=str(n))
        seats = list(Seat.objects.filter(branch=branch, is_active=True).order_by("sort_key"))
        # One student per seat keeps clear of overlapping shifts; seats already taken stay so.
        booked = set(
            Membership.objects.not_cancelled()
            .filter(branch=branch, seat__isnull=False)
            .values_list("seat_id", flat=True)
        )
        memberships = payments = 0

        for n in range(1, count + 1):
            student = create_student(
                branch=branch,
                full_name=f"Demo Student {n:04d}",
                mobile=f"9000{n:06d}",
                gender=random.choice("FFMMO"),
                admission_date=today - timedelta(days=random.randint(10, 360)),
            )
            shift = random.choice(shifts)
            seat = next(
                (s for s in seats if s.pk not in booked and random.random() < 0.6),
                None,
            )
            start = student.admission_date
            while start <= today + timedelta(days=5):
                months = random.choice([1, 1, 1, 2, 3])
                membership = save_membership(
                    Membership(
                        branch=branch,
                        student=student,
                        shift=shift,
                        seat=seat if seat and start <= today else None,
                        start_date=start,
                        end_date=default_end_date(start, months),
                        price=FEE * months,
                    )
                )
                memberships += 1
                paid = FEE * months if random.random() < 0.85 else FEE * months / 2
                record_payment(
                    student=student,
                    membership=membership,
                    amount=paid,
                    mode=random.choice(["CASH", "CASH", "UPI"]),
                    paid_on=min(start, today),
                )
                payments += 1
                if random.random() < 0.12:
                    break  # left the library
                start = membership.end_date + timedelta(days=1)
            if seat:
                booked.add(seat.pk)
            if n % 25 == 0:
                WaitlistEntry.objects.create(
                    branch=branch, student=student, preferred_shift=shift, position=n // 25
                )

        rent = LedgerCategory.objects.get(code="rent")
        power = LedgerCategory.objects.get(code="electricity")
        month = today.replace(day=1)
        for _ in range(12):
            LedgerEntry.objects.create(branch=branch, category=rent, entry_date=month, amount=8000)
            LedgerEntry.objects.create(
                branch=branch,
                category=power,
                entry_date=month + timedelta(days=4),
                amount=random.randint(1200, 2400),
            )
            month = (month - timedelta(days=1)).replace(day=1)
        return f"Created {count} demo students, {memberships} memberships and {payments} payments."
