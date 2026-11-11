"""
Startup checks for staging and production. They run on `manage.py migrate` and
`manage.py check`, so a deploy with unsafe settings stops before the new code goes live.
"""

from django.conf import settings
from django.core.checks import Error, register
from django.core.exceptions import ImproperlyConfigured

from . import crypto


@register()
def deployment_settings_check(app_configs, **kwargs):
    if not settings.IS_DEPLOYED:
        return []

    errors = []

    if not settings.FIELD_ENCRYPTION_KEYS:
        errors.append(
            Error(
                "FIELD_ENCRYPTION_KEYS is not set.",
                hint="Generate one with `python manage.py generate_encryption_key`.",
                id="core.E001",
            )
        )
    else:
        try:
            for key in settings.FIELD_ENCRYPTION_KEYS:
                crypto.decode_key(key)
        except ImproperlyConfigured as exc:
            errors.append(Error(str(exc), id="core.E002"))

    fake_sms = settings.SMS_BACKEND in {"core.sms.ConsoleSMSBackend", "core.sms.LocmemSMSBackend"}
    staging_opt_in = settings.ENVIRONMENT == "staging" and settings.SMS_CONSOLE_ALLOWED
    if fake_sms and not staging_opt_in:
        errors.append(
            Error(
                f"SMS_BACKEND is {settings.SMS_BACKEND}, which does not send real messages.",
                hint=(
                    "Configure the SMS provider backend. Staging may use the console backend "
                    "with SMS_CONSOLE_ALLOWED=true; production never can."
                ),
                id="core.E003",
            )
        )

    if settings.DEBUG:
        errors.append(Error("DEBUG must be off in staging and production.", id="core.E004"))

    return errors
