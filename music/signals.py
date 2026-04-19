"""Signals for the music app — auto-sync territories from ArtistaLocalitat.

R12: the signal is wrapped in `transaction.on_commit()` so the territory
M2M is recomputed once, after the surrounding transaction commits, instead
of N times in the middle of an `atomic()` block (one per ArtistaLocalitat
row inserted/updated). The previous behaviour produced inconsistent
intermediate states visible to concurrent readers.

D5: a Canco must not list its own main Artista as a collaborator. The
`m2m_changed` guard below rejects `canco.artistes_col.add(...)` calls
that would create a self-collab. Migration 0034 cleaned up pre-existing
rows; this signal prevents the same class of bug from re-entering the
data via the Deezer contributor parser.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from music.models import ArtistaDeezer, ArtistaLocalitat, Canco


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


@receiver(m2m_changed, sender=Canco.artistes_col.through)
def prevent_self_collab(sender, instance, action, pk_set, reverse, **kwargs):
    """D5: reject `canco.artistes_col.add(main_artista)`.

    Only fires on the forward direction (Canco.artistes_col.add/set). The
    reverse direction (Artista.participacions.add) is rarely used; the
    check is symmetric anyway because we compare by ID.
    """
    if action not in {"pre_add", "pre_set"} or not pk_set:
        return
    if reverse:
        # `instance` is the Artista; pk_set is Canco IDs. Reject any Canco
        # whose main artista is `instance`.
        if Canco.objects.filter(pk__in=pk_set, artista=instance).exists():
            raise ValidationError(
                "D5: an artist cannot be listed as a collaborator on "
                "their own track."
            )
    else:
        # `instance` is the Canco; pk_set is Artista IDs.
        if instance.artista_id in pk_set:
            raise ValidationError(
                "D5: an artist cannot be listed as a collaborator on "
                "their own track."
            )


@receiver(post_save, sender=ArtistaDeezer)
def clear_deezer_no_trobat_on_ad_save(sender, instance, created, **kwargs):
    """Clear the stale `Artista.deezer_no_trobat` flag when a real Deezer
    link appears.

    The flag was originally a cache for "we searched Deezer and couldn't
    find this artist — don't re-query every run". But the artist can
    later be discovered via auto-descoberta, staff action, or feat.
    attribution, any of which creates an ArtistaDeezer row. Before this
    signal, the flag stayed True and the staff "sense Deezer" filter
    showed artists that clearly had a Deezer id — exactly the case of
    Àlex Blat surfaced on 2026-04-19.
    """
    if not created:
        return
    artista = instance.artista
    if artista.deezer_no_trobat:
        artista.deezer_no_trobat = False
        artista.save(update_fields=["deezer_no_trobat"])
