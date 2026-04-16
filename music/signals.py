"""Signals for the music app — auto-sync territories from ArtistaLocalitat."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from music.models import ArtistaLocalitat


@receiver(post_save, sender=ArtistaLocalitat)
def sync_territoris_on_localitat_save(sender, instance, **kwargs):
    """Recompute artist territories when a location is added or changed."""
    instance.artista.sync_territoris_from_localitats()


@receiver(post_delete, sender=ArtistaLocalitat)
def sync_territoris_on_localitat_delete(sender, instance, **kwargs):
    """Recompute artist territories when a location is removed."""
    # The artista may have been cascade-deleted too
    from music.models import Artista
    if Artista.objects.filter(pk=instance.artista_id).exists():
        instance.artista.sync_territoris_from_localitats()
