"""Public artist endpoints for the React SPA.

GET /api/v1/artistes/            — paginated directory with search + territory filter
GET /api/v1/artistes/<slug>/     — artist profile (info + territories + recent rankings + discography)
"""

import datetime

from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from music.models import Album, Artista, Canco
from ranking.models import RankingSetmanal


def _territoris_summary(artista) -> list[str]:
    """Territory codes this artist belongs to (M2M, auto-synced)."""
    return list(artista.territoris.values_list("codi", flat=True).order_by("codi"))


def _localitat_principal(artista) -> dict | None:
    loc = artista.localitats.select_related("municipi__territori").first()
    if loc is None:
        return None
    if loc.municipi:
        return {
            "nom": loc.municipi.nom,
            "comarca": loc.municipi.comarca,
            "territori": loc.municipi.territori_id,
        }
    if loc.localitat_manual:
        return {"nom": loc.localitat_manual, "comarca": "", "territori": "ALT"}
    return None


def _latest_cover(artista) -> str | None:
    """Artist card image — derived from the most recent album cover.

    Artista has no dedicated image field yet; populating one from
    Deezer is a backfill we'll do later. For now this is a cheap
    proxy that covers most active artists (any with ≥1 album).
    """
    return (
        Album.objects.filter(artista=artista)
        .exclude(imatge_url="")
        .order_by("-data_llancament")
        .values_list("imatge_url", flat=True)
        .first()
    )


def _artista_row(artista) -> dict:
    """Compact shape for directory listing."""
    return {
        "pk": artista.pk,
        "nom": artista.nom,
        "slug": artista.slug,
        "genere": artista.genere or "",
        "territoris": _territoris_summary(artista),
        "localitat": _localitat_principal(artista),
        "deezer_id": artista.deezer_id_principal,
        "imatge_url": _latest_cover(artista),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def artistes_list(request: Request) -> Response:
    """Paginated directory of approved artists.

    Query params (all optional, all compose via AND):
      q          — case-insensitive substring match on name
      territori  — any of PPCC/CAT/VAL/BAL/AND/CNO/FRA/ALG/CAR/ALT
      comarca    — exact comarca name (from /api/v1/localitzacio/comarques/)
      municipi   — exact municipi name
      amb_dones  — "1": percentatge_femeni in {100, 50+} (female-led / mixed)
      nou        — "1": has any album released in the last 365 days
      al_top     — "1": has at least one track ever in RankingSetmanal
      page       — 1-based page index (default 1)
      per_page   — items per page (default 40, capped at 100)
    """
    qs = Artista.objects.filter(aprovat=True).prefetch_related(
        "territoris", "localitats__municipi", "deezer_ids"
    )

    territori = (request.GET.get("territori") or "").upper()
    if territori:
        qs = qs.filter(territoris__codi=territori)

    comarca = (request.GET.get("comarca") or "").strip()
    if comarca:
        qs = qs.filter(localitats__municipi__comarca=comarca)

    municipi = (request.GET.get("municipi") or "").strip()
    if municipi:
        qs = qs.filter(localitats__municipi__nom=municipi)

    if (request.GET.get("amb_dones") or "") == "1":
        # Use percentatge_femeni >= 50% (values "100" or "50+").
        qs = qs.filter(percentatge_femeni__in=["100", "50+"])

    if (request.GET.get("nou") or "") == "1":
        # Any album released within the past 365 days.
        cutoff = datetime.date.today() - datetime.timedelta(days=365)
        qs = qs.filter(
            Exists(
                Album.objects.filter(
                    artista=OuterRef("pk"),
                    data_llancament__gte=cutoff,
                )
            )
        )

    if (request.GET.get("al_top") or "") == "1":
        # Nested OuterRef via Canco is buggy here; a direct pk__in over
        # the (~100 artists) set is cheaper and clearer.
        top_artist_ids = RankingSetmanal.objects.values_list(
            "canco__artista_id", flat=True
        ).distinct()
        qs = qs.filter(pk__in=top_artist_ids)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(nom__icontains=q)

    qs = qs.distinct().order_by("nom")

    try:
        per_page = min(int(request.GET.get("per_page") or 40), 100)
    except ValueError:
        per_page = 40

    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page") or 1)

    return Response(
        {
            "results": [_artista_row(a) for a in page.object_list],
            "page": page.number,
            "num_pages": paginator.num_pages,
            "total": paginator.count,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def artista_detail(request: Request, slug: str) -> Response:
    """Full artist profile.

    Includes: base info, territories, locations, social links, last
    weeks in the ranking, verified discography. Unapproved artists
    still resolve but with a minimal shape (flagged `aprovat=false`)
    so the client can render the "under review" state.
    """
    artista = get_object_or_404(
        Artista.objects.prefetch_related(
            "territoris", "localitats__municipi", "deezer_ids", "albums"
        ),
        slug=slug,
    )

    base = {
        "pk": artista.pk,
        "nom": artista.nom,
        "slug": artista.slug,
        "aprovat": artista.aprovat,
        "genere": artista.genere or "",
        "percentatge_femeni": artista.percentatge_femeni or None,
        "territoris": _territoris_summary(artista),
        "localitats": [
            {
                "municipi": (
                    {
                        "nom": loc.municipi.nom,
                        "comarca": loc.municipi.comarca,
                        "territori": loc.municipi.territori_id,
                    }
                    if loc.municipi
                    else None
                ),
                "manual": loc.localitat_manual or None,
            }
            for loc in artista.localitats.select_related("municipi").all()
        ],
        "deezer_ids": list(artista.deezer_ids.values_list("deezer_id", flat=True)),
        "deezer_nb_fan": artista.deezer_nb_fan,
        "deezer_nb_album": artista.deezer_nb_album,
        "social": {
            field: getattr(artista, field) or None
            for field, _ in Artista.SOCIAL_LINK_FIELDS
            if getattr(artista, field)
        },
    }

    if not artista.aprovat:
        return Response({**base, "historial": [], "discografia": []})

    # Last 10 weeks across any territory.
    historial = list(
        RankingSetmanal.objects.filter(canco__artista=artista)
        .select_related("canco")
        .order_by("-setmana", "territori", "posicio")[:50]
    )
    setmanes: dict[datetime.date, list] = {}
    for e in historial:
        setmanes.setdefault(e.setmana, []).append(
            {
                "territori": e.territori,
                "posicio": e.posicio,
                "canco_nom": e.canco.nom if e.canco else e.canco_nom_snapshot,
                "canco_id": e.canco_id,
            }
        )
    historial_out = [
        {"setmana": s.isoformat(), "entries": v}
        for s, v in sorted(setmanes.items(), reverse=True)[:10]
    ]

    discografia = list(
        artista.albums.filter(cancons__verificada=True)
        .prefetch_related("cancons")
        .distinct()
        .order_by("-data_llancament")
    )
    disco_out = [
        {
            "slug": a.slug,
            "nom": a.nom,
            "data_llancament": (
                a.data_llancament.isoformat() if a.data_llancament else None
            ),
            "imatge_url": getattr(a, "imatge_url", None) or None,
            "n_cancons": a.cancons.filter(verificada=True).count(),
        }
        for a in discografia
    ]

    return Response({**base, "historial": historial_out, "discografia": disco_out})
