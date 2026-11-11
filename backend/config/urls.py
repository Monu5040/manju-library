from django.contrib import admin
from django.urls import include, path
from django_otp.admin import OTPAdminSite

# The Django admin is a back-office tool for the Super Admin only, and it asks for the
# authenticator-app code on every login.
admin.site.__class__ = OTPAdminSite
admin.site.site_header = "Manju Library back office"
admin.site.site_title = "Manju Library back office"

urlpatterns = [
    path("backoffice/", admin.site.urls),
    path("api/", include("config.api_urls")),
]
