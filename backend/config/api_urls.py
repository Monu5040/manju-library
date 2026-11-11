from django.urls import path

from accounts import views as accounts_views
from core import views as core_views

urlpatterns = [
    path("health/", core_views.HealthView.as_view(), name="health"),
    # Session and CSRF
    path("auth/csrf/", accounts_views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/me/", accounts_views.MeView.as_view(), name="auth-me"),
    path("auth/logout/", accounts_views.LogoutView.as_view(), name="auth-logout"),
    # Students: one-time code by SMS
    path("auth/otp/request/", accounts_views.OtpRequestView.as_view(), name="auth-otp-request"),
    path("auth/otp/verify/", accounts_views.OtpVerifyView.as_view(), name="auth-otp-verify"),
    # Admins and staff: password, then authenticator app
    path("auth/admin/login/", accounts_views.AdminLoginView.as_view(), name="auth-admin-login"),
    path(
        "auth/admin/totp/setup/",
        accounts_views.TotpSetupView.as_view(),
        name="auth-admin-totp-setup",
    ),
    path(
        "auth/admin/totp/verify/",
        accounts_views.TotpVerifyView.as_view(),
        name="auth-admin-totp-verify",
    ),
    # Admin area
    path("admin/overview/", accounts_views.AdminOverviewView.as_view(), name="admin-overview"),
]
