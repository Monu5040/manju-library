from django.core.management.base import BaseCommand

from core.crypto import generate_key


class Command(BaseCommand):
    help = "Print a new 256-bit key for FIELD_ENCRYPTION_KEYS. Store it in the secrets manager."

    def handle(self, *args, **options):
        self.stdout.write(generate_key())
