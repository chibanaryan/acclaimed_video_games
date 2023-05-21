
from pathlib import Path

import environ
from django.contrib import messages

root = environ.Path(__file__) - 2
env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env()


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

    'django_extensions',
    'debug_toolbar',

    'games',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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