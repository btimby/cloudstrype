from .settings import *


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'cloudstrype',
        'USER': 'cloudstrype',
        'PASSWORD': '',
        'HOST': 'localhost',
    }
}