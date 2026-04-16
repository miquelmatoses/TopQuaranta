from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    # Django
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "axes",  # S4: brute-force login protection
    # Project apps
    "music",
    "ingesta",
    "ranking",
    "web",
    "comptes",
]

AUTH_USER_MODEL = "comptes.Usuari"

# S10: Argon2 is preferred; PBKDF2 variants retained so existing hashes
# continue to verify. Django rehashes to Argon2 on next successful login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# S4: django-axes authentication backend intercepts failed login attempts.
# Must be first in the list. ModelBackend stays after it for actual auth.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # S4: must come AFTER AuthenticationMiddleware so request.user is set.
    "axes.middleware.AxesMiddleware",
]

# S4: django-axes configuration. Lock out after 5 failed attempts per
# (username, IP) tuple for 1 hour; after 10 attempts, lock for 24 hours.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours for the first-tier lockout
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "web/403.html"

ROOT_URLCONF = "topquaranta.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "web.context_processors.current_year",
                "web.context_processors.user_header_info",
            ],
        },
    },
]

WSGI_APPLICATION = "topquaranta.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ca"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    ("mm-design", BASE_DIR / "node_modules" / "mm-design"),
]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ADMINS = [("TopQuaranta", "admin@topquaranta.cat")]
DEFAULT_FROM_EMAIL = "noreply@topquaranta.cat"
SERVER_EMAIL = "noreply@topquaranta.cat"

_LOG_DIR = Path("/var/log/topquaranta")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        # All ERROR / CRITICAL log records across the project are appended to
        # a single file. Consumed by bin/tq-health.sh and the ops dashboard;
        # see CLAUDE_PIPELINE.md (monitoring section).
        "errors_file": {
            "class": "logging.FileHandler",
            "filename": str(_LOG_DIR / "errors.log"),
            "formatter": "verbose",
            "level": "ERROR",
            # delay=True means the file is not opened until first use; avoids
            # startup failures in environments where /var/log/topquaranta is
            # not writable (e.g. tests, CI).
            "delay": True,
        },
    },
    "root": {
        "handlers": ["console", "errors_file"],
        "level": "INFO",
    },
    "loggers": {
        "ingesta": {"level": "INFO"},
        "ranking": {"level": "INFO"},
    },
}
