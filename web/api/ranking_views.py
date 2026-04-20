"""Ranking endpoints for the React SPA.

GET /api/v1/ranking/?territori=CAT&setmana=2026-04-13
    Weekly ranking (top 40) for a territory. `setmana` optional — if
    absent, returns the most recent stored week for that territory.
    Falls back to RankingProvisional when no weekly row exists yet.
"""

import datetime

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from music.constants import MAX_POSICIONS_TOP, TERRITORIS_VALIDS
from ranking.models import RankingProvisional, RankingSetmanal


def _serialize_entry(entry, is_provisional: bool) -> dict:
    """Shape used by the React RankingPage — one row per track."""
    canco = entry.canco
    artista = canco.artista if canco else None
    album = canco.album if canco else None
    return {
        "posicio": entry.posicio,
        "score": float(
            entry.score_setmanal if not is_provisional else entry.score_setmanal
        ),
        "canco": {
            "id": canco.pk if canco else None,
            "nom": canco.nom if canco else entry.canco_nom_snapshot,
            "slug": None,  # Canco has no slug yet
            "isrc": canco.isrc if canco else None,
            "preview_url": canco.preview_url if canco else None,
            "deezer_id": canco.deezer_id if canco else None,
        },
        "artista": (
            {
                "id": artista.pk if artista else None,
                "nom": artista.nom if artista else entry.artista_nom_snapshot,
                "slug": artista.slug if artista else None,
            }
            if artista or entry.artista_nom_snapshot
            else None
        ),
        "album": (
            {
                "id": album.pk if album else None,
                "nom": album.nom if album else None,
                "imatge_url": (
                    (getattr(album, "imatge_url", None) or None) if album else None
                ),
            }
            if album
            else None
        ),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def ranking(request: Request) -> Response:
    """Top 40 for a territory + week. Defaults to latest week.

    Query params:
      - territori: one of TERRITORIS_VALIDS (required)
      - setmana:   YYYY-MM-DD, Monday of the ISO week (optional)
    """
    territori = (request.GET.get("territori") or "").strip().upper()
    if territori not in TERRITORIS_VALIDS:
        return Response(
            {"error": f"Invalid territori. Must be one of {list(TERRITORIS_VALIDS)}."},
            status=400,
        )

    setmana_raw = (request.GET.get("setmana") or "").strip()
    setmana = None
    if setmana_raw:
        try:
            setmana = datetime.date.fromisoformat(setmana_raw)
        except ValueError:
            return Response(
                {"error": "Invalid setmana format. Expected YYYY-MM-DD."}, status=400
            )

    qs = RankingSetmanal.objects.select_related(
        "canco", "canco__artista", "canco__album"
    ).filter(territori=territori)

    if setmana is not None:
        qs = qs.filter(setmana=setmana)
    else:
        latest_week = (
            RankingSetmanal.objects.filter(territori=territori)
            .order_by("-setmana")
            .values_list("setmana", flat=True)
            .first()
        )
        if latest_week is None:
            # Fall back to provisional if the territory has no official week yet.
            prov = list(
                RankingProvisional.objects.select_related(
                    "canco", "canco__artista", "canco__album"
                )
                .filter(territori=territori)
                .order_by("posicio")[:MAX_POSICIONS_TOP]
            )
            return Response(
                {
                    "territori": territori,
                    "setmana": None,
                    "es_provisional": True,
                    "data_calcul": prov[0].data_calcul.isoformat() if prov else None,
                    "entries": [_serialize_entry(e, is_provisional=True) for e in prov],
                }
            )
        qs = qs.filter(setmana=latest_week)
        setmana = latest_week

    entries = list(qs.order_by("posicio")[:MAX_POSICIONS_TOP])
    return Response(
        {
            "territori": territori,
            "setmana": setmana.isoformat() if setmana else None,
            "es_provisional": False,
            "data_calcul": None,
            "entries": [_serialize_entry(e, is_provisional=False) for e in entries],
        }
    )
