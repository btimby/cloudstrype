"""
Django settings for cloudstrype project.

Generated by 'django-admin startproject' using Django 1.10.5.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

# flake8: noqa

import os
import environ

from os.path import join as pathjoin


ROOT = environ.Path(__file__) - 4
ENV = environ.Env()
environ.Env.read_env(pathjoin(str(ROOT), '.env'))

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = ENV('SECRET_KEY', default='mot!1w1il6f2ub@89*3j&+)c(z9yvcfj!_le57ttqptr%_g4db')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = ENV('DEBUG', default=True)

# TODO: get into .env
ALLOWED_HOSTS = ['cloudstrype.io', 'www.cloudstrype.io', 'cloudstrype.com', 'www.cloudstrype.com']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Allows us to be an OAuth provider (maybe not necessary, but perhaps is
    # for desktop/mobile app).
    'oauth2_provider',
    # Mainly for `reset_db` management command.
    'django_extensions',
    'django_filters',

    # API.
    'rest_framework',

    # Provide endpoints for normal user login and access token creation. I
    # don't think I will end up using this, instead, I will probably use
    # oauth2_provider to allow desktop/mobile app authentication.
    'rest_framework.authtoken',
    'rest_auth',

    # Integrated apps (part of the project).
    'main',
    'api',
    'ui',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cloudstrype.urls'

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

WSGI_APPLICATION = 'cloudstrype.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': ENV.db(default='postgresql://cloudstrype:password@localhost/cloudstrype')
}


# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATIC_URL = '/static/'

# Custom settings (additions go here).

AUTH_USER_MODEL = 'main.User'

OAUTH2_PROVIDER = {
    # this is the list of available scopes
    'SCOPES': {
        'read': 'Read scope',
        'write': 'Write scope',
        'groups': 'Access to your groups'
    }
}

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.BrowsableAPIRenderer',
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.TemplateHTMLRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        #'oauth2_provider.ext.rest_framework.OAuth2Authentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
}

STATIC_ROOT = ENV('STATIC_ROOT', default='.static')

SITE_ID = 1

LOGIN_REDIRECT_URL = '/'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
        },
    },
}

# File chunk size, can be modified at any time, will only affect newly written
# chunks.
CLOUDSTRYPE_CHUNK_SIZE = 32 * 1024

# In production, we will probably send mail through a 3rd party.
EMAIL_BACKEND = ENV('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
MAILJET_API_KEY = ENV('MAILJET_API_KEY', default='')
MAILJET_API_SECRET = ENV('MAILJET_API_SECRET', default='')

# Onedrive strips out a scope before redirecting back to us.
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

if DEBUG:
    # For testing locally, don't require SSL.
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
