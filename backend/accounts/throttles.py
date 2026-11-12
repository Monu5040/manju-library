"""Rate limits for the login endpoints. Rates live in settings.REST_FRAMEWORK."""

from rest_framework.throttling import SimpleRateThrottle

from .models import normalize_mobile


class _IpThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class OtpRequestIpThrottle(_IpThrottle):
    scope = "otp_request_ip"


class OtpVerifyIpThrottle(_IpThrottle):
    scope = "otp_verify_ip"


class AdminLoginIpThrottle(_IpThrottle):
    scope = "admin_login_ip"


class AdminTotpIpThrottle(_IpThrottle):
    scope = "admin_totp_ip"


class OtpRequestMobileThrottle(SimpleRateThrottle):
    """Limits how many codes one phone number can be sent, whoever asks."""

    scope = "otp_request_mobile"

    def get_cache_key(self, request, view):
        mobile = normalize_mobile(request.data.get("mobile"))
        if not mobile:
            return None
        return self.cache_format % {"scope": self.scope, "ident": mobile}


class AdminLoginIdentifierThrottle(SimpleRateThrottle):
    """Limits password guesses against one account, from any number of addresses."""

    scope = "admin_login_identifier"

    def get_cache_key(self, request, view):
        identifier = str(request.data.get("identifier") or "").strip().lower()
        if not identifier:
            return None
        if "@" not in identifier:
            # "+91 98765 43210", "9876543210a" and "9876543210" are the same account.
            identifier = normalize_mobile(identifier) or identifier
        return self.cache_format % {"scope": self.scope, "ident": identifier}


class OnlinePaymentThrottle(SimpleRateThrottle):
    """Each online payment start asks Razorpay for a link: a few per hour per login."""

    scope = "online_payment"

    def get_cache_key(self, request, view):
        if request.method != "POST" or not request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}
