from pathlib import Path
import sys

import environ
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
env.read_env(BASE_DIR / ".env")

# Define TEST_MODE early for Sentry configuration
TEST_MODE = "test" in sys.argv

SENTRY_DSN = env("SENTRY_DSN", default=None)
# Don't initialize Sentry during test runs to avoid capturing test errors
if SENTRY_DSN and not TEST_MODE:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        send_default_pii=True,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

# Core Django settings
DEBUG = env("DEBUG", default=False)  # Default to True for development
SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-dev-key-change-in-production" if DEBUG else None,
)  # Required - no default for security in production
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "acclaimedvideogames.com",
    "www.acclaimedvideogames.com",
]
SITE_ID = 1
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ROOT_URLCONF = "acclaimedgames.urls"
WSGI_APPLICATION = "acclaimedgames.wsgi.application"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.flatpages",
    "django.contrib.sites",
    "django.contrib.postgres",
    "django.contrib.humanize",
    "django.forms",
    "corsheaders",
    "django_extensions",
    "rest_framework",
    "games",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.flatpages.middleware.FlatpageFallbackMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "games.middleware.HTMXPushURLMiddleware",  # HTMX history support
]

# Only enable cache middleware in production
if not DEBUG:
    MIDDLEWARE.insert(0, "django.middleware.cache.UpdateCacheMiddleware")
    MIDDLEWARE.append("django.middleware.cache.FetchFromCacheMiddleware")

# Enable debug toolbar only in development
if DEBUG:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        # When loaders is explicitly defined, APP_DIRS must be False
        # The app_directories loader is included in the loaders list instead
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            # In development, don't use cached template loader
            # This ensures template changes are picked up immediately
            "loaders": (
                [
                    "django.template.loaders.filesystem.Loader",
                    "django.template.loaders.app_directories.Loader",
                ]
                if DEBUG
                else [
                    (
                        "django.template.loaders.cached.Loader",
                        [
                            "django.template.loaders.filesystem.Loader",
                            "django.template.loaders.app_directories.Loader",
                        ],
                    ),
                ]
            ),
        },
    },
]

DATABASES = {
    "default": env.db(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

# Add SQLite timeout to prevent "database is locked" errors during concurrent writes
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"]["OPTIONS"] = {
        "timeout": 20,  # Increase timeout from default 5 seconds to 20 seconds
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
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

# Authentication URLs
LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

INTERNAL_IPS = [
    "127.0.0.1",
]

# Cache configuration - use dummy cache for development if no CACHE_URL set
cache_url = env("CACHE_URL", default=None)
if cache_url:
    CACHES = {
        "default": env.cache(),
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }

CACHE_MIDDLEWARE_SECONDS = 60 * 60

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 100,
}

IGDB_CLIENT_ID = env("IGDB_CLIENT_ID", default="XXX")
IGDB_CLIENT_SECRET = env("IGDB_CLIENT_SECRET", default="XXX")
IGDB_USE_PRO_TIER = env.bool("IGDB_USE_PRO_TIER", default=False)

# Logging configuration
# Suppress noisy logs during test runs
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "games.igdb": {
            "handlers": ["console"],
            "level": "ERROR" if TEST_MODE else "WARNING",
        },
        "games.management.commands.get_igdb": {
            "handlers": ["console"],
            "level": "CRITICAL" if TEST_MODE else "INFO",
        },
    },
}
