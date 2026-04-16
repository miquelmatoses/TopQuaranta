"""Signals for the music app — auto-sync territories from ArtistaLocalitat.

R12: the signal is wrapped in `transaction.on_commit()` so the territory
M2M is recomputed once, after the surrounding transaction commits, instead
of N times in the middle of an `atomic()` block (one per ArtistaLocalitat
row inserted/updated). The previous behaviour produced inconsistent
intermediate states visible to concurrent readers.
"""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from music.models import ArtistaLocalitat


def _resync(artista_id: int) -> None:
    """Resolve the artist by id and resync its territories.

    Defensive lookup: if the artist (or the localitat that triggered us)
    has been cascade-deleted between the signal firing and the on_commit
    callback running, do nothing.
    """
    from music.models import Artista

    artista = Artista.objects.filter(pk=artista_id).first()
    if artista is not None:
        artista.sync_territoris_from_localitats()


@receiver(post_save, sender=ArtistaLocalitat)
def sync_territoris_on_localitat_save(sender, instance, **kwargs):
    """Recompute artist territories when a location is added or changed."""
    artista_id = instance.artista_id
    transaction.on_commit(lambda: _resync(artista_id))


@receiver(post_delete, sender=ArtistaLocalitat)
def sync_territoris_on_localitat_delete(sender, instance, **kwargs):
    """Recompute artist territories when a location is removed."""
    artista_id = instance.artista_id
    transaction.on_commit(lambda: _resync(artista_id))
