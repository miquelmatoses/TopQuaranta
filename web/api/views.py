from django.db.models import Count
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from music.models import Artista, ArtistaLocalitat, Municipi
from ranking.models import RankingSetmanal

# ── Location API — single source of truth ──
#
# These endpoints expose public, non-sensitive reference data (the list of
# Catalan territories / comarques / municipis). They are consumed both by the
# public proposal form (no auth) and by staff pages (artist edit, pending
# approval). There is no reason to require auth for these GET endpoints.
# Both web/api/urls.py and web/views/staff/urls.py route to these same
# functions so staff template {% url %} tags keep working without change.
#
# S9: all @api_view-decorated handlers inherit the DRF throttle classes
# configured at settings.REST_FRAMEWORK — 60/min anon, 300/min user.


@api_view(["GET"])
def api_territoris(request: Request) -> Response:
    """List territories that have municipis."""
    result = []
    seen: set[str] = set()
    for m in Municipi.objects.values("territori__codi", "territori__nom").distinct():
        codi = m["territori__codi"]
        if codi not in seen:
            result.append({"codi": codi, "nom": m["territori__nom"]})
            seen.add(codi)
    result.sort(key=lambda x: x["codi"])
    return Response(result)


@api_view(["GET"])
def api_comarques(request: Request) -> Response:
    """List comarques for a territory."""
    territori = request.GET.get("territori", "")
    if not territori:
        return Response([])
    comarques = list(
        Municipi.objects.filter(territori__codi=territori)
        .values_list("comarca", flat=True)
        .distinct()
        .order_by("comarca")
    )
    return Response(comarques)


@api_view(["GET"])
def api_municipis(request: Request) -> Response:
    """List municipis for a comarca."""
    comarca = request.GET.get("comarca", "")
    if not comarca:
        return Response([])
    municipis = list(
        Municipi.objects.filter(comarca=comarca)
        .values_list("nom", flat=True)
        .order_by("nom")
    )
    return Response(municipis)


@api_view(["GET"])
def api_municipi_lookup(request: Request) -> Response:
    """Find a municipi by name and comarca, return its PK."""
    nom = request.GET.get("nom", "").strip()
    comarca = request.GET.get("comarca", "").strip()
    if not nom or not comarca:
        return Response({"error": "Cal nom i comarca"}, status=400)
    try:
        m = Municipi.objects.get(nom=nom, comarca=comarca)
        return Response(
            {
                "pk": m.pk,
                "nom": m.nom,
                "comarca": m.comarca,
                "territori": m.territori_id,
            }
        )
    except Municipi.DoesNotExist:
        return Response({"error": "Municipi no trobat"}, status=404)


@api_view(["GET"])
def mapa_artistes(request: Request) -> Response:
    """Map data for three zoom levels: territories, comarques, municipis.

    Returns artist data grouped at each level for the latest ranking week.
    An artist with multiple locations appears in all corresponding municipis.
    """
    latest = (
        RankingSetmanal.objects.order_by("-setmana")
        .values_list("setmana", flat=True)
        .first()
    )

    # Artist ranking appearances for latest week
    artist_ids: dict[int, int] = {}
    if latest:
        for row in (
            RankingSetmanal.objects.filter(setmana=latest)
            .values("canco__artista_id")
            .annotate(aparicions=Count("id"))
            .order_by("-aparicions")
        ):
            artist_ids[row["canco__artista_id"]] = row["aparicions"]

    # Load all municipis from Municipi model
    all_municipis = list(
        Municipi.objects.select_related("territori").values(
            "nom", "comarca", "territori__nom"
        )
    )

    # Load artists with their locations via ArtistaLocalitat
    artista_by_localitat: dict[str, list[dict]] = {}
    artista_by_comarca: dict[str, dict] = {}

    if artist_ids:
        # Get all ArtistaLocalitat for ranked artists
        localitats = ArtistaLocalitat.objects.filter(
            artista__aprovat=True,
            artista_id__in=artist_ids.keys(),
            municipi__isnull=False,
        ).select_related("artista", "municipi", "municipi__territori")
        for al in localitats:
            artista = al.artista
            info = {
                "nom": artista.nom,
                "slug": artista.slug,
                "aparicions": artist_ids.get(artista.id, 0),
                "territori": al.municipi.territori_id,
            }

            # Group by localitat (municipi name) for municipis level
            loc = al.municipi.nom.lower()
            artista_by_localitat.setdefault(loc, []).append(info)

            # Group by comarca — keep top artist
            com = al.municipi.comarca.lower()
            if (
                com not in artista_by_comarca
                or info["aparicions"] > artista_by_comarca[com]["aparicions"]
            ):
                artista_by_comarca[com] = info

    # Build comarques data
    comarques: dict[str, dict] = {}
    for m in all_municipis:
        com = m["comarca"].lower()
        if com not in comarques:
            comarques[com] = {
                "nom": m["comarca"],
                "territori": m["territori__nom"],
                "artista": artista_by_comarca.get(com),
            }

    # Build municipis data
    municipis_data: dict[str, dict] = {}
    for m in all_municipis:
        nom_lower = m["nom"].lower()
        artistes = artista_by_localitat.get(nom_lower, [])
        municipis_data[nom_lower] = {
            "nom": m["nom"],
            "comarca": m["comarca"],
            "territori": m["territori__nom"],
            "n_artistes": len(artistes),
            "artistes": sorted(artistes, key=lambda a: -a["aparicions"])[:5],
        }

    return Response(
        {
            "comarques": comarques,
            "municipis": municipis_data,
        }
    )
