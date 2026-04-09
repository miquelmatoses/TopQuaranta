# web_cms/tqcms/settings/production.py
import os

from .base import *

# ── SECRET_KEY des de .env i validació mínima ────────────────────────────────
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-"):
    raise RuntimeError(
        "Configureu DJANGO_SECRET_KEY a .env amb una clau llarga i aleatòria (>= 50 caràcters)."
    )

DEBUG = False

# ── Proxy/TLS darrere de Caddy ────────────────────────────────────────────────
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── Hosts i CSRF ──────────────────────────────────────────────────────────────
ALLOWED_HOSTS = [
    "www.topquaranta.cat",
    "topquaranta.cat",
    "localhost",
    "127.0.0.1",
]

PREPEND_WWW = True

CSRF_TRUSTED_ORIGINS = [
    "https://www.topquaranta.cat",
    "https://topquaranta.cat",
]


# ── Cookies segures ──────────────────────────────────────────────────────────
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True  # ja és True per defecte, però ho fem explícit
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ── Seguretat en prod ────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# HSTS: comença curt i puja quan estiga tot OK (p.ex. 30d → 180d → 365d)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ── Wagtail ──────────────────────────────────────────────────────────────────
WAGTAILADMIN_BASE_URL = "https://www.topquaranta.cat"

# ── Email (SMTP real via .env) ───────────────────────────────────────────────
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# ── Autenticació (si uses allauth) ───────────────────────────────────────────
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
ACCOUNT_UNIQUE_EMAIL = True  # correus únics
# —— Allauth rate limits (substitueix intents de login deprecats) ——
ACCOUNT_RATE_LIMITS = {
    # màxim 5 intents fallits per IP/usuari cada 5 minuts
    "login_failed": "5/5m",
    # opcionalment limita signup/reset si vols
    # "signup": "10/h",
    # "reset_password": "5/15m",
}

# ── Logging a consola (ideal per a containers/systemd) ───────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# Assume https by default for URLField (prepara Django 6)
FORMS_URLFIELD_ASSUME_HTTPS = True

SILENCED_SYSTEM_CHECKS = ["security.W019"]
