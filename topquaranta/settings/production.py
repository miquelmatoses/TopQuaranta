import dj_database_url
from decouple import Csv, config

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = config("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

DATABASES = {
    # P6: persistent connections. Without pooling, every request opens a
    # fresh psycopg2 connection (~5ms on localhost). `conn_max_age=600`
    # keeps the connection alive for up to 10 minutes per worker, and
    # `conn_health_checks=True` pings before reuse so a recycled-by-the-
    # server connection doesn't raise InterfaceError mid-request.
    "default": dj_database_url.config(
        default=config("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
    ),
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

# Spotify. The client-credentials ingesta flow has been blocked since
# 2024, but playlist management via user OAuth still works fine (no
# Premium required). Used by the `actualitzar_playlists_spotify` cron
# to sync the public top-40 + novetats playlists.
SPOTIFY_CLIENT_ID = config("SPOTIFY_CLIENT_ID", default="")
SPOTIFY_CLIENT_SECRET = config("SPOTIFY_CLIENT_SECRET", default="")
# Loopback redirect — Spotify allows HTTP on 127.0.0.1. Admin does the
# one-time OAuth dance via `autoritzar_spotify`; the code lands in the
# browser URL and gets pasted back into the command. No callback
# server needed in production.
SPOTIFY_REDIRECT_URI = config(
    "SPOTIFY_REDIRECT_URI", default="http://127.0.0.1:8888/callback"
)

# No SMTP is configured on this server. mail_admins() calls would try
# localhost:25 and raise ConnectionRefusedError. Route admin notifications
# to a file instead; call sites already catch errors defensively.
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = "/var/log/topquaranta/admin_mail"
