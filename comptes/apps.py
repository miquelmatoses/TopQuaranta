from django.apps import AppConfig


class ComptesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "comptes"

    def ready(self):  # noqa: D401
        # Import signal handlers so they register at app load.
        from . import signals  # noqa: F401
