"""Public song endpoint.

GET /api/v1/cancons/<pk>/  — song metadata + weekly chart history.
"""

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from music.models import Canco
from ranking.models import RankingProvisional, RankingSetmanal


@api_view(["GET"])
@permission_classes([AllowAny])
def canco_detail(request: Request, slug: str) -> Response:
    canco = get_object_or_404(
        Canco.objects.select_related("artista", "album").prefetch_related(
            "artistes_col"
        ),
        slug=slug,
    )

    # Weekly ranking history per territory. Shape designed to feed a
    # Recharts LineChart with `setmana` on the X axis and one line per
    # territori (posicio on Y, inverted — lower is better).
    rows = list(
        RankingSetmanal.objects.filter(canco=canco)
        .order_by("setmana", "territori")
        .values("setmana", "territori", "posicio")
    )
    # Group by week → one record per week with one key per territori.
    by_week: dict = {}
    territoris_vistos: set[str] = set()
    for r in rows:
        wk = r["setmana"].isoformat()
        by_week.setdefault(wk, {"setmana": wk})
        by_week[wk][r["territori"]] = r["posicio"]
        territoris_vistos.add(r["territori"])

    historial = [by_week[k] for k in sorted(by_week.keys())]

    provisional = list(
        RankingProvisional.objects.filter(canco=canco)
        .order_by("territori")
        .values("territori", "posicio", "data_calcul")
    )
    provisional_out = [
        {
            "territori": p["territori"],
            "posicio": p["posicio"],
            "data_calcul": p["data_calcul"].isoformat() if p["data_calcul"] else None,
        }
        for p in provisional
    ]

    return Response(
        {
            "pk": canco.pk,
            "slug": canco.slug,
            "nom": canco.nom,
            "isrc": canco.isrc or None,
            "durada_ms": canco.durada_ms,
            "preview_url": canco.preview_url or None,
            "deezer_id": canco.deezer_id,
            "data_llancament": (
                canco.data_llancament.isoformat() if canco.data_llancament else None
            ),
            "artista": (
                {"slug": canco.artista.slug, "nom": canco.artista.nom}
                if canco.artista
                else None
            ),
            "album": (
                {
                    "slug": canco.album.slug,
                    "nom": canco.album.nom,
                    "imatge_url": canco.album.imatge_url or None,
                }
                if canco.album
                else None
            ),
            "artistes_col": [
                {"slug": a.slug, "nom": a.nom} for a in canco.artistes_col.all()
            ],
            "ml_classe": canco.ml_classe or None,
            "whisper_lang": canco.whisper_lang or None,
            "whisper_p": canco.whisper_p,
            "territoris_historial": sorted(territoris_vistos),
            "historial": historial,
            "provisional": provisional_out,
        }
    )
