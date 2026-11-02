from pathlib import Path
import os

# ============================================================
# BASE DIRECTORY
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# SECURITY
# ============================================================

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-development-only-key'
)

DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
]


# ============================================================
# APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    # Django built-in apps
    'daphne',
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'channels',

    # Local apps
    'seaweed_parallel',
]

AUTH_USER_MODEL = 'seaweed_parallel.User'


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ============================================================
# URL / APPLICATION CONFIGURATION
# ============================================================

ROOT_URLCONF = 'mainProject.urls'

# Change this one path to replace the logo throughout the application.
SEASTEM_LOGO = 'images/logo.png'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # Global template directory
        'DIRS': [
            BASE_DIR / 'templates',
        ],

        'APP_DIRS': True,

        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'mainProject.context_processors.branding',
            ],
        },
    },
]


# ============================================================
# ASGI
# ============================================================

ASGI_APPLICATION = 'mainProject.asgi.application'


# ============================================================
# DATABASE
# ============================================================
# SQLite is intentional for this development/academic project.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 30,
        },
    }
}


# ============================================================
# PASSWORD VALIDATION
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'MinimumLengthValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'CommonPasswordValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'NumericPasswordValidator'
        ),
    },
]


# ============================================================
# INTERNATIONALIZATION
# ============================================================

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Manila'

USE_I18N = True

USE_TZ = True


# ============================================================
# STATIC FILES
# ============================================================

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'


# ============================================================
# MEDIA FILES
# ============================================================
# Uploaded seaweed images will be stored here during development.

MEDIA_URL = 'media/'

MEDIA_ROOT = BASE_DIR / 'media'


# ============================================================
# DJANGO CHANNELS
# ============================================================

CHANNEL_LAYERS = {
    'default': {
        # Redis 3.0.504 does not support BZPOPMIN, which the sorted-set
        # backend requires. Pub/sub keeps Channels on Redis without it.
        'BACKEND': 'channels_redis.pubsub.RedisPubSubChannelLayer',
        'CONFIG': {
            'hosts': [
                {
                    'address': 'redis://127.0.0.1:6379/2',
                    'protocol': 2,
                },
            ],
        },
    },
}


# ============================================================
# CELERY
# ============================================================

CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'

CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/1'

CELERY_ACCEPT_CONTENT = [
    'json',
]

CELERY_TASK_SERIALIZER = 'json'

CELERY_RESULT_SERIALIZER = 'json'

CELERY_TIMEZONE = 'Asia/Manila'

CELERY_BROKER_TRANSPORT_OPTIONS = {
    'protocol': 2,
}

CELERY_WORKER_PREFETCH_MULTIPLIER = 1

CELERY_TASK_ACKS_LATE = True

CELERY_TASK_TRACK_STARTED = True


# ============================================================
# DJANGO REST FRAMEWORK
# ============================================================

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
}

LOGIN_URL = 'signin'


# ============================================================
# EMAIL
# ============================================================
# Development only: emails appear in the terminal.

EMAIL_BACKEND = (
    'django.core.mail.backends.console.EmailBackend'
)


# ============================================================
# DEFAULT PRIMARY KEY
# ============================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


