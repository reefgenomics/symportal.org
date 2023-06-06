import os

dbPath = os.path.join(os.path.dirname(__file__), 'db.sqlite3')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': os.getenv('SYMPORTAL_DATABASE_CONTAINER'),
        'PORT': '5432',
#	        'OPTIONS': {'timeout':200}
    }
}



# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}


INSTALLED_APPS = (
    'dbApp',
    )

SECRET_KEY = ''
