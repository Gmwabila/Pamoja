import os
from pathlib import Path

from django.conf.locale import LANG_INFO
from django.core.exceptions import ImproperlyConfigured

from .database import postgres_database


BASE_DIR = Path(__file__).resolve().parent.parent

ON_RENDER = os.environ.get("RENDER") == "true"

DEBUG = os.environ.get(
    "DJANGO_DEBUG",
    "0" if ON_RENDER else "1",
) == "1"

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "local-development-only-pamoja-change-before-deployment",
)

if not DEBUG and (
    not SECRET_KEY
    or SECRET_KEY.startswith("local-development")
):
    raise ImproperlyConfigured(
        "Set DJANGO_SECRET_KEY before deployment."
    )


ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS",
        "localhost,127.0.0.1,[::1],testserver" if DEBUG else "",
    ).split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "",
    ).split(",")
    if origin.strip()
]

render_hostname = os.environ.get(
    "RENDER_EXTERNAL_HOSTNAME",
    "",
).strip()

if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)
    CSRF_TRUSTED_ORIGINS.append(
        "https://" + render_hostname
    )


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.languages.ProfileLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


database_url = os.environ.get("DATABASE_URL", "").strip()

if database_url:
    DATABASES = {
        "default": postgres_database(database_url),
    }

    direct_url = os.environ.get(
        "DATABASE_URL_UNPOOLED",
        "",
    ).strip()

    if direct_url:
        DATABASES["migration"] = postgres_database(direct_url)

elif not DEBUG:
    raise ImproperlyConfigured(
        "Set DATABASE_URL to your Neon PostgreSQL "
        "connection string before deployment."
    )

else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        },
    }


AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# Languages available in PAMOJA.
LANGUAGE_CODE = "en"

LANGUAGES = [
    ("en", "English"),
    ("fr", "Français"),
    ("es", "Español"),
    ("ln", "Lingála"),
    ("sw", "Kiswahili"),
    ("ja", "日本語"),
]

# Metadata for our custom Lingala translations.
LANG_INFO.setdefault(
    "ln",
    {
        "code": "ln",
        "name": "Lingala",
        "name_local": "Lingála",
        "bidi": False,
    },
)

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

USE_I18N = True

LANGUAGE_COOKIE_NAME = "pamoja_language"
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
LANGUAGE_COOKIE_HTTPONLY = True
LANGUAGE_COOKIE_SAMESITE = "Lax"
LANGUAGE_COOKIE_SECURE = not DEBUG


TIME_ZONE = "UTC"
USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

if not DEBUG:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": (
                "whitenoise.storage."
                "CompressedManifestStaticFilesStorage"
            ),
        },
    }


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "welcome"

SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 3600
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]

if ON_RENDER:
    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )