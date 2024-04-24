
from pathlib import Path

import environ
import sentry_sdk
from django.contrib import messages
from sentry_sdk.integrations.django import DjangoIntegration

root = environ.Path(__file__) - 2
env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env()

sentry_sdk.init(
    dsn="https://464839bc01a7d54f332ce808c6b6868b@o72598.ingest.sentry.io/4505695966789632",
    integrations=[DjangoIntegration()],
    send_default_pii=True,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = env('DEBUG', default=False)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'en-us'
ROOT_URLCONF = 'acclaimedgames.urls'
SECRET_KEY = env('SECRET_KEY', default='XXX')
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = 'static/'
TIME_ZONE = 'UTC'
USE_I18N = False
USE_TZ = False
WSGI_APPLICATION = 'acclaimedgames.wsgi.application'
SITE_ID = 1

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.flatpages',
    'django.contrib.sites',
    'django.contrib.postgres',
    'django.forms',
    'corsheaders',

    'django_extensions',
    # 'debug_toolbar',
    'crispy_forms',
    'crispy_bulma',
    'rest_framework',

    'games',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.cache.UpdateCacheMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

# if DEBUG:
#     INSTALLED_APPS.append('debug_toolbar')
#     MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR/'frontend/dist'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


DATABASES = {
    'default': env.db(),
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

INTERNAL_IPS = [
    '127.0.0.1',
]

ALLOWED_HOSTS = [
    '127.0.0.1',
    '192.168.0.67',
    'sean2000.pythonanywhere.com',
    'acclaimedgames.herokuapp.com',
    'acclaimedvideogames.com',
    'www.acclaimedvideogames.com',
]

CACHES = {
    'default': env.cache(),
}

CACHE_MIDDLEWARE_SECONDS = 60 * 60 * 24

MESSAGE_TAGS = {
    messages.INFO: "is-primary",
    messages.ERROR: "is-danger",
}

IGDB_CLIENT_ID = env('IGDB_CLIENT_ID', default='XXX')
IGDB_CLIENT_SECRET = env('IGDB_CLIENT_SECRET', default='XXX')

CRISPY_ALLOWED_TEMPLATE_PACKS = ["bulma"]
CRISPY_TEMPLATE_PACK = "bulma"

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [],
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 100,
}
CORS_ALLOWED_ORIGINS = ['http://127.0.0.1:8080', 'http://localhost:8080']

STATICFILES_DIRS = [
    BASE_DIR / 'frontend/dist/static'
]
