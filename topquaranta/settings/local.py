from .base import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = "django-insecure-local-dev-key-do-not-use-in-production"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "topquaranta",
        "USER": "topquaranta",
        "PASSWORD": "topquaranta",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

ALLOWED_HOSTS = ["*"]
