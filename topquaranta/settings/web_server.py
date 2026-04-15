"""
Settings for the public web server (port 8083).
Inherits production settings without FORCE_SCRIPT_NAME.
"""

from .production import *  # noqa: F401,F403

# Caddy terminates TLS and proxies HTTP internally
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

ALLOWED_HOSTS = ["www.topquaranta.cat", "topquaranta.cat", "legacy.topquaranta.cat", "127.0.0.1"]

STATIC_URL = "/static/"
