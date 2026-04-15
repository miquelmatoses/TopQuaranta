import datetime

from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from music.models import Artista, Canco
from ranking.models import RankingProvisional, RankingSetmanal

TERRITORIS_VALIDS = ("CAT", "VAL", "BAL", "PPCC")

TERRITORI_NOMS = {
    "CAT": "Catalunya",
    "VAL": "País Valencià",
    "BAL": "Illes Balears",
    "PPCC": "Països Catalans",
}


def _setmana_actual() -> datetime.date:
    """Return Monday of the current ISO week."""
    today = datetime.date.today()
    return datetime.date.fromisocalendar(
        today.isocalendar().year, today.isocalendar().week, 1
    )


def _get_ranking(
    territori: str, setmana: datetime.date
) -> tuple[list, bool, datetime.date | None]:
    """Fetch ranking for a territory and week.

    Returns (ranking_qs, es_provisional, data_calcul).
    PPCC never falls back to RankingProvisional.
    """
    ranking = list(
        RankingSetmanal.objects.filter(territori=territori, setmana=setmana)
        .select_related("canco", "canco__artista", "canco__album")
        .order_by("posicio")[:40]
    )

    if ranking or territori == "PPCC":
        return ranking, False, None

    provisional = list(
        RankingProvisional.objects.filter(territori=territori)
        .select_related("canco", "canco__artista", "canco__album")
        .order_by("posicio")[:40]
    )
    data_calcul = None
    if provisional:
        data_calcul = provisional[0].data_calcul
    return provisional, True, data_calcul


def homepage(request: HttpRequest) -> HttpResponse:
    """Public homepage showing the current week's Top 40 for CAT territory."""
    setmana = _setmana_actual()
    ranking, es_provisional, data_calcul = _get_ranking("CAT", setmana)

    return render(request, "web/homepage.html", {
        "ranking": ranking,
        "es_provisional": es_provisional,
        "setmana": setmana,
        "data_calcul": data_calcul,
        "territori_actiu": "CAT",
    })


def ranking_territori(
    request: HttpRequest, territori: str, setmana_str: str | None = None
) -> HttpResponse:
    """Top 40 ranking for a specific territory, optionally for a specific week."""
    territori = territori.upper()
    if territori not in TERRITORIS_VALIDS:
        raise Http404

    if setmana_str:
        try:
            setmana = datetime.date.fromisoformat(setmana_str)
        except ValueError:
            raise Http404
        if setmana.weekday() != 0:  # Must be a Monday
            raise Http404
    else:
        setmana = _setmana_actual()

    ranking, es_provisional, data_calcul = _get_ranking(territori, setmana)
    nom_territori = TERRITORI_NOMS[territori]

    return render(request, "web/ranking.html", {
        "ranking": ranking,
        "es_provisional": es_provisional,
        "setmana": setmana,
        "data_calcul": data_calcul,
        "territori": territori,
        "territori_actiu": territori,
        "nom_territori": nom_territori,
    })


def directori_artistes(request: HttpRequest) -> HttpResponse:
    """Browsable directory of approved artists with territory filter and search."""
    qs = Artista.objects.filter(aprovat=True).prefetch_related("territoris")

    territori = request.GET.get("territori", "").upper()
    if territori in ("CAT", "VAL", "BAL"):
        qs = qs.filter(territoris__codi=territori)

    cerca = request.GET.get("q", "").strip()
    if cerca:
        qs = qs.filter(nom__icontains=cerca)

    qs = qs.distinct().order_by("nom")
    paginator = Paginator(qs, 40)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "web/artistes.html", {
        "page": page,
        "territori_filtre": territori,
        "cerca": cerca,
    })


def perfil_artista(request: HttpRequest, slug: str) -> HttpResponse:
    """Artist profile with ranking history and discography."""
    artista = get_object_or_404(Artista, slug=slug, aprovat=True)
    territoris = artista.get_territoris()

    # Last 10 weeks in RankingSetmanal (any territory)
    historial = (
        RankingSetmanal.objects.filter(canco__artista=artista)
        .select_related("canco")
        .order_by("-setmana", "territori", "posicio")[:50]
    )
    # Group by week
    setmanes: dict[datetime.date, list] = {}
    for entry in historial:
        setmanes.setdefault(entry.setmana, []).append(entry)
    historial_setmanes = sorted(setmanes.items(), reverse=True)[:10]

    # Discography: only verified tracks
    discografia = (
        artista.albums
        .filter(cancons__verificada=True)
        .prefetch_related("cancons")
        .distinct()
        .order_by("-data_llancament")
    )

    return render(request, "web/artista.html", {
        "artista": artista,
        "territoris": territoris,
        "historial_setmanes": historial_setmanes,
        "discografia": discografia,
    })


def mapa(request: HttpRequest) -> HttpResponse:
    """Three-level zoomable SVG map using D3.js."""
    import json

    from django.db import connection
    from django.db.models import Count

    latest = RankingSetmanal.objects.order_by("-setmana").values_list("setmana", flat=True).first()
    artist_ids: dict[int, int] = {}
    if latest:
        for r in (
            RankingSetmanal.objects.filter(setmana=latest)
            .values("canco__artista_id")
            .annotate(aparicions=Count("id"))
        ):
            artist_ids[r["canco__artista_id"]] = r["aparicions"]

    # Load all municipis
    with connection.cursor() as c:
        c.execute('SELECT "Municipi", "Comarca", "Territori" FROM municipis')
        all_municipis = [{"nom": r[0], "comarca": r[1], "territori": r[2]} for r in c.fetchall()]

    # Artist data by localitat and comarca
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
            if artista.localitat:
                artista_by_localitat.setdefault(artista.localitat.lower(), []).append(info)
            if artista.comarca:
                com = artista.comarca.lower()
                if com not in artista_by_comarca or info["aparicions"] > artista_by_comarca[com]["aparicions"]:
                    artista_by_comarca[com] = info

    comarques_data: dict[str, dict] = {}
    for m in all_municipis:
        com = m["comarca"].lower()
        if com not in comarques_data:
            comarques_data[com] = {
                "nom": m["comarca"],
                "territori": m["territori"],
                "artista": artista_by_comarca.get(com),
            }

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

    return render(request, "web/mapa.html", {
        "comarques_json": json.dumps(comarques_data, ensure_ascii=False),
        "municipis_json": json.dumps(municipis_data, ensure_ascii=False),
    })
