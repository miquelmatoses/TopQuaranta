"""Public album endpoint for the React SPA.

GET /api/v1/albums/<slug>/  — album metadata + track listing + which tracks appeared in a ranking
"""

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from music.models import Album
from ranking.models import RankingProvisional, RankingSetmanal


@api_view(["GET"])
@permission_classes([AllowAny])
def album_detail(request: Request, slug: str) -> Response:
    album = get_object_or_404(
        Album.objects.select_related("artista"),
        slug=slug,
    )

    cancons = list(
        album.cancons.select_related("artista")
        .prefetch_related("artistes_col")
        .order_by("id")
    )
    canco_ids = [c.pk for c in cancons]

    ranked_ids = set(
        RankingSetmanal.objects.filter(canco_id__in=canco_ids)
        .values_list("canco_id", flat=True)
        .distinct()
    ) | set(
        RankingProvisional.objects.filter(canco_id__in=canco_ids)
        .values_list("canco_id", flat=True)
        .distinct()
    )

    return Response(
        {
            "slug": album.slug,
            "nom": album.nom,
            "data_llancament": (
                album.data_llancament.isoformat() if album.data_llancament else None
            ),
            "imatge_url": getattr(album, "imatge_url", None) or None,
            "deezer_id": album.deezer_id,
            "artista": (
                {
                    "nom": album.artista.nom,
                    "slug": album.artista.slug,
                }
                if album.artista
                else None
            ),
            "cancons": [
                {
                    "pk": c.pk,
                    "slug": c.slug,
                    "nom": c.nom,
                    "isrc": c.isrc or None,
                    "durada_ms": c.durada_ms,
                    "preview_url": c.preview_url or None,
                    "deezer_id": c.deezer_id,
                    "al_top": c.pk in ranked_ids,
                    "artistes_col": [
                        {"nom": a.nom, "slug": a.slug} for a in c.artistes_col.all()
                    ],
                }
                for c in cancons
            ],
        }
    )
