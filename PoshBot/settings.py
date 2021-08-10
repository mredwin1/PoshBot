"""
Django settings for PoshBot project.

Generated by 'django-admin startproject' using Django 3.1.6.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""
import os

from celery.schedules import crontab
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ['SECRET_KEY']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(int(os.environ['DEBUG']))

if DEBUG:
    ALLOWED_HOSTS = ['127.0.0.1', '0.0.0.0', 'localhost', 'poshbot.localhost']
else:
    ALLOWED_HOSTS = [os.environ['DOMAIN'], f'www.{os.environ["DOMAIN"]}']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'users.apps.UsersConfig',
    'poshmark.apps.PoshmarkConfig',
    'crispy_forms',
    'imagekit',
    'django_cleanup.apps.CleanupConfig',  # This always has to be last in order to discover all file fields properly
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'PoshBot.urls'

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

WSGI_APPLICATION = 'PoshBot.wsgi.application'


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'class': 'logging.FileHandler',
            'filename': 'django.log',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}


# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": 'django.db.backends.postgresql',
        "NAME": os.environ['SQL_DATABASE'],
        "USER": os.environ['SQL_USER'],
        "PASSWORD": os.environ['SQL_PASSWORD'],
        "HOST": os.environ['SQL_HOST'],
        "PORT": os.environ['SQL_PORT'],
    }
}


# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

MEDIA_URL = '/media/'
MEDIA_ROOT = '/shared_volume/media'

# Crispy Forms
CRISPY_TEMPLATE_PACK = 'bootstrap4'

# Custom User & Log In
AUTH_USER_MODEL = 'users.User'
LOGIN_REDIRECT_URL = 'home'
LOGIN_URL = 'login'

# Redis Settings
REDIS_HOST = 'redis'
REDIS_PORT = 6379

# Celery Settings
CELERY_BROKER_URL = f'{REDIS_HOST}://{REDIS_HOST}:{REDIS_PORT}'
CELERY_RESULT_BACKEND = f'{REDIS_HOST}://{REDIS_HOST}:{REDIS_PORT}'

CELERY_TASK_ROUTES = {
    'poshmark.tasks.basic_sharing': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.advanced_sharing': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.start_campaign': {'queue': 'no_concurrency', 'routing_key': 'no_concurrency'},
    'poshmark.tasks.restart_task': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.redis_log_reader': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.redis_instance_reader': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.log_cleanup': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.redis_cleaner': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.posh_user_balancer': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.register_gmail': {'queue': 'gmail_registration', 'routing_key': 'gmail_registration'},
    'poshmark.tasks.register_posh_user': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.enable_email_forwarding': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.gmail_proxy_reset': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.generate_posh_users': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.assign_posh_users': {'queue': 'concurrency', 'routing_key': 'concurrency'},
    'poshmark.tasks.list_item': {'queue': 'concurrency', 'routing_key': 'concurrency'},
}

# Periodic Tasks
CELERY_BEAT_SCHEDULE = {
    'log_cleanup': {
        'task': 'poshmark.tasks.log_cleanup',
        'schedule': crontab(minute=0, hour=0),
        'options': {'queue': 'concurrency'}
    },
    'redis_cleaner': {
        'task': 'poshmark.tasks.redis_cleaner',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'concurrency'}
    },
#     'posh_user_balancer': {
#         'task': 'poshmark.tasks.posh_user_balancer',
#         'schedule': crontab(minute='*/2'),
#         'options': {'queue': 'concurrency'}
#     },
#     'gmail_proxy_reset': {
#         'task': 'poshmark.tasks.gmail_proxy_reset',
#         'schedule': crontab(minute='*/1'),
#         'options': {'queue': 'concurrency'}
#     },
}
