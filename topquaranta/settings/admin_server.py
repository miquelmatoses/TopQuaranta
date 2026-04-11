"""
Settings for the Django admin server (port 8082).
Inherits production but disables SSL redirect for HTTP access via IP.
"""

from .production import *  # noqa: F401,F403

# Allow HTTP access via IP — this server is for internal admin only
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
ALLOWED_HOSTS = ["*"]

# Caddy strips /nou-admin before proxying, so Django sees / internally.
# FORCE_SCRIPT_NAME tells Django to prefix all generated URLs with /nou-admin.
FORCE_SCRIPT_NAME = "/nou-admin"
STATIC_URL = "/nou-admin/static/"
