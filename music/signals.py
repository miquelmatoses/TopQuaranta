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


@receiver(post_delete, sender=ArtistaDeezer)
def unapprove_on_last_deezer_removed(sender, instance, **kwargs):
    """Invariant: `aprovat=True` ⇒ at least one external ID
    (Deezer OR MusicBrainz).

    When the last Deezer ID is removed, the Deezer pipeline can no
    longer ingest material for the artist — but if we have an MBID we
    can still rely on the MusicBrainz sync, so keep them aprovat.

    Only desaprova'l if the artist lost BOTH external anchors
    (Deezer + MBID).

    Motivation: Crim-style collisions. Two Catalan artists share a
    single Deezer ID (347962). Only one can own it per the DB unique
    constraint; the other stays Deezer-less but MusicBrainz-backed.
    """
    artista_id = instance.artista_id
    if not artista_id:
        return
    # If any other Deezer ID still references this artist, nothing to do.
    if ArtistaDeezer.objects.filter(artista_id=artista_id).exists():
        return
    from music.models import Artista

    # Still has an MBID → the MB pipeline is enough to keep them live.
    if (
        Artista.objects.filter(pk=artista_id)
        .exclude(musicbrainz_id="")
        .exclude(musicbrainz_id__isnull=True)
        .exists()
    ):
        return

    # No Deezer + no MBID → desaprova'l. The `update()` path skips
    # Artista.save() so we don't retrigger the territori sync.
    Artista.objects.filter(pk=artista_id, aprovat=True).update(
        aprovat=False,
        pendent_review=False,
    )
