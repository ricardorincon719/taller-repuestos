import os
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, "true" if default else "false").lower() == "true"

DEBUG = env_bool("DJANGO_DEBUG", True)
APP_ENVIRONMENT = os.environ.get(
    "APP_ENVIRONMENT", "production" if not DEBUG else "development"
).lower()
DEVELOPMENT_SECRET_KEY = "development-only-change-me-before-production"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", DEVELOPMENT_SECRET_KEY)
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()

if not DEBUG and SECRET_KEY == DEVELOPMENT_SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in production.")
if (
    not DEBUG
    and not os.environ.get("DJANGO_ALLOWED_HOSTS")
    and not RENDER_EXTERNAL_HOSTNAME
):
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is required in production.")
if not DEBUG and not os.environ.get("DATABASE_URL"):
    raise ImproperlyConfigured("DATABASE_URL is required in production.")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"
    ).split(",")
    if host.strip()
]
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.organizations",
    "apps.customers",
    "apps.quotes",
    "apps.billing",
    "apps.dashboard",
]

MIDDLEWARE = [
    "config.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.organizations.middleware.OrganizationLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"
CSRF_FAILURE_VIEW = "config.views.csrf_failure"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.app_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.dev.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

CACHES = {
    "default": {
        "BACKEND": os.environ.get(
            "DJANGO_CACHE_BACKEND",
            (
                "django.core.cache.backends.locmem.LocMemCache"
                if DEBUG
                else "django.core.cache.backends.filebased.FileBasedCache"
            ),
        ),
        "LOCATION": os.environ.get(
            "DJANGO_CACHE_LOCATION", "/tmp/taller-pro-cache"
        ),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "es"
LANGUAGES = [
    ("es", "Español"),
    ("pt-br", "Português do Brasil"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", "43200"))
SESSION_SAVE_EVERY_REQUEST = True
SECURE_SSL_REDIRECT = (
    not DEBUG
    and os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true"
)
SECURE_HSTS_SECONDS = int(
    os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = (
    not DEBUG
    and os.environ.get("DJANGO_SECURE_HSTS_PRELOAD", "false").lower() == "true"
)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

default_site_url = (
    f"https://{RENDER_EXTERNAL_HOSTNAME}"
    if RENDER_EXTERNAL_HOSTNAME
    else "http://localhost:8000"
)
SITE_URL = os.environ.get("SITE_URL", default_site_url).rstrip("/")
TRIAL_DAYS = int(os.environ.get("TRIAL_DAYS", "14"))
REGISTRATION_RATE_LIMIT = int(os.environ.get("REGISTRATION_RATE_LIMIT", "5"))
REGISTRATION_RATE_LIMIT_WINDOW = int(
    os.environ.get("REGISTRATION_RATE_LIMIT_WINDOW", "3600")
)
AUTH_RATE_LIMIT_WINDOW = int(os.environ.get("AUTH_RATE_LIMIT_WINDOW", "3600"))
LOGIN_RATE_LIMIT = int(os.environ.get("LOGIN_RATE_LIMIT", "10"))
PASSWORD_RESET_RATE_LIMIT = int(os.environ.get("PASSWORD_RESET_RATE_LIMIT", "5"))
ACTIVATION_RESEND_RATE_LIMIT = int(os.environ.get("ACTIVATION_RESEND_RATE_LIMIT", "5"))
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", bool(RENDER_EXTERNAL_HOSTNAME))
PASSWORD_RESET_TIMEOUT = int(os.environ.get("PASSWORD_RESET_TIMEOUT", "3600"))
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Taller Pro <no-reply@localhost>")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))

LEGAL_DOCUMENT_VERSION = os.environ.get("LEGAL_DOCUMENT_VERSION", "2026-08-02")
LEGAL_ENTITY_NAME = os.environ.get("LEGAL_ENTITY_NAME", "Taller Pro")
LEGAL_ENTITY_ADDRESS = os.environ.get("LEGAL_ENTITY_ADDRESS", "")
LEGAL_CONTACT_EMAIL = os.environ.get(
    "LEGAL_CONTACT_EMAIL", "soporte.tallerpro@gmail.com"
)
LEGAL_JURISDICTION = os.environ.get("LEGAL_JURISDICTION", "Brasil")
PUBLIC_PLAN_PRICE_LABEL = os.environ.get(
    "PUBLIC_PLAN_PRICE_LABEL", "Precio final visible antes de pagar"
)
ACCOUNT_DELETION_GRACE_DAYS = int(
    os.environ.get("ACCOUNT_DELETION_GRACE_DAYS", "7")
)

PADDLE_ENABLED = env_bool("PADDLE_ENABLED", False)
PADDLE_ENVIRONMENT = os.environ.get("PADDLE_ENVIRONMENT", "sandbox").lower()
PADDLE_CLIENT_TOKEN = os.environ.get("PADDLE_CLIENT_TOKEN", "")
PADDLE_API_KEY = os.environ.get("PADDLE_API_KEY", "")
PADDLE_WEBHOOK_SECRET = os.environ.get("PADDLE_WEBHOOK_SECRET", "")
PADDLE_STARTER_PRICE_ID = os.environ.get("PADDLE_STARTER_PRICE_ID", "")
PADDLE_PROFESSIONAL_PRICE_ID = os.environ.get(
    "PADDLE_PROFESSIONAL_PRICE_ID", ""
)
PADDLE_API_BASE_URL = (
    "https://sandbox-api.paddle.com"
    if PADDLE_ENVIRONMENT == "sandbox"
    else "https://api.paddle.com"
)
PADDLE_API_TIMEOUT = int(os.environ.get("PADDLE_API_TIMEOUT", "10"))
PADDLE_WEBHOOK_TOLERANCE = int(
    os.environ.get("PADDLE_WEBHOOK_TOLERANCE", "300")
)
BILLING_PAST_DUE_GRACE_DAYS = int(
    os.environ.get("BILLING_PAST_DUE_GRACE_DAYS", "3")
)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "config.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        }
    },
}

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=APP_ENVIRONMENT,
        release=os.environ.get("RENDER_GIT_COMMIT", ""),
        send_default_pii=False,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
    )

if not DEBUG and urlparse(SITE_URL).scheme != "https":
    raise ImproperlyConfigured("SITE_URL must use HTTPS in production.")
if not DEBUG and EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
    raise ImproperlyConfigured("A production email backend is required.")
if APP_ENVIRONMENT == "production" and EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
    raise ImproperlyConfigured("Production must use the SMTP email backend.")
if not DEBUG and EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    if not all((EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)):
        raise ImproperlyConfigured("Production SMTP host and credentials are required.")
    if "@localhost" in DEFAULT_FROM_EMAIL:
        raise ImproperlyConfigured("DEFAULT_FROM_EMAIL must use a verified domain.")
if PADDLE_ENVIRONMENT not in {"sandbox", "production"}:
    raise ImproperlyConfigured("PADDLE_ENVIRONMENT must be sandbox or production.")
if PADDLE_ENABLED and not all(
    (
        PADDLE_CLIENT_TOKEN,
        PADDLE_API_KEY,
        PADDLE_WEBHOOK_SECRET,
        PADDLE_STARTER_PRICE_ID or PADDLE_PROFESSIONAL_PRICE_ID,
    )
):
    raise ImproperlyConfigured("Paddle credentials and at least one price are required.")
if APP_ENVIRONMENT == "production" and PADDLE_ENABLED and PADDLE_ENVIRONMENT != "production":
    raise ImproperlyConfigured("Production must use the Paddle production environment.")
if APP_ENVIRONMENT == "production" and not all(
    (LEGAL_ENTITY_NAME, LEGAL_ENTITY_ADDRESS, LEGAL_CONTACT_EMAIL, LEGAL_JURISDICTION)
):
    raise ImproperlyConfigured(
        "Production legal entity, address, contact and jurisdiction are required."
    )
