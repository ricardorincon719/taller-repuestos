import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
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
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
TIME_ZONE = "America/Sao_Paulo"
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
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Taller Pro <no-reply@localhost>")
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))

if not DEBUG and SITE_URL.startswith("http://localhost"):
    raise ImproperlyConfigured("SITE_URL must use the public production URL.")
if not DEBUG and EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
    raise ImproperlyConfigured("A production email backend is required.")
