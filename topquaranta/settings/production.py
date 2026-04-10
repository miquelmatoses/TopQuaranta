from decouple import config, Csv
import dj_database_url

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = config("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

DATABASES = {
    "default": dj_database_url.config(default=config("DATABASE_URL")),
}

# Security
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Last.fm
LASTFM_API_KEY = config("LASTFM_API_KEY")
LASTFM_API_SECRET = config("LASTFM_API_SECRET", default="")

# Spotify
SPOTIFY_CLIENT_ID = config("SPOTIFY_CLIENT_ID", default="")
SPOTIFY_CLIENT_SECRET = config("SPOTIFY_CLIENT_SECRET", default="")

# Telegram
TELEGRAM_BOT_TOKEN = config("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHANNEL_ID = config("TELEGRAM_CHANNEL_ID", default="")
