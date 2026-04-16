"""
Business logic for track/artist/album approval and rejection.

All admin actions delegate to these functions so the logic lives in one place.
Each function operates inside the caller's transaction — the caller wraps
with transaction.atomic() as needed.
"""

import logging

from django.db import transaction

from .models import Album, Artista, Canco, HistorialRevisio
from .verificacio import crear_historial

logger = logging.getLogger(__name__)


def rebutjar_canco(canco: Canco, motiu: str) -> None:
    """
    Reject a single track: record historial, set verificada=False and activa=False.
    The track stays in DB for audit but won't appear in pending lists or rankings.
    """
    crear_historial(canco, "rebutjada", motiu)
    canco.verificada = False
    canco.activa = False
    canco.save(update_fields=["verificada", "activa"])


def aprovar_canco(canco: Canco) -> None:
    """Approve a single track: record historial, set verificada=True."""
    crear_historial(canco, "aprovada", "ok")
    canco.verificada = True
    canco.save(update_fields=["verificada"])


def rebutjar_album(album: Album, motiu: str) -> int:
    """
    Reject all unverified tracks in an album, mark album as descartat.
    Returns number of tracks deleted.
    """
    cancons = Canco.objects.filter(album=album, verificada=False)
    for canco in cancons.select_related("artista", "album"):
        crear_historial(canco, "rebutjada", motiu)
    deleted = cancons.count()
    cancons.delete()
    album.descartat = True
    album.save(update_fields=["descartat"])
    return deleted


def rebutjar_artista(artista: Artista, motiu: str) -> int:
    """
    Reject an artist: delete all unverified tracks, clear deezer_id,
    mark deezer_no_trobat=True, mark all albums as descartat.
    Returns number of tracks deleted.
    """
    cancons = Canco.objects.filter(artista=artista, verificada=False)
    for canco in cancons.select_related("album"):
        crear_historial(canco, "rebutjada", motiu)
    deleted = cancons.count()
    cancons.delete()

    artista.deezer_ids.all().delete()
    artista.deezer_id = None
    artista.deezer_no_trobat = True
    artista.save(update_fields=["deezer_id", "deezer_no_trobat"])
    Album.objects.filter(artista=artista).update(descartat=True)

    return deleted
