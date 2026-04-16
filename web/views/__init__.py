import datetime

from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseNotFound, HttpResponseServerError
from django.shortcuts import get_object_or_404, redirect, render
from django.template import loader

from music.constants import TERRITORI_NOMS, TERRITORIS_VALIDS  # noqa: F401 (re-exported)
from music.models import Album, Artista, Canco, Municipi
from ranking.models import RankingProvisional, RankingSetmanal

TERRITORI_DESCRIPCIONS = {
    "PPCC": "El rànquing agregat de tots els territoris de parla catalana",
    "CAT": "El rànquing de la música en català a Catalunya",
    "VAL": "El rànquing de la música en català al País Valencià",
    "BAL": "El rànquing de la música en català a les Illes Balears",
    "ALT": "El rànquing d'artistes d'Andorra, la Catalunya Nord, la Franja i l'Alguer",
    "AND": "Andorra",
    "CNO": "Catalunya Nord",
    "FRA": "Franja de Ponent",
    "ALG": "l'Alguer",
}

# Territories that redirect to ALT when clicked
TERRITORIS_REDIRECT_ALT = {"AND", "CNO", "FRA", "ALG"}

# Territories shown in selector and ranking sub-nav (same order)
# PPCC is always separate/featured; these are the rest, alphabetical.
TERRITORIS_SELECTOR = [
    {"codi": "ALG", "nom": "l'Alguer"},
    {"codi": "AND", "nom": "Andorra"},
    {"codi": "BAL", "nom": "Illes Balears"},
    {"codi": "CAT", "nom": "Catalunya"},
    {"codi": "CNO", "nom": "Catalunya Nord"},
    {"codi": "FRA", "nom": "Franja de Ponent"},
    {"codi": "VAL", "nom": "País Valencià"},
]


def _setmana_actual() -> datetime.date:
    """Return Monday of the current ISO week."""
    today = datetime.date.today()
    return datetime.date.fromisocalendar(
        today.isocalendar().year, today.isocalendar().week, 1
    )


def _ranking_base_qs():
    """Common select_related and prefetch for ranking queries."""
    return (
        RankingSetmanal.objects
        .select_related("canco", "canco__artista", "canco__album")
        .prefetch_related("canco__artistes_col")
    )


def _provisional_base_qs():
    """Common select_related and prefetch for provisional ranking queries."""
    return (
        RankingProvisional.objects
        .select_related("canco", "canco__artista", "canco__album")
        .prefetch_related("canco__artistes_col")
    )


def _get_ranking(
    territori: str, setmana: datetime.date
) -> tuple[list, bool, datetime.date | None]:
    """Fetch ranking for a territory and week.

    Returns (ranking_list, es_provisional, data_calcul).
    PPCC is computed by the full algorithm (like any other territory)
    via calcular_ranking_territori('PPCC') in the pipeline.
    The web view simply reads the stored results.
    """
    ranking = list(
        _ranking_base_qs()
        .filter(territori=territori, setmana=setmana)
        .order_by("posicio")[:40]
    )

    if ranking:
        return ranking, False, None

    # Fallback to provisional (all territories including PPCC)
    provisional = list(
        _provisional_base_qs()
        .filter(territori=territori)
        .order_by("posicio")[:40]
    )
    data_calcul = None
    if provisional:
        data_calcul = provisional[0].data_calcul
    return provisional, True, data_calcul


def homepage(request: HttpRequest) -> HttpResponse:
    """Public homepage showing the current week's Top 40 for PPCC territory."""
    setmana = _setmana_actual()
    ranking, es_provisional, data_calcul = _get_ranking("PPCC", setmana)

    return render(request, "web/homepage.html", {
        "ranking": ranking,
        "es_provisional": es_provisional,
        "setmana": setmana,
        "data_calcul": data_calcul,
        "territori_actiu": "PPCC",
    })


def ranking_page(request: HttpRequest) -> HttpResponse:
    """Single ranking page with territory selector.

    Without ?t= parameter: shows territory selector.
    With ?t=cat (etc.): shows the ranking for that territory.
    Optional ?setmana=YYYY-MM-DD for historical weeks.
    """
    territori = request.GET.get("t", "").upper()

    if not territori:
        # Territory selector page — PPCC featured on top, rest in flat grid
        ppcc = {"codi": "PPCC", "nom": TERRITORI_NOMS["PPCC"], "desc": TERRITORI_DESCRIPCIONS["PPCC"]}

        return render(request, "web/ranking_selector.html", {
            "ppcc": ppcc,
            "territoris": TERRITORIS_SELECTOR,
        })

    # AND/CNO/FRA/ALG redirect to ALT ranking
    if territori in TERRITORIS_REDIRECT_ALT:
        return redirect(f"/ranking/?t=alt", permanent=False)

    if territori not in TERRITORIS_VALIDS:
        raise Http404

    setmana_str = request.GET.get("setmana")
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
        "territoris_nav": TERRITORIS_SELECTOR,
    })


def ranking_territori_redirect(
    request: HttpRequest, territori: str, setmana_str: str | None = None
) -> HttpResponse:
    """Redirect old /ranking/<territori>/ URLs to /ranking/?t=<territori>."""
    url = f"/ranking/?t={territori}"
    if setmana_str:
        url += f"&setmana={setmana_str}"
    return redirect(url, permanent=True)


def directori_artistes(request: HttpRequest) -> HttpResponse:
    """Browsable directory of approved artists with territory filter and search."""
    qs = Artista.objects.filter(aprovat=True).prefetch_related("territoris", "localitats__municipi")

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
    """Artist profile with ranking history and discography.

    Non-approved artists show a minimal page with context-appropriate
    calls to action (register, propose info, or staff edit link).
    """
    artista = get_object_or_404(
        Artista.objects.prefetch_related("localitats__municipi"), slug=slug
    )

    if not artista.aprovat:
        return render(request, "web/artista_no_verificat.html", {
            "artista": artista,
        })

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


def perfil_album(request: HttpRequest, slug: str) -> HttpResponse:
    """Album page with cover, metadata, and track listing with ranking info."""
    album = get_object_or_404(
        Album.objects.select_related("artista"),
        slug=slug,
    )

    # Tracks on this album — verified ones first, then all
    cancons = (
        album.cancons
        .select_related("artista")
        .prefetch_related("artistes_col")
        .order_by("id")
    )

    # Which tracks from this album have appeared in rankings?
    canco_ids = [c.id for c in cancons]
    ranking_cancons = set(
        RankingSetmanal.objects.filter(canco_id__in=canco_ids)
        .values_list("canco_id", flat=True)
        .distinct()
    )
    provisional_cancons = set(
        RankingProvisional.objects.filter(canco_id__in=canco_ids)
        .values_list("canco_id", flat=True)
        .distinct()
    )
    cancons_al_ranking = ranking_cancons | provisional_cancons

    return render(request, "web/album.html", {
        "album": album,
        "cancons": cancons,
        "cancons_al_ranking": cancons_al_ranking,
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

    # Load all municipis from the new music_municipi table
    all_municipis = list(
        Municipi.objects.values("nom", "comarca", "territori_id").iterator()
    )
    # Normalize key name to match the rest of this view
    all_municipis = [
        {"nom": m["nom"], "comarca": m["comarca"], "territori": m["territori_id"]}
        for m in all_municipis
    ]

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


# ── Error handlers (S13) — custom-styled 404 / 500 / 403 pages ──
#
# Registered in topquaranta/urls.py via `handler404 = ...` etc. Django only
# uses these when DEBUG=False; in local dev you still get the technical
# 500 page.

def handler_404(request: HttpRequest, exception=None) -> HttpResponse:
    template = loader.get_template("web/404.html")
    return HttpResponseNotFound(template.render({"request": request}, request))


def handler_500(request: HttpRequest) -> HttpResponse:
    template = loader.get_template("web/500.html")
    return HttpResponseServerError(template.render({"request": request}, request))


def handler_403(request: HttpRequest, exception=None) -> HttpResponse:
    template = loader.get_template("web/403.html")
    return HttpResponseForbidden(template.render({"request": request}, request))
