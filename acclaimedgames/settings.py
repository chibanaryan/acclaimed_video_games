from pathlib import Path
import sys

import environ
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
env.read_env(BASE_DIR / ".env")
# Load local development overrides if present (higher priority)
local_env = BASE_DIR / ".env.development.local"
if local_env.exists():
    env.read_env(local_env, overwrite=True)

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
APPEND_SLASH = True  # Automatically redirect URLs without trailing slashes

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
    "django.contrib.sitemaps",
    "django.forms",
    "corsheaders",
    "rest_framework",
    "tailwind",
    "theme",
    "core",
    "games",
    "books",
    # django-allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
]

# django-tailwind configuration
TAILWIND_APP_NAME = "theme"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Must be after SecurityMiddleware
    "django.middleware.gzip.GZipMiddleware",  # Compress HTML responses (48 KiB savings)
    # "games.csp_middleware.CSPMiddleware",  # Disabled: nonce mismatch
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.flatpages.middleware.FlatpageFallbackMiddleware",
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
                "games.context_processors.csp_nonce",  # CSP nonce for templates
                "games.context_processors.feature_flags",  # Feature flags
                "games.context_processors.media_type",  # Current media type (games/books)
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

# Use in-memory SQLite for faster tests (each parallel process gets its own DB)
if TEST_MODE:
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
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

# Custom User model
AUTH_USER_MODEL = "games.User"

# Authentication URLs
LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"
LOGOUT_REDIRECT_URL = "/"

# Authentication backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# django-allauth configuration
ACCOUNT_ADAPTER = "games.adapters.ModalAccountAdapter"
SOCIALACCOUNT_ADAPTER = "games.adapters.ModalSocialAccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email", "username"}  # Allow both email and username login
ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "password1*",
    "password2*",
]  # Email required, no username for signup
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_PREVENT_ENUMERATION = False  # Show "email already exists" error on signup form
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""  # No prefix in email subjects
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
SOCIALACCOUNT_AUTO_SIGNUP = True

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
    # Use file-based cache as default to persist across development server restarts
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": BASE_DIR / "django_cache",
        }
    }

CACHE_MIDDLEWARE_SECONDS = 60 * 60

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []

# WhiteNoise configuration for compression and caching
# Creates hashed filenames (e.g., main.a1b2c3d4.css) for cache busting
# Creates gzip and brotli compressed versions automatically
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# WhiteNoise caching optimizations
# Note: CORS headers for font files are handled in CSP middleware
# Cache static files for 1 year (safe because filenames include content hash)
WHITENOISE_MAX_AGE = 31536000  # 1 year in seconds

# Add 'immutable' to Cache-Control for hashed files (prevents revalidation checks)
# Files with content hash in name never need revalidation
# Note: WhiteNoise automatically adds 'immutable' for files with content hashes
# WHITENOISE_IMMUTABLE_FILE_TEST can be customized if needed

# Enable aggressive compression (gzip + brotli)
WHITENOISE_KEEP_ONLY_HASHED_FILES = True  # Remove non-hashed files in production

# Allow WhiteNoise to serve index files (e.g., index.html)
WHITENOISE_INDEX_FILE = False  # Django handles routing, not static file serving

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

# Wikidata API authentication (optional - for 10x faster rate limits)
# Format: username@botname:password
# (from https://meta.wikimedia.org/wiki/Special:BotPasswords)
WIKIDATA_ACCESS_TOKEN = env("WIKIDATA_ACCESS_TOKEN", default=None)

# Email configuration (Brevo SMTP)
# In dev: print to console. In prod: send via Brevo SMTP.
# Brevo requires verified sender - contact@acclaimedvideogames.com is verified
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp-relay.brevo.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "9c6ed8001@smtp-brevo.com"
EMAIL_HOST_PASSWORD = env("BREVO_SMTP_KEY", default="")

DEFAULT_FROM_EMAIL = "Acclaimed Video Games <contact@acclaimedvideogames.com>"
CONTACT_EMAIL = "contact@acclaimedvideogames.com"
SITE_URL = env(
    "SITE_URL",
    default="http://localhost:8000" if DEBUG else "https://www.acclaimedvideogames.com",
)

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
        "games.signals": {
            "handlers": ["console"],
            "level": "ERROR" if TEST_MODE else "INFO",
        },
        "games.utils": {
            "handlers": ["console"],
            "level": "ERROR" if TEST_MODE else "INFO",
        },
    },
}

# Security settings
# These headers help protect against common web vulnerabilities
SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME type sniffing
X_FRAME_OPTIONS = "DENY"  # Prevent clickjacking

# Production-only security settings (require HTTPS)
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000  # 1 year - enable HTTP Strict Transport Security
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True  # Only send session cookie over HTTPS
    CSRF_COOKIE_SECURE = True  # Only send CSRF cookie over HTTPS
    SECURE_SSL_REDIRECT = True  # Redirect HTTP to HTTPS
