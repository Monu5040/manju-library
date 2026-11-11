from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts import views as accounts_views
from analytics import views as analytics_views
from billing.views import PaymentViewSet
from core import views as core_views
from imports.views import ImportViewSet
from ledger import views as ledger_views
from library.views import BranchViewSet, PlanViewSet, SeatViewSet, ShiftViewSet
from members import views as members_views
from portal import views as portal_views

admin_router = DefaultRouter(trailing_slash=True)
admin_router.include_root_view = False
admin_router.register("branches", BranchViewSet, basename="branch")
admin_router.register("shifts", ShiftViewSet, basename="shift")
admin_router.register("seats", SeatViewSet, basename="seat")
admin_router.register("plans", PlanViewSet, basename="plan")
admin_router.register("students", members_views.StudentViewSet, basename="student")
admin_router.register("memberships", members_views.MembershipViewSet, basename="membership")
admin_router.register("waitlist", members_views.WaitlistViewSet, basename="waitlist")
admin_router.register("payments", PaymentViewSet, basename="payment")
admin_router.register("staff", accounts_views.StaffViewSet, basename="staff")
admin_router.register("imports", ImportViewSet, basename="import")
admin_router.register("notices", portal_views.NoticeViewSet, basename="notice")
admin_router.register(
    "ledger/categories", ledger_views.LedgerCategoryViewSet, basename="ledger-category"
)
admin_router.register("ledger/entries", ledger_views.LedgerEntryViewSet, basename="ledger-entry")
admin_router.register("ledger/imports", ledger_views.LedgerImportViewSet, basename="ledger-import")
admin_router.register("cash-closings", ledger_views.CashClosingViewSet, basename="cash-closing")

urlpatterns = [
    path("health/", core_views.HealthView.as_view(), name="health"),
    # Session and CSRF
    path("auth/csrf/", accounts_views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/me/", accounts_views.MeView.as_view(), name="auth-me"),
    path("auth/logout/", accounts_views.LogoutView.as_view(), name="auth-logout"),
    path("auth/password/", accounts_views.PasswordChangeView.as_view(), name="auth-password"),
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
    path("admin/overview/", members_views.DashboardView.as_view(), name="admin-overview"),
    path("admin/admissions/", members_views.AdmissionView.as_view(), name="admin-admission"),
    path("admin/seat-map/", members_views.SeatMapView.as_view(), name="admin-seat-map"),
    path("admin/ledger/daily/", ledger_views.DailyLedgerView.as_view(), name="admin-ledger-daily"),
    path("admin/analytics/", analytics_views.AnalyticsView.as_view(), name="admin-analytics"),
    path(
        "admin/analytics/export/",
        analytics_views.AnalyticsExportView.as_view(),
        name="admin-analytics-export",
    ),
    path("admin/", include(admin_router.urls)),
    # Student portal
    path("portal/home/", portal_views.PortalHomeView.as_view(), name="portal-home"),
    path(
        "portal/students/<int:pk>/", portal_views.PortalStudentView.as_view(), name="portal-student"
    ),
    path(
        "portal/receipts/<int:pk>/", portal_views.PortalReceiptView.as_view(), name="portal-receipt"
    ),
]
