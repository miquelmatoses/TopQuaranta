"""Auto-create PerfilUsuari on Usuari creation.

Every authenticated surface in the app assumes `usuari.perfil` exists —
onboarding, directori, publicacions. This signal ensures that's always
true, even for users created via `createsuperuser`, the admin, or the
Django API, not just the `registre` form.
"""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_perfil_usuari(sender, instance, created, **kwargs):
    """Ensure every Usuari has a PerfilUsuari 1:1 companion."""
    if not created:
        return
    # Late import so we don't touch PerfilUsuari before the app is fully
    # loaded (signals.py runs from AppConfig.ready()).
    from .models import PerfilUsuari

    PerfilUsuari.objects.get_or_create(usuari=instance)
