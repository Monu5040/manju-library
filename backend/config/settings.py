"""
Django settings for the Manju Library API.

Every environment-specific value comes from environment variables (see .env.example).
ENVIRONMENT is one of: development, test, build, staging, production.
"""

from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

ENVIRONMENT = env("ENVIRONMENT", default="development")
IS_DEPLOYED = ENVIRONMENT in {"staging", "production"}
DEBUG = env.bool("DEBUG", default=ENVIRONMENT == "development")

if IS_DEPLOYED:
    SECRET_KEY = env("SECRET_KEY")
else:
    SECRET_KEY = env("SECRET_KEY", default="django-insecure-local-only-never-use-in-production")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS", default=["http://localhost:5173", "http://127.0.0.1:5173"]
)

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "django_filters",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "core",
    "accounts",
    "audit",
    "library",
    "members",
    "billing",
    "imports",
    "portal",
    "ledger",
    "analytics",
    "automation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.NoStoreApiMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Data stores
# ---------------------------------------------------------------------------

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://manju:manju@localhost:5432/manju"),
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "manju",
    }
}

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.EmailOrMobileBackend"]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Students sign in with a one-time code sent by SMS; admins use a password plus an
# authenticator app (TOTP). Sessions are server-side and travel in an httpOnly cookie.
STUDENT_SESSION_AGE = timedelta(days=30)
ADMIN_SESSION_AGE = timedelta(hours=8)
LOGIN_CODE_TTL = timedelta(minutes=5)
LOGIN_CODE_MAX_ATTEMPTS = 5
ADMIN_PENDING_LOGIN_TTL = timedelta(minutes=5)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "core.views.csrf_failure"

OTP_TOTP_ISSUER = env("OTP_TOTP_ISSUER", default="Manju Library")
OTP_ADMIN_HIDE_SENSITIVE_DATA = True

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.Pagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    # Rupee amounts as JSON numbers, not strings.
    "COERCE_DECIMAL_TO_STRING": False,
    "DEFAULT_THROTTLE_RATES": {
        "otp_request_mobile": env("THROTTLE_OTP_REQUEST_MOBILE", default="5/hour"),
        "otp_request_ip": env("THROTTLE_OTP_REQUEST_IP", default="30/hour"),
        "otp_verify_ip": env("THROTTLE_OTP_VERIFY_IP", default="30/hour"),
        "admin_login_ip": env("THROTTLE_ADMIN_LOGIN_IP", default="20/hour"),
        "admin_login_identifier": env("THROTTLE_ADMIN_LOGIN_IDENTIFIER", default="10/hour"),
        "admin_totp_ip": env("THROTTLE_ADMIN_TOTP_IP", default="30/hour"),
        "online_payment": env("THROTTLE_ONLINE_PAYMENT", default="20/hour"),
    },
    # Number of reverse proxies in front of Django (Nginx = 1). Used to read the client IP.
    "NUM_PROXIES": env.int("NUM_PROXIES", default=0),
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
}
if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append(
        "rest_framework.renderers.BrowsableAPIRenderer"
    )

# ---------------------------------------------------------------------------
# Field encryption (Aadhaar and other sensitive values)
# ---------------------------------------------------------------------------

# Comma-separated base64url-encoded 32-byte keys. The first key encrypts; every key can
# decrypt, so a new key can be added in front and old data re-encrypted over time.
# Generate one with: python manage.py generate_encryption_key
_LOCAL_ONLY_KEY = "bG9jYWwtZGV2LW9ubHkta2V5LTMyLWJ5dGVzLWxvbmc="  # 32 bytes, local use only
FIELD_ENCRYPTION_KEYS = env.list(
    "FIELD_ENCRYPTION_KEYS", default=[] if IS_DEPLOYED else [_LOCAL_ONLY_KEY]
)

# ---------------------------------------------------------------------------
# SMS
# ---------------------------------------------------------------------------

SMS_BACKEND = env("SMS_BACKEND", default="core.sms.ConsoleSMSBackend")
SMS_SENDER_ID = env("SMS_SENDER_ID", default="MANJUL")
# Staging only: allow the console backend (codes appear in server logs) until a provider is set up.
SMS_CONSOLE_ALLOWED = env.bool("SMS_CONSOLE_ALLOWED", default=False)

# MSG91 (SMS_BACKEND=core.sms.Msg91SMSBackend). The template must be DLT-approved.
MSG91_AUTH_KEY = env("MSG91_AUTH_KEY", default="")
MSG91_OTP_TEMPLATE_ID = env("MSG91_OTP_TEMPLATE_ID", default="")
MSG91_CODE_VARIABLE = env("MSG91_CODE_VARIABLE", default="otp")
MSG91_MINUTES_VARIABLE = env("MSG91_MINUTES_VARIABLE", default="")
MSG91_API_URL = env("MSG91_API_URL", default="https://control.msg91.com/api/v5/flow/")
# DLT-approved templates for automatic reminders. Each one receives the variables name,
# library, date, seat, shift and amount. A kind without a template is sent by hand instead.
MSG91_REMINDER_TEMPLATES = {
    kind: env(f"MSG91_TEMPLATE_{kind}", default="")
    for kind in ("EXPIRING_SOON", "EXPIRES_TODAY", "DUES", "WAITLIST")
}

# ---------------------------------------------------------------------------
# Online payments (Razorpay)
# ---------------------------------------------------------------------------

# Students pay on Razorpay's own page (a payment link), so no Razorpay script runs on this
# site and the CSP stays strict. Razorpay confirms each payment with a signed webhook; a job
# also asks Razorpay about open links in case a webhook is missed. Online payments stay off
# until all three values are set and the owner turns them on in Settings.
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="")
RAZORPAY_API_URL = env("RAZORPAY_API_URL", default="https://api.razorpay.com/v1/")
# With test keys on a deployed server, only these mobile numbers can pay online, so test
# money never gives a real student a receipt or a renewal. Production refuses test keys.
RAZORPAY_TEST_MOBILES = env.list("RAZORPAY_TEST_MOBILES", default=[])
# Where students come back to after paying. Deployed sites work it out from the request;
# set this when the API is reached through another address (local development).
SITE_URL = env("SITE_URL", default="")

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_BEAT_SCHEDULE = {
    "purge-expired-login-codes": {
        "task": "accounts.tasks.purge_expired_login_codes",
        "schedule": timedelta(hours=1),
    },
    # Hourly in the day, so a missed run (a restart, a deploy) catches up within the hour.
    "reminders": {
        "task": "automation.tasks.run_reminders",
        "schedule": crontab(minute=5, hour="8-20"),
    },
    "mark-students-left": {
        "task": "automation.tasks.mark_students_left",
        "schedule": crontab(minute=30, hour=2),
    },
    "purge-old-import-data": {
        "task": "automation.tasks.purge_old_import_data",
        "schedule": crontab(minute=40, hour=2),
    },
    "clear-expired-sessions": {
        "task": "automation.tasks.clear_expired_sessions",
        "schedule": crontab(minute=50, hour=2),
    },
    # Catches online payments whose webhook never arrived.
    "check-online-payments": {
        "task": "billing.tasks.check_online_payments",
        "schedule": timedelta(minutes=10),
    },
}

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files (Django admin back-office only; the React app is served by Nginx)
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# ---------------------------------------------------------------------------
# Security (deployed environments sit behind Nginx, which terminates HTTPS)
# ---------------------------------------------------------------------------

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

if IS_DEPLOYED:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
    # HSTS preload is hard to undo, so it stays off unless deliberately enabled.
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
    if not SECURE_HSTS_PRELOAD:
        SILENCED_SYSTEM_CHECKS = ["security.W021"]

# ---------------------------------------------------------------------------
# Logging: one JSON object per line on stdout
# ---------------------------------------------------------------------------

LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "core.logging.JsonFormatter"},
        "plain": {"format": "%(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain" if DEBUG else "json",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
    },
}

# ---------------------------------------------------------------------------
# Error monitoring
# ---------------------------------------------------------------------------

# The deployed commit, shown on the System status page (set by deploy.sh through Compose).
APP_VERSION = env("APP_VERSION", default="dev")

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=ENVIRONMENT,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        send_default_pii=False,
        # Never send local variables or request bodies: they can hold login codes, Aadhaar
        # numbers or uploaded spreadsheets.
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
    )
