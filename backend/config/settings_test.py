"""Settings for the test suite: same as production code paths, with fast and isolated services."""

import os

os.environ.setdefault("ENVIRONMENT", "test")

from .settings import *  # noqa: E402,F403

DEBUG = False

# Fast hashing in tests only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

SMS_BACKEND = "core.sms.LocmemSMSBackend"

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {"handlers": [], "level": "CRITICAL"},
}

# django-otp waits after failed authenticator codes; tests check our own limits instead.
OTP_TOTP_THROTTLE_FACTOR = 0

# Tests never run collectstatic; let WhiteNoise look files up on demand instead.
WHITENOISE_AUTOREFRESH = True
