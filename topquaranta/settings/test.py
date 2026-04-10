from .base import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = "django-insecure-test-key-do-not-use-in-production"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ALLOWED_HOSTS = ["*"]
