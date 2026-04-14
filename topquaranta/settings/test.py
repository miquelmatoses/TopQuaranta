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

# API keys for tests (mocked, never called for real)
SPOTIFY_CLIENT_ID = "test-spotify-id"
SPOTIFY_CLIENT_SECRET = "test-spotify-secret"
LASTFM_API_KEY = "test-lastfm-key"
LASTFM_API_SECRET = "test-lastfm-secret"
