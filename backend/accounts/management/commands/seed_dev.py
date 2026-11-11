from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User

ADMIN_MOBILE = "9000000001"
STUDENT_MOBILE = "9000000002"
DEFAULT_LOCAL_PASSWORD = "local-admin-password-123"  # noqa: S105  (local development only)


class Command(BaseCommand):
    help = "Create a Super Admin and a sample student for local development."

    def add_arguments(self, parser):
        parser.add_argument("--admin-password", default=DEFAULT_LOCAL_PASSWORD)

    def handle(self, *args, **options):
        if settings.IS_DEPLOYED:
            raise CommandError("seed_dev is for local development only.")

        if not User.objects.filter(mobile=ADMIN_MOBILE).exists():
            User.objects.create_superuser(
                ADMIN_MOBILE,
                options["admin_password"],
                full_name="Local Admin",
                email="admin@example.com",
            )
            self.stdout.write(f"Super Admin: admin@example.com / {options['admin_password']}")
        if not User.objects.filter(mobile=STUDENT_MOBILE).exists():
            User.objects.create_user(STUDENT_MOBILE, full_name="Sample Student", role=Role.STUDENT)
            self.stdout.write(
                f"Student: {STUDENT_MOBILE} (the login code appears in the server log)"
            )
        self.stdout.write(self.style.SUCCESS("Local accounts are ready."))
