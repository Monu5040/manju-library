from datetime import time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User

ADMIN_MOBILE = "9000000001"
STUDENT_MOBILE = "9000000002"
DEFAULT_LOCAL_PASSWORD = "local-admin-password-123"  # noqa: S105  (local development only)

# Shift times as used in the library's workbook (Formula Items sheet).
SHIFTS = [
    ("Morning", time(6, 0), time(10, 0)),
    ("Late morning", time(10, 15), time(14, 15)),
    ("Afternoon", time(14, 30), time(18, 30)),
    ("Evening", time(18, 45), time(22, 45)),
    ("Morning long", time(6, 0), time(14, 15)),
    ("Day", time(10, 15), time(18, 30)),
    ("Afternoon long", time(14, 30), time(22, 45)),
]

# Made-up people for local screens only.
SAMPLE_STUDENTS = [
    ("Sample Student", STUDENT_MOBILE, 1, "Day", 0, 450),
    ("Asha Kumari", "9000000011", 2, "Day", -27, 0),
    ("Ravi Kumar", "9000000012", 2, "Morning", -5, 250),
    ("Neha Singh", "9000000013", 3, "Evening", -40, 0),
]


class Command(BaseCommand):
    help = "Local development: a Super Admin, the library's shifts and seats, and sample students."

    def add_arguments(self, parser):
        parser.add_argument("--admin-password", default=DEFAULT_LOCAL_PASSWORD)

    @transaction.atomic
    def handle(self, *args, **options):
        if settings.IS_DEPLOYED:
            raise CommandError("seed_dev is for local development only.")

        from billing.services import record_payment
        from library.models import Branch, Plan, Seat, Shift
        from members.models import Membership, Student
        from members.services import create_student, default_end_date, save_membership

        if not User.objects.filter(mobile=ADMIN_MOBILE).exists():
            User.objects.create_superuser(
                ADMIN_MOBILE,
                options["admin_password"],
                full_name="Local Admin",
                email="admin@example.com",
            )
            self.stdout.write(f"Super Admin: admin@example.com / {options['admin_password']}")

        branch = Branch.objects.order_by("id").first()
        for order, (name, start, end) in enumerate(SHIFTS):
            Shift.objects.get_or_create(
                branch=branch,
                name=name,
                defaults={"start_time": start, "end_time": end, "sort_order": order},
            )
        for number in range(1, 52):
            Seat.objects.get_or_create(branch=branch, number=str(number))
        day = Shift.objects.get(branch=branch, name="Day")
        plan, _ = Plan.objects.get_or_create(
            branch=branch,
            name="1 month · Day",
            defaults={"duration_months": 1, "shift": day, "price": Decimal("450")},
        )

        today = timezone.localdate()
        for seat_no, (name, mobile, seat_offset, shift_name, start_offset, paid) in enumerate(
            SAMPLE_STUDENTS, start=1
        ):
            if Student.objects.filter(branch=branch, mobile=mobile, full_name=name).exists():
                continue
            student = create_student(
                branch=branch, full_name=name, mobile=mobile, admission_date=today
            )
            start = today + timedelta(days=start_offset)
            membership = save_membership(
                Membership(
                    branch=branch,
                    student=student,
                    plan=plan,
                    shift=Shift.objects.get(branch=branch, name=shift_name),
                    seat=Seat.objects.get(branch=branch, number=str(seat_no + seat_offset)),
                    start_date=start,
                    end_date=default_end_date(start, 1),
                    price=Decimal("450"),
                )
            )
            if paid:
                record_payment(student=student, membership=membership, amount=Decimal(paid))

        if User.objects.filter(mobile=STUDENT_MOBILE, role=Role.STUDENT).exists():
            self.stdout.write(
                f"Student login: {STUDENT_MOBILE} (the code appears in the server log)"
            )
        self.stdout.write(
            self.style.SUCCESS("Local data is ready: 7 shifts, 51 seats, sample students.")
        )
