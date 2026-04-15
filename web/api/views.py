from django.db import connection
from django.db.models import Count
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from music.models import Artista
from ranking.models import RankingSetmanal


@api_view(["GET"])
def mapa_artistes(request: Request) -> Response:
    """Map data for three zoom levels: territories, comarques, municipis.

    Returns artist data grouped at each level for the latest ranking week.
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

    # Load all municipis from DB
    with connection.cursor() as c:
        c.execute('SELECT "Municipi", "Comarca", "Territori" FROM municipis')
        all_municipis = [
            {"nom": r[0], "comarca": r[1], "territori": r[2]} for r in c.fetchall()
        ]

    # Load artists with comarca/localitat
    artista_by_localitat: dict[str, list[dict]] = {}
    artista_by_comarca: dict[str, dict] = {}

    if artist_ids:
        for artista in Artista.objects.filter(
            aprovat=True, id__in=artist_ids.keys()
        ).prefetch_related("territoris"):
            terrs = list(artista.territoris.values_list("codi", flat=True))
            info = {
                "nom": artista.nom,
                "slug": artista.slug,
                "aparicions": artist_ids.get(artista.id, 0),
                "territori": terrs[0] if terrs else "",
            }

            # Group by localitat for municipis level
            if artista.localitat:
                loc = artista.localitat.lower()
                artista_by_localitat.setdefault(loc, []).append(info)

            # Group by comarca — keep top artist
            if artista.comarca:
                com = artista.comarca.lower()
                if com not in artista_by_comarca or info["aparicions"] > artista_by_comarca[com]["aparicions"]:
                    artista_by_comarca[com] = info

    # Build comarques data
    comarques: dict[str, dict] = {}
    for m in all_municipis:
        com = m["comarca"].lower()
        if com not in comarques:
            comarques[com] = {
                "nom": m["comarca"],
                "territori": m["territori"],
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
            "territori": m["territori"],
            "n_artistes": len(artistes),
            "artistes": sorted(artistes, key=lambda a: -a["aparicions"])[:5],
        }

    return Response({
        "comarques": comarques,
        "municipis": municipis_data,
    })
