import re

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

MOBILE_PATTERN = r"^[6-9]\d{9}$"
mobile_validator = RegexValidator(
    MOBILE_PATTERN, "Enter a 10-digit Indian mobile number that starts with 6, 7, 8 or 9."
)


def normalize_mobile(value: str | int | None) -> str:
    """
    Reduce a phone number to its 10 digits: drops spaces, dashes, a +91 / 91 prefix and a
    leading 0. Returns "" when nothing usable is left; validation happens separately.
    """
    if value is None:
        return ""
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


class Role(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
    STAFF = "STAFF", "Staff"
    STUDENT = "STUDENT", "Student"


ADMIN_ROLES = frozenset({Role.SUPER_ADMIN, Role.STAFF})


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, mobile, password, **extra_fields):
        mobile = normalize_mobile(mobile)
        if not mobile:
            raise ValueError("A mobile number is required.")
        email = extra_fields.pop("email", None)
        email = self.normalize_email(email) if email else None
        user = self.model(mobile=mobile, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, mobile, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.STUDENT)
        return self._create_user(mobile, password, **extra_fields)

    def create_superuser(self, mobile, password=None, **extra_fields):
        if not password:
            raise ValueError("A Super Admin needs a password.")
        extra_fields["role"] = Role.SUPER_ADMIN
        return self._create_user(mobile, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    One login account. Students sign in with their mobile number and an SMS code; admins and
    staff sign in with email or mobile, a password and an authenticator app. Siblings who
    share a parent's phone share one account here; their student profiles hang off it.
    """

    mobile = models.CharField(max_length=10, unique=True, validators=[mobile_validator])
    email = models.EmailField(unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    can_export = models.BooleanField(
        default=False,
        help_text="Staff only: allowed to export data. Super Admins can always export.",
    )
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "mobile"
    REQUIRED_FIELDS = ["full_name", "email"]

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.mobile})"

    def save(self, *args, **kwargs):
        # Django's own superuser flag always follows the role.
        self.is_superuser = self.role == Role.SUPER_ADMIN
        super().save(*args, **kwargs)

    @property
    def is_staff(self) -> bool:
        """Access to the Django admin back office: Super Admins only."""
        return self.role == Role.SUPER_ADMIN

    @property
    def is_admin_role(self) -> bool:
        return self.role in ADMIN_ROLES

    @property
    def may_export(self) -> bool:
        return self.role == Role.SUPER_ADMIN or (self.role == Role.STAFF and self.can_export)

    @property
    def masked_mobile(self) -> str:
        return f"{self.mobile[:2]}XXXXXX{self.mobile[-2:]}"

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.full_name.split(" ")[0] if self.full_name else self.mobile


class LoginCode(models.Model):
    """A one-time SMS code. Only an HMAC of the code is stored, never the code itself."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="login_codes"
    )
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"Login code for user {self.user_id} at {self.created_at:%Y-%m-%d %H:%M}"
