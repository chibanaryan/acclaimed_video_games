import importlib.util
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

import environ
from django.utils.csp import CSP
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from core.cache_config import build_caches, release_cache_prefix
from core.csp import handler_hash, sentry_enabled, sentry_report_uri

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
env.read_env(BASE_DIR / ".env")
# Load local development overrides if present (higher priority)
local_env = BASE_DIR / ".env.development.local"
if local_env.exists():
    env.read_env(local_env, overwrite=True)

# Define TEST_MODE early for Sentry configuration
# Check both Django's manage.py test and pytest
TEST_MODE = "test" in sys.argv or "pytest" in sys.modules
RUNNING_DEVSERVER = "runserver" in sys.argv

SENTRY_DSN = env("SENTRY_DSN", default=None)
# Heroku sets DYNO on every dyno; anywhere else is a developer's machine.
# A blank value counts as unset: it must not turn reporting on from a laptop.
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="") or (
    "production" if "DYNO" in os.environ else "development"
)
SENTRY_ENABLED = sentry_enabled(
    SENTRY_DSN, SENTRY_ENVIRONMENT, test_mode=TEST_MODE, argv=sys.argv
)
if SENTRY_ENABLED:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        integrations=[DjangoIntegration()],
        # Deprecated in sentry-sdk 2.7x in favour of data_collection, but kept:
        # passing data_collection turns off the EventScrubber, which is what
        # filters passwords and tokens out of request bodies and frame locals.
        send_default_pii=True,
        # Sampled, not exhaustive: tracing and profiling every request cost
        # per-request CPU and latency on a dyno that has neither to spare,
        # and burn the Sentry quota. Errors are still captured in full.
        traces_sample_rate=0.1,
        profiles_sample_rate=0.0,
    )

# Core Django settings
DEBUG = env("DEBUG", default=False)  # Default to True for development

# Feature flags - Books app is in development, only show in DEBUG/TEST mode
BOOKS_ENABLED = DEBUG or TEST_MODE

SECRET_KEY = env(
    "SECRET_KEY",
    default=(
        "django-insecure-dev-key-change-in-production" if (DEBUG or TEST_MODE) else None
    ),
)  # Required - no default for security in production
# The apex's public origin: the landing page, emails, the fetchers'
# User-Agent. Unlike SITE_URL it does not follow DEBUG, so a local render
# carries the same canonical tags as production. www.acclaimedmedia.org is
# 301'd to it, and the old acclaimedvideogames.com hosts to the games site,
# by Cloudflare redirect rules that never reach Django (see "Domain" in
# AGENTS.md).
CANONICAL_ORIGIN = "https://acclaimedmedia.org"
# The three sites the one app serves, by host (core/sites.py): the landing
# page at the apex, games and music on their own subdomains. Each origin is
# what that site's canonical links, sitemap and structured data name.
SITE_ORIGINS = {
    "root": CANONICAL_ORIGIN,
    "games": "https://games.acclaimedmedia.org",
    "music": "https://music.acclaimedmedia.org",
}
SITE_URLCONFS = {
    "root": "acclaimedgames.urls_root",
    "games": "acclaimedgames.urls_games",
    "music": "acclaimedgames.urls_music",
}
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "acclaimedmedia.org",
    "games.acclaimedmedia.org",
    "music.acclaimedmedia.org",
]
if DEBUG:
    # games.localhost:8000 and music.localhost:8000, which browsers resolve
    # to loopback, are how the subdomains are reached in development
    ALLOWED_HOSTS.append(".localhost")
if TEST_MODE:
    # The test client's host; it was listed unconditionally, so production
    # answered requests that named it
    ALLOWED_HOSTS.append("testserver")
SITE_ID = 1
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# A request to a known host gets that site's URLconf from
# core.middleware.SiteHostMiddleware; any other host (the test client's
# "testserver", 127.0.0.1) gets this one, the games site.
ROOT_URLCONF = SITE_URLCONFS["games"]
WSGI_APPLICATION = "acclaimedgames.wsgi.application"
APPEND_SLASH = True  # Automatically redirect URLs without trailing slashes

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    # Before staticfiles: `runserver` then leaves static files to WhiteNoise,
    # which sends WHITENOISE_MAX_AGE (0 in development). Django's own static
    # handler sends no Cache-Control at all, so a browser cached a script by
    # heuristic - a tenth of its age since Last-Modified - and kept serving
    # the old code after an edit. Only the runserver command is affected.
    "whitenoise.runserver_nostatic",
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
    "music",
    # django-allauth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
    "django_extensions",
]


# django-tailwind configuration
TAILWIND_APP_NAME = "theme"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Picks the site (landing, games, music) and its URLconf from the host
    "core.middleware.SiteHostMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Must be after SecurityMiddleware
    # Tiny 200 for Sentry's uptime monitor that refuses gzip (667 KB a minute)
    "games.middleware.UncompressedUptimeCheckMiddleware",
    "games.middleware.RateLimitMiddleware",  # Bot/crawler rate limiting
    # Compress HTML responses (48 KiB savings); skips SSE streams
    "games.middleware.EventStreamAwareGZipMiddleware",
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

# There is deliberately no site-wide `UpdateCacheMiddleware` /
# `FetchFromCacheMiddleware` pair. Every page here varies on `Cookie` - the
# auth-aware chrome and the CSRF token see to that - so the middleware keyed a
# separate copy of each page on each visitor's cookie header, while declining
# to store anything at all for a first-time visitor who has none. Three
# workers' worth of per-visitor HTML was most of why the dyno sat over its
# 512 MB quota. `core.mixins.AnonymousResponseCacheMixin` is the whole-page
# cache instead: anonymous requests only, one key per URL, and only for the
# pages worth it.

# Enable debug toolbar only in development. It is in requirements-dev.txt, not
# the production lock, so DEBUG on a production install must not need it.
DEBUG_TOOLBAR = DEBUG and importlib.util.find_spec("debug_toolbar") is not None
if DEBUG_TOOLBAR:
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
                "django.template.context_processors.csp",  # {{ csp_nonce }}
                "games.context_processors.feature_flags",  # Feature flags
                "games.context_processors.media_type",  # Current media type
                "games.context_processors.canonical_origin",  # Public origin
            ],
            # In development/tests, don't use cached template loader
            # This ensures template changes are picked up immediately
            # and Django's test client can track templates used.
            # Both branches strip template indentation at load time
            # (core/template_loaders.py), so dev renders what prod renders.
            "loaders": (
                [
                    "core.template_loaders.FilesystemLoader",
                    "core.template_loaders.AppDirectoriesLoader",
                ]
                if DEBUG or TEST_MODE
                else [
                    (
                        "django.template.loaders.cached.Loader",
                        [
                            "core.template_loaders.FilesystemLoader",
                            "core.template_loaders.AppDirectoriesLoader",
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
        # Take the write lock when a transaction begins. Under the default
        # (DEFERRED), two requests that each read and then write inside
        # transaction.atomic - the tracking toggles do - both hold read
        # locks, and SQLite fails one at once with "database is locked"
        # rather than waiting out the timeout. Postgres needs no such thing.
        "transaction_mode": "IMMEDIATE",
    }

# Use in-memory SQLite for faster tests (each parallel process gets its own DB).
# CI's django-tests job sets TEST_DATABASE_URL, because SQLite enforces neither
# varchar lengths nor some constraints that production's Postgres does.
if TEST_MODE:
    DATABASES["default"] = env.db("TEST_DATABASE_URL", default="sqlite://:memory:")

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
AUTH_USER_MODEL = "core.User"

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

# Cache configuration. `core.cache_config` explains why there are two
# aliases: `default` is shared across processes (DatabaseCache in production),
# `local` is per-process and holds whole-page HTML and rate-limit counters.
CACHES = build_caches(
    env("CACHE_URL", default=None),
    debug=DEBUG,
    test_mode=TEST_MODE,
    base_dir=BASE_DIR,
)
# The release, for the API's page caches only; see release_cache_prefix
RELEASE_CACHE_PREFIX = (
    "" if TEST_MODE else release_cache_prefix(os.environ.get("HEROKU_RELEASE_VERSION"))
)

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []

# WhiteNoise configuration for compression and caching
# Creates hashed filenames (e.g., main.a1b2c3d4.css) for cache busting
# Creates gzip and brotli compressed versions automatically
# Use simple storage for tests (manifest-based storage requires collectstatic)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if TEST_MODE
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

# WhiteNoise caching optimizations
# Note: CORS headers for font files are handled in CSP middleware
# Cache static files for 1 year in production, where every name carries a
# content hash, so a changed file is a new URL and no `?v=` literal is needed.
# In development names are unhashed: a year's cache there kept a browser on
# the old JS after an edit, which is all the `?v=` literals were for. Zero is
# WhiteNoise's own default under DEBUG.
WHITENOISE_MAX_AGE = 0 if DEBUG else 31536000  # 1 year in seconds

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
    "DEFAULT_PAGINATION_CLASS": "core.pagination.CappedLimitOffsetPagination",
    "PAGE_SIZE": 100,
    "DEFAULT_THROTTLE_CLASSES": ["core.throttling.ClientIPAnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "60/minute"},
}

IGDB_CLIENT_ID = env("IGDB_CLIENT_ID", default="XXX")
IGDB_CLIENT_SECRET = env("IGDB_CLIENT_SECRET", default="XXX")
IGDB_USE_PRO_TIER = env.bool("IGDB_USE_PRO_TIER", default=False)

# Wikidata API authentication (optional - for 10x faster rate limits)
# Format: username@botname:password
# (from https://meta.wikimedia.org/wiki/Special:BotPasswords)
WIKIDATA_ACCESS_TOKEN = env("WIKIDATA_ACCESS_TOKEN", default=None)

# Discogs API authentication (optional - raises the rate limit above the 25
# requests/minute the anonymous tier reports). A free personal access token
# from https://www.discogs.com/settings/developers is enough; the music
# metadata client reads the limit off the response headers either way.
DISCOGS_TOKEN = env("DISCOGS_TOKEN", default=None)

# Tests run without outside credentials, as CI does. A developer's .env
# holds real ones, and with them a test that did not patch its client got a
# live IGDB token from Twitch: local and CI runs took different paths, and
# conftest.py now refuses outside connections anyway.
if TEST_MODE:
    IGDB_CLIENT_ID = IGDB_CLIENT_SECRET = "XXX"
    WIKIDATA_ACCESS_TOKEN = DISCOGS_TOKEN = None

# Email configuration (Brevo SMTP)
# In dev: print to console. In prod: send via Brevo SMTP.
# Brevo requires verified sender - contact@acclaimedvideogames.com is verified
# MAILERS replaces the EMAIL_* settings, which Django 6.1 deprecates.
if DEBUG:
    MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
else:
    MAILERS = {
        "default": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {
                "host": "smtp-relay.brevo.com",
                "port": 587,
                "use_tls": True,
                "username": env("BREVO_SMTP_USER", default=""),
                "password": env("BREVO_SMTP_KEY", default=""),
            },
        }
    }

DEFAULT_FROM_EMAIL = "Acclaimed Media <contact@acclaimedvideogames.com>"
CONTACT_EMAIL = "contact@acclaimedvideogames.com"
SITE_URL = env(
    "SITE_URL",
    default="http://localhost:8000" if DEBUG else CANONICAL_ORIGIN,
)

# Logging configuration
# Suppress noisy logs during test runs
# Each app logs INFO and up through one handler, labelled with level and
# logger name (Heroku adds the timestamp). Until 2026-10-26 only seven named
# loggers had a handler, so refresh_all_metadata, music.discogs,
# music.wikidata and every other unnamed module lost their INFO lines, and
# their warnings went out through Python's bare last-resort handler. The
# narrower loggers below only set a level and inherit the app's handler, so
# nothing prints twice. The root logger is left alone: a handler there would
# also print Django's 404 warnings, which on a public site is mostly bots.
_APP_LOG_LEVEL = "ERROR" if TEST_MODE else "INFO"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "labelled": {"format": "%(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "labelled",
        },
    },
    "loggers": {
        **{
            app: {
                "handlers": ["console"],
                "level": _APP_LOG_LEVEL,
                "propagate": False,
            }
            for app in ("games", "music", "core", "books")
        },
        "games.igdb": {"level": "ERROR" if TEST_MODE else "WARNING"},
        "games.management.commands.get_igdb": {
            "level": "CRITICAL" if TEST_MODE else "INFO"
        },
        "games.middleware": {"level": "ERROR" if TEST_MODE else "WARNING"},
        # Temporary: SentryUptimeBot's trace headers, for Sentry Support
        "games.middleware.uptime": {"level": "ERROR" if TEST_MODE else "INFO"},
    },
}

# Content Security Policy, report-only for now (2026-10-26): violations are
# reported, nothing is blocked. Enforcing it is a matter of moving this dict
# to SECURE_CSP once the reports are quiet.
# - Scripts: this origin, the request's nonce (every inline <script> carries
#   {{ csp_nonce }}; AnonymousResponseCacheMixin re-mints it on a cached
#   page, and htmx copies it onto the scripts a swap brings in), Google
#   Analytics, and the admin's Cloudinary widget. 'unsafe-eval' because
#   Alpine evaluates its expressions with new Function. 'unsafe-hashes' with
#   one hash allows exactly the tracking buttons' onclick="event.
#   stopPropagation()", which sit on rows that carry no Alpine on purpose.
# - Styles: 'unsafe-inline' without a nonce, since a nonce would disable it
#   and style="" attributes are everywhere.
# - Images: any https host, since articles embed images from anywhere.
# - Connections: the hosts gtag.js sends its hits to. www.google.com is
#   scoped to /g/collect, the one path it posts to there, so the rest of
#   google.com stays out.
# - Forms: the Donate page's PayPal buttons, by path, as for www.google.com.
# Reports go to Sentry's CSP endpoint, derived from the DSN.
_CSP_STOP_PROPAGATION = handler_hash("event.stopPropagation()")
SECURE_CSP_REPORT_ONLY = {
    "default-src": [CSP.SELF],
    "script-src": [
        CSP.SELF,
        CSP.NONCE,
        CSP.UNSAFE_EVAL,
        CSP.UNSAFE_HASHES,
        _CSP_STOP_PROPAGATION,
        "https://www.googletagmanager.com",
        "https://upload-widget.cloudinary.com",
        # The admin article preview's markdown renderer, by path
        "https://cdn.jsdelivr.net/npm/marked/",
    ],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:", "https:"],
    "font-src": [CSP.SELF, "data:"],
    "media-src": [CSP.SELF],
    "connect-src": [
        CSP.SELF,
        "https://*.google-analytics.com",
        "https://*.analytics.google.com",
        "https://*.googletagmanager.com",
        # GA4's hits to www.google.com, by path (2026-10-29)
        "https://www.google.com/g/collect",
    ],
    "frame-src": ["https://upload-widget.cloudinary.com"],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF, "https://www.paypal.com/donate"],
    "frame-ancestors": [CSP.NONE],
}
_csp_report_uri = sentry_report_uri(SENTRY_DSN) if SENTRY_ENABLED else None
if _csp_report_uri:
    SECURE_CSP_REPORT_ONLY["report-uri"] = [_csp_report_uri]

# Renamed when the cookies moved to the whole acclaimedmedia.org domain (see
# the production block below): a host-only cookie of the old name, left on
# the apex by an earlier visit, would otherwise be sent beside the new one,
# and Django keeps whichever the browser lists last. JavaScript that reads
# the CSRF cookie reads this name.
SESSION_COOKIE_NAME = "am_sessionid"
CSRF_COOKIE_NAME = "am_csrftoken"

# Security settings
# These headers help protect against common web vulnerabilities
SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME type sniffing
X_FRAME_OPTIONS = "DENY"  # Prevent clickjacking

# Production-only security settings (require HTTPS)
# Exclude TEST_MODE since tests run with DEBUG=False but shouldn't have HTTPS redirect
if not DEBUG and not TEST_MODE and not RUNNING_DEVSERVER:
    SECURE_HSTS_SECONDS = 31536000  # 1 year - enable HTTP Strict Transport Security
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # allauth's links built without a request; with one they follow its scheme
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
    SESSION_COOKIE_SECURE = True  # Only send session cookie over HTTPS
    CSRF_COOKIE_SECURE = True  # Only send CSRF cookie over HTTPS
    # One sign-in across the games and music subdomains and the apex
    SESSION_COOKIE_DOMAIN = CSRF_COOKIE_DOMAIN = (
        "." + urlsplit(CANONICAL_ORIGIN).hostname
    )
    SECURE_SSL_REDIRECT = True  # Redirect HTTP to HTTPS
