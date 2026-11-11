"""
Authentication API.

Students:  POST otp/request {mobile} -> SMS code -> POST otp/verify {mobile, code} -> session.
Admins:    POST admin/login {identifier, password} -> {"next": "setup" | "verify"}
           setup:  GET admin/totp/setup -> QR data, POST admin/totp/setup {token} -> session
           verify: POST admin/totp/verify {token} -> session
Everyone:  GET csrf (sets the CSRF cookie), GET me, POST logout.

Login endpoints check the CSRF token even before anyone is signed in (login CSRF).
"""

import base64
import time

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db.models import Count
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from audit import services as audit
from core.sms import send_sms

from . import otp
from .models import ADMIN_ROLES, Role, User
from .permissions import IsAdminOrStaff
from .serializers import (
    AdminLoginSerializer,
    MeSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    TotpTokenSerializer,
)
from .throttles import (
    AdminLoginIdentifierThrottle,
    AdminLoginIpThrottle,
    AdminTotpIpThrottle,
    OtpRequestIpThrottle,
    OtpRequestMobileThrottle,
    OtpVerifyIpThrottle,
)

AUTH_BACKEND = "accounts.backends.EmailOrMobileBackend"
PENDING_ADMIN_KEY = "pending_admin_login"


def _mask_mobile(mobile: str) -> str:
    return f"{mobile[:2]}XXXXXX{mobile[-2:]}" if len(mobile) == 10 else "invalid"


def _mask_identifier(identifier: str) -> str:
    if "@" in identifier:
        name, _, domain = identifier.partition("@")
        return f"{name[:1]}***@{domain}"
    return _mask_mobile(identifier)


# ---------------------------------------------------------------------------
# Session basics
# ---------------------------------------------------------------------------


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


class MeView(APIView):
    def get(self, request):
        user = request.user
        if user.is_admin_role and not user.is_verified():
            raise PermissionDenied("Finish signing in with your authenticator app.")
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if request.user.is_authenticated:
            audit.record(request, "auth.logout")
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Students: SMS code
# ---------------------------------------------------------------------------


@method_decorator(csrf_protect, name="dispatch")
class OtpRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OtpRequestIpThrottle, OtpRequestMobileThrottle]

    def post(self, request):
        serializer = OtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile = serializer.validated_data["mobile"]

        user = User.objects.filter(mobile=mobile, role=Role.STUDENT, is_active=True).first()
        if user is not None:
            code = otp.issue_code(user)
            minutes = int(settings.LOGIN_CODE_TTL.total_seconds() // 60)
            send_sms(
                mobile,
                f"{code} is your Manju Library login code. It expires in {minutes} minutes. "
                "Do not share it with anyone.",
            )
            audit.record(request, "auth.otp_sent", actor=user, entity="user", entity_id=user.pk)

        # Same answer whether or not the number is registered, so numbers cannot be probed.
        return Response(
            {"detail": "If this number is registered, a login code has been sent."},
            status=status.HTTP_202_ACCEPTED,
        )


@method_decorator(csrf_protect, name="dispatch")
class OtpVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OtpVerifyIpThrottle]

    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile = serializer.validated_data["mobile"]
        code = serializer.validated_data["code"]

        user = User.objects.filter(mobile=mobile, role=Role.STUDENT, is_active=True).first()
        if user is None or not otp.verify_code(user, code):
            audit.record(
                request,
                "auth.otp_failed",
                actor=user,
                metadata={"mobile": _mask_mobile(mobile)},
            )
            raise ValidationError(
                {"code": ["That code is wrong or has expired. Request a new one."]}
            )

        login(request, user, backend=AUTH_BACKEND)
        request.session.set_expiry(int(settings.STUDENT_SESSION_AGE.total_seconds()))
        audit.record(request, "auth.login", actor=user, metadata={"method": "sms_code"})
        return Response(MeSerializer(user).data)


# ---------------------------------------------------------------------------
# Admins and staff: password, then authenticator app
# ---------------------------------------------------------------------------


def _pending_admin(request) -> User | None:
    pending = request.session.get(PENDING_ADMIN_KEY)
    if not pending:
        return None
    age = time.time() - float(pending.get("started", 0))
    if age > settings.ADMIN_PENDING_LOGIN_TTL.total_seconds():
        request.session.pop(PENDING_ADMIN_KEY, None)
        return None
    return User.objects.filter(
        pk=pending.get("user_id"), is_active=True, role__in=ADMIN_ROLES
    ).first()


def _require_pending_admin(request) -> User:
    user = _pending_admin(request)
    if user is None:
        raise PermissionDenied("Your sign-in expired. Enter your password again.")
    return user


def _finish_admin_login(request, user: User, device: TOTPDevice) -> Response:
    request.session.pop(PENDING_ADMIN_KEY, None)
    login(request, user, backend=AUTH_BACKEND)
    otp_login(request, device)
    request.session.set_expiry(int(settings.ADMIN_SESSION_AGE.total_seconds()))
    audit.record(request, "auth.login", actor=user, metadata={"method": "password_totp"})
    return Response(MeSerializer(user).data)


@method_decorator(csrf_protect, name="dispatch")
class AdminLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AdminLoginIpThrottle, AdminLoginIdentifierThrottle]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=identifier, password=password)
        if user is None or not user.is_admin_role:
            audit.record(
                request,
                "auth.password_failed",
                actor=user,
                metadata={"identifier": _mask_identifier(identifier)},
            )
            raise ValidationError({"non_field_errors": ["Wrong email/mobile or password."]})

        # Start from a clean session that is not signed in; the authenticator step finishes it.
        if request.user.is_authenticated:
            logout(request)
        request.session.cycle_key()
        request.session[PENDING_ADMIN_KEY] = {"user_id": user.pk, "started": time.time()}

        has_app = TOTPDevice.objects.devices_for_user(user, confirmed=True).exists()
        audit.record(request, "auth.password_ok", actor=user)
        return Response({"next": "verify" if has_app else "setup"})


@method_decorator(csrf_protect, name="dispatch")
class TotpSetupView(APIView):
    """First sign-in for an admin: connect an authenticator app (Google Authenticator etc.)."""

    permission_classes = [AllowAny]
    throttle_classes = [AdminTotpIpThrottle]

    def get(self, request):
        user = _require_pending_admin(request)
        if TOTPDevice.objects.devices_for_user(user, confirmed=True).exists():
            return Response(
                {"detail": "An authenticator app is already connected to this account."},
                status=status.HTTP_409_CONFLICT,
            )
        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        if device is None:
            device = TOTPDevice.objects.create(user=user, name="Authenticator app", confirmed=False)
        secret = base64.b32encode(device.bin_key).decode().rstrip("=")
        return Response({"otpauth_uri": device.config_url, "secret": secret})

    def post(self, request):
        user = _require_pending_admin(request)
        serializer = TotpTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        if device is None:
            return Response(
                {"detail": "Start the authenticator setup again."},
                status=status.HTTP_409_CONFLICT,
            )
        if not device.verify_token(serializer.validated_data["token"]):
            audit.record(request, "auth.totp_failed", actor=user, metadata={"stage": "setup"})
            raise ValidationError(
                {"token": ["That code did not match. Check your phone's clock and try again."]}
            )

        device.confirmed = True
        device.save(update_fields=["confirmed"])
        audit.record(request, "auth.totp_connected", actor=user)
        return _finish_admin_login(request, user, device)


@method_decorator(csrf_protect, name="dispatch")
class TotpVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AdminTotpIpThrottle]

    def post(self, request):
        user = _require_pending_admin(request)
        serializer = TotpTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]

        for device in TOTPDevice.objects.devices_for_user(user, confirmed=True):
            if device.verify_token(token):
                return _finish_admin_login(request, user, device)

        audit.record(request, "auth.totp_failed", actor=user, metadata={"stage": "verify"})
        raise ValidationError(
            {"token": ["That code did not match. Use the newest code in your app."]}
        )


# ---------------------------------------------------------------------------
# Admin area
# ---------------------------------------------------------------------------


class AdminOverviewView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        counts = dict(
            User.objects.filter(is_active=True)
            .order_by()
            .values_list("role")
            .annotate(total=Count("id"))
        )
        return Response(
            {
                "users": {
                    "students": counts.get(Role.STUDENT, 0),
                    "staff": counts.get(Role.STAFF, 0),
                    "super_admins": counts.get(Role.SUPER_ADMIN, 0),
                }
            }
        )
