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

from music.constants import MAX_POSICIONS_TOP, TERRITORI_NOMS
from ranking.models import RankingProvisional, RankingSetmanal

# Territories the public API accepts — the five ranking-eligible plus
# the smaller ones that fall back to ALT (AND, CNO, FRA, ALG). Caller
# can pass any of these; the fallback logic below redirects empty ones.
API_TERRITORIS = tuple(TERRITORI_NOMS.keys())


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
            "nom": canco.nom if canco else getattr(entry, "canco_nom_snapshot", ""),
            "slug": canco.slug if canco else None,
            "isrc": canco.isrc if canco else None,
            "preview_url": canco.preview_url if canco else None,
            "deezer_id": canco.deezer_id if canco else None,
        },
        "artista": (
            {
                "id": artista.pk if artista else None,
                "nom": (
                    artista.nom
                    if artista
                    else getattr(entry, "artista_nom_snapshot", "")
                ),
                "slug": artista.slug if artista else None,
            }
            if artista or getattr(entry, "artista_nom_snapshot", "")
            else None
        ),
        "album": (
            {
                "id": album.pk if album else None,
                "slug": album.slug if album else None,
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
    if territori not in API_TERRITORIS:
        return Response(
            {"error": f"Invalid territori. Must be one of {list(API_TERRITORIS)}."},
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

    # Small territories (AND, CNO, FRA, ALG) fold their tracks into ALT
    # when they don't reach the 20-track threshold, so if the caller
    # asked for one of those and we have nothing stored, we redirect to
    # ALT for the same week and tell the client via `fallback_from`.
    FALLBACK_TERRITORIS = {"AND", "CNO", "FRA", "ALG", "CAR"}

    def _latest_week(t: str):
        return (
            RankingSetmanal.objects.filter(territori=t)
            .order_by("-setmana")
            .values_list("setmana", flat=True)
            .first()
        )

    fallback_from = None
    actual_territori = territori

    if setmana is None:
        setmana = _latest_week(territori)
        if setmana is None and territori in FALLBACK_TERRITORIS:
            setmana = _latest_week("ALT")
            if setmana is not None:
                fallback_from = territori
                actual_territori = "ALT"
        if setmana is None:
            # Fall back to provisional for the originally-requested territory.
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
                    "fallback_from": None,
                    "setmana": None,
                    "es_provisional": True,
                    "data_calcul": prov[0].data_calcul.isoformat() if prov else None,
                    "entries": [_serialize_entry(e, is_provisional=True) for e in prov],
                }
            )

    entries = list(
        RankingSetmanal.objects.select_related(
            "canco", "canco__artista", "canco__album"
        )
        .filter(territori=actual_territori, setmana=setmana)
        .order_by("posicio")[:MAX_POSICIONS_TOP]
    )

    # If the caller pinned a specific setmana and the small-territory
    # row came up empty, try ALT for the same week.
    if not entries and territori in FALLBACK_TERRITORIS and fallback_from is None:
        alt_entries = list(
            RankingSetmanal.objects.select_related(
                "canco", "canco__artista", "canco__album"
            )
            .filter(territori="ALT", setmana=setmana)
            .order_by("posicio")[:MAX_POSICIONS_TOP]
        )
        if alt_entries:
            fallback_from = territori
            actual_territori = "ALT"
            entries = alt_entries

    return Response(
        {
            "territori": actual_territori,
            "fallback_from": fallback_from,
            "setmana": setmana.isoformat() if setmana else None,
            "es_provisional": False,
            "data_calcul": None,
            "entries": [_serialize_entry(e, is_provisional=False) for e in entries],
        }
    )
