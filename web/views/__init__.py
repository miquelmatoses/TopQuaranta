import datetime
import hashlib
from functools import wraps

from django.core.cache import caches
from django.core.paginator import Paginator
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseServerError,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template import loader
from django.views.decorators.http import etag, last_modified

from music.constants import TERRITORI_NOMS  # noqa: F401 (re-exported)
from music.constants import TERRITORIS_VALIDS
from music.models import Album, Artista, Canco, Municipi, StaffAuditLog
from ranking.models import ConfiguracioGlobal, RankingProvisional, RankingSetmanal

# ── Φ4 · Transparència algorítmica ───────────────────────────────────────
# Human-readable descriptions of every coefficient in ConfiguracioGlobal.
# Shown publicly on /com-funciona/. The tone matches the site's editorial
# register: explains WHAT each number does in Catalan prose, not formulas.
# Keep in sync with ranking/models.py ConfiguracioGlobal fields.

COEFICIENTS_DESCRIPCIO = {
    "penalitzacio_descens": {
        "label": "Penalització per caiguda",
        "blurb": "Quan una cançó perd posicions respecte de la setmana passada, "
        "aquest valor decideix com de dur és el cop. Més alt = més "
        "càstig quan una cançó s'enfonsa a la llista.",
    },
    "exponent_penalitzacio_antiguitat": {
        "label": "Exponent d'antiguitat",
        "blurb": "Controla com de ràpidament perden força les cançons antigues. "
        "Els singles de fa 11 mesos desapareixen del top molt més "
        "amunt d'aquest exponent que amb un valor baix — el top és "
        "per a música viva, no per a canons.",
    },
    "max_factor_a": {
        "label": "Factor A màxim (fase de posicionament)",
        "blurb": "El primer multiplicador que s'aplica al signal brut. "
        "Posa un sostre a la primera ronda del càlcul perquè les "
        "cançons amb xifres extremes no arrosseguin tot el top.",
    },
    "max_factor_b": {
        "label": "Factor B màxim (fase de monopolis)",
        "blurb": "Sostre del segon multiplicador. Intervé quan s'aplica la "
        "penalització per monopoli — si un àlbum o un artista es "
        "cruspeixen massa cançons del top.",
    },
    "max_factor_c": {
        "label": "Factor C màxim (fase de novetats)",
        "blurb": "Sostre del tercer multiplicador. Protegeix les cançons noves "
        "que encara no han acumulat història perquè no quedin "
        "infravalorades pel càlcul.",
    },
    "max_factor_final": {
        "label": "Factor final màxim",
        "blurb": "El sostre global de la fórmula. Evita que cap cançó pugui "
        "dominar els rànquings amb un score desmesurat.",
    },
    "penalitzacio_album_per_canco": {
        "label": "Penalització per àlbum",
        "blurb": "Si un mateix àlbum té tres, quatre o més cançons al top, "
        "aquest valor redueix el score de cada una addicional. "
        "La idea: un top 40 on només sonen dos àlbums no és un top.",
    },
    "penalitzacio_artista_per_canco": {
        "label": "Penalització per artista",
        "blurb": "Mateixa lògica que l'anterior, però aplicada a l'artista "
        "en comptes de l'àlbum. Si un artista acumula massa cançons "
        "al top, cada una de més pateix una petita rebaixa.",
    },
    "coeficient_penalitzacio_top": {
        "label": "Penalització per alta posició",
        "blurb": "Les cançons que portin moltes setmanes al top 3 o top 5 "
        "reben una penalització creixent perquè no es perpetuïn "
        "indefinidament al capdamunt. Els hits no són eterns.",
    },
    "penalitzacio_setmana_0": {
        "label": "Penalització setmana 0 (acabada de sortir)",
        "blurb": "Una cançó que ha sortit aquesta mateixa setmana encara no "
        "té un signal representatiu de Last.fm. Aquest valor corre "
        "el benefici del dubte: alt = costa molt entrar al top la "
        "setmana de l'estrena.",
    },
    "penalitzacio_setmana_1": {
        "label": "Penalització setmana 1",
        "blurb": "Igual que l'anterior però per cançons de la segona setmana. "
        "Normalment més baix que setmana 0.",
    },
    "penalitzacio_setmana_2": {
        "label": "Penalització setmana 2",
        "blurb": "A partir de la tercera setmana habitualment ja no cal "
        "ajustar res; aquest valor pot ser zero si l'entrada ja "
        "té prou dades.",
    },
    "suavitat": {
        "label": "Factor de suavitat",
        "blurb": "Quan més alt, els canvis de posició entre setmana i setmana "
        "són més lents — un top més estable. Més baix = el top es "
        "mou setmana a setmana amb més agressivitat.",
    },
    "min_cancons_ranking_propi": {
        "label": "Llindar per a ranquing propi",
        "blurb": "Un territori (diguem-ne l'Alguer o la Franja) només rep un "
        "top 40 propi si hi ha almenys aquesta quantitat de cançons "
        "elegibles. Per sota, els artistes d'aquell territori "
        "s'integren al top 'Altres territoris'.",
    },
    "dia_setmana_ranking": {
        "label": "Dia de la setmana del tancament",
        "blurb": "Quin dia de la setmana es congela el top oficial. "
        "Codi intern: 0 = dilluns, 6 = diumenge.",
    },
}


def _coeficients_context() -> list[dict]:
    """Build the list of coefficients with human labels for /com-funciona/.

    Reads ConfiguracioGlobal.load() live so if staff tweaks a value the
    page updates immediately. Preserves the order of COEFICIENTS_DESCRIPCIO
    for a consistent editorial flow.
    """
    cfg = ConfiguracioGlobal.load()
    rows = []
    for field_name, meta in COEFICIENTS_DESCRIPCIO.items():
        rows.append(
            {
                "field": field_name,
                "label": meta["label"],
                "blurb": meta["blurb"],
                "value": getattr(cfg, field_name),
            }
        )
    return rows


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
    return RankingSetmanal.objects.select_related(
        "canco", "canco__artista", "canco__album"
    ).prefetch_related("canco__artistes_col")


def _provisional_base_qs():
    """Common select_related and prefetch for provisional ranking queries."""
    return RankingProvisional.objects.select_related(
        "canco", "canco__artista", "canco__album"
    ).prefetch_related("canco__artistes_col")


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
        _provisional_base_qs().filter(territori=territori).order_by("posicio")[:40]
    )
    data_calcul = None
    if provisional:
        data_calcul = provisional[0].data_calcul
    return provisional, True, data_calcul


# ── P1 · Server-side page cache for anonymous hits ──────────────────────
# Logged-in users see a personalised header ("Sortir" + account link) so
# their responses can NOT share a cache with anon users. Rather than fight
# Django's @cache_page to handle both, we do the simplest thing: cache
# ONLY for anonymous requests. The site's traffic mix is dominated by
# anonymous visitors reading the public ranking, so this covers the
# common case while keeping the logged-in flow untouched.
#
# Keys combine (path, query-string, hashed User-Agent-agnostic data). TTL
# 600s (10 min) — shorter than the daily ranking refresh cadence so a new
# provisional ranking appears within 10 min of being computed, without
# having to plumb cache invalidation.
#
# This complements P8's @last_modified / @etag: those still run inside
# the view, and on a cache MISS the stored response carries the correct
# Last-Modified / ETag so revalidations on the cached copy also 304.

PAGE_CACHE_TTL_SECONDS = 600


def cache_page_for_anon(ttl: int):
    """Cache the view's response in `pagecache` — but only for anon users.

    Preserves the 304 Not Modified flow from P8's @last_modified / @etag:
    on a cache HIT we check the client's If-None-Match / If-Modified-
    Since against the cached response's ETag / Last-Modified and return
    304 if they match, before copying the body over the wire.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            cache = caches["pagecache"]
            key_raw = (
                f"{view_func.__module__}.{view_func.__name__}:"
                f"{request.path}?{request.META.get('QUERY_STRING', '')}"
            )
            key = "pagecache:" + hashlib.sha1(key_raw.encode()).hexdigest()
            cached = cache.get(key)
            if cached is not None:
                # Re-apply conditional GET semantics on cache hit so the
                # 304 shortcut still fires.
                inm = request.META.get("HTTP_IF_NONE_MATCH")
                cached_etag = cached.get("ETag")
                if inm and cached_etag and inm.strip() == cached_etag:
                    return HttpResponse(status=304)
                # (If-Modified-Since is handled with weaker guarantees; the
                # ETag path above already covers the common case.)
                return cached
            response = view_func(request, *args, **kwargs)
            # Only cache 200s so we don't poison the cache with a transient
            # 5xx or a conditional 304 (which has no body).
            if response.status_code == 200:
                cache.set(key, response, ttl)
            return response

        return wrapped

    return decorator


# ── P8 · HTTP conditional caching for public ranking pages ──────────────
# Last-Modified + ETag so browsers (and intermediate caches) can revalidate
# cheaply: on a repeat visit the client sends If-Modified-Since / If-None-
# Match, and if the underlying ranking hasn't changed we short-circuit to
# a 304 Not Modified response — saving the template render, the prefetch,
# and the bytes on the wire. No Cache-Control: public because the header
# differs per auth state; the ETag encodes `is_authenticated` to keep
# logged-in and anonymous clients from sharing cached responses by accident.


def _ranking_last_modified_dt(
    territori: str, setmana: datetime.date
) -> datetime.datetime | None:
    """Most recent timestamp at which the ranking for (territori, setmana) changed."""
    official = (
        RankingSetmanal.objects.filter(territori=territori, setmana=setmana)
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    if official:
        return official
    provis_date = (
        RankingProvisional.objects.filter(territori=territori)
        .order_by("-data_calcul")
        .values_list("data_calcul", flat=True)
        .first()
    )
    if provis_date:
        # DateField → midnight UTC for Last-Modified.
        return datetime.datetime.combine(
            provis_date, datetime.time(0, 0), tzinfo=datetime.timezone.utc
        )
    return None


def _etag_for(
    request: HttpRequest, territori: str | None, setmana: datetime.date | None
) -> str | None:
    """Weak ETag combining ranking identity + auth state.

    Auth state is included because the rendered page differs in the header
    ("Entrar" vs "Sortir"). Without this, a logged-in user could see the
    anonymous-cached version after switching accounts.
    """
    if not territori or not setmana:
        return None
    lm = _ranking_last_modified_dt(territori, setmana)
    if lm is None:
        return None
    auth = "1" if request.user.is_authenticated else "0"
    return f'W/"{territori}-{setmana.isoformat()}-{int(lm.timestamp())}-{auth}"'


def _homepage_last_modified(request: HttpRequest) -> datetime.datetime | None:
    return _ranking_last_modified_dt("PPCC", _setmana_actual())


def _homepage_etag(request: HttpRequest) -> str | None:
    return _etag_for(request, "PPCC", _setmana_actual())


def _ranking_page_territori_setmana(
    request: HttpRequest,
) -> tuple[str | None, datetime.date | None]:
    """Parse ?t= and ?setmana= from the query string, or return (None, None).

    Returning None from the conditional-view helpers tells Django to skip
    the header entirely and fall through to the view (which renders the
    territory selector / 404 path).
    """
    territori = request.GET.get("t", "").upper()
    if not territori or territori not in TERRITORIS_VALIDS:
        return None, None
    setmana_str = request.GET.get("setmana")
    if setmana_str:
        try:
            setmana = datetime.date.fromisoformat(setmana_str)
        except ValueError:
            return None, None
        if setmana.weekday() != 0:
            return None, None
    else:
        setmana = _setmana_actual()
    return territori, setmana


def _ranking_page_last_modified(request: HttpRequest) -> datetime.datetime | None:
    territori, setmana = _ranking_page_territori_setmana(request)
    if not territori or not setmana:
        return None
    return _ranking_last_modified_dt(territori, setmana)


def _ranking_page_etag(request: HttpRequest) -> str | None:
    territori, setmana = _ranking_page_territori_setmana(request)
    return _etag_for(request, territori, setmana)


@cache_page_for_anon(PAGE_CACHE_TTL_SECONDS)
@last_modified(_homepage_last_modified)
@etag(_homepage_etag)
def homepage(request: HttpRequest) -> HttpResponse:
    """Public homepage showing the current week's Top 40 for PPCC territory."""
    setmana = _setmana_actual()
    ranking, es_provisional, data_calcul = _get_ranking("PPCC", setmana)
    darrera_actualitzacio = _ranking_last_modified_dt("PPCC", setmana)

    return render(
        request,
        "web/homepage.html",
        {
            "ranking": ranking,
            "es_provisional": es_provisional,
            "setmana": setmana,
            "data_calcul": data_calcul,
            "darrera_actualitzacio": darrera_actualitzacio,
            "territori_actiu": "PPCC",
        },
    )


@cache_page_for_anon(PAGE_CACHE_TTL_SECONDS)
@last_modified(_ranking_page_last_modified)
@etag(_ranking_page_etag)
def ranking_page(request: HttpRequest) -> HttpResponse:
    """Single ranking page with territory selector.

    Without ?t= parameter: shows territory selector.
    With ?t=cat (etc.): shows the ranking for that territory.
    Optional ?setmana=YYYY-MM-DD for historical weeks.
    """
    territori = request.GET.get("t", "").upper()

    if not territori:
        # Territory selector page — PPCC featured on top, rest in flat grid
        ppcc = {
            "codi": "PPCC",
            "nom": TERRITORI_NOMS["PPCC"],
            "desc": TERRITORI_DESCRIPCIONS["PPCC"],
        }

        return render(
            request,
            "web/ranking_selector.html",
            {
                "ppcc": ppcc,
                "territoris": TERRITORIS_SELECTOR,
            },
        )

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
    darrera_actualitzacio = _ranking_last_modified_dt(territori, setmana)
    nom_territori = TERRITORI_NOMS[territori]

    return render(
        request,
        "web/ranking.html",
        {
            "ranking": ranking,
            "es_provisional": es_provisional,
            "setmana": setmana,
            "data_calcul": data_calcul,
            "darrera_actualitzacio": darrera_actualitzacio,
            "territori": territori,
            "territori_actiu": territori,
            "nom_territori": nom_territori,
            "territoris_nav": TERRITORIS_SELECTOR,
        },
    )


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
    qs = Artista.objects.filter(aprovat=True).prefetch_related(
        "territoris", "localitats__municipi"
    )

    territori = request.GET.get("territori", "").upper()
    if territori in ("CAT", "VAL", "BAL"):
        qs = qs.filter(territoris__codi=territori)

    cerca = request.GET.get("q", "").strip()
    if cerca:
        qs = qs.filter(nom__icontains=cerca)

    qs = qs.distinct().order_by("nom")
    paginator = Paginator(qs, 40)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "web/artistes.html",
        {
            "page": page,
            "territori_filtre": territori,
            "cerca": cerca,
        },
    )


def perfil_artista(request: HttpRequest, slug: str) -> HttpResponse:
    """Artist profile with ranking history and discography.

    Non-approved artists show a minimal page with context-appropriate
    calls to action (register, propose info, or staff edit link).
    """
    artista = get_object_or_404(
        Artista.objects.prefetch_related("localitats__municipi"), slug=slug
    )

    if not artista.aprovat:
        return render(
            request,
            "web/artista_no_verificat.html",
            {
                "artista": artista,
            },
        )

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
        artista.albums.filter(cancons__verificada=True)
        .prefetch_related("cancons")
        .distinct()
        .order_by("-data_llancament")
    )

    return render(
        request,
        "web/artista.html",
        {
            "artista": artista,
            "territoris": territoris,
            "historial_setmanes": historial_setmanes,
            "discografia": discografia,
        },
    )


def perfil_album(request: HttpRequest, slug: str) -> HttpResponse:
    """Album page with cover, metadata, and track listing with ranking info."""
    album = get_object_or_404(
        Album.objects.select_related("artista"),
        slug=slug,
    )

    # Tracks on this album — verified ones first, then all
    cancons = (
        album.cancons.select_related("artista")
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

    return render(
        request,
        "web/album.html",
        {
            "album": album,
            "cancons": cancons,
            "cancons_al_ranking": cancons_al_ranking,
        },
    )


def mapa(request: HttpRequest) -> HttpResponse:
    """Three-level zoomable SVG map using D3.js."""
    import json

    from django.db import connection
    from django.db.models import Count

    latest = (
        RankingSetmanal.objects.order_by("-setmana")
        .values_list("setmana", flat=True)
        .first()
    )
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
        # R11: read locations through ArtistaLocalitat → Municipi instead of
        # the dropped legacy fields. An artist with multiple locations
        # appears in each one.
        for artista in Artista.objects.filter(
            aprovat=True, id__in=artist_ids.keys()
        ).prefetch_related("territoris", "localitats__municipi"):
            terrs = list(artista.territoris.values_list("codi", flat=True))
            info = {
                "nom": artista.nom,
                "slug": artista.slug,
                "aparicions": artist_ids.get(artista.id, 0),
                "territori": terrs[0] if terrs else "",
            }
            for loc in artista.localitats.all():
                if loc.municipi is None:
                    continue
                town = loc.municipi.nom.lower()
                com = loc.municipi.comarca.lower()
                artista_by_localitat.setdefault(town, []).append(info)
                if (
                    com not in artista_by_comarca
                    or info["aparicions"] > artista_by_comarca[com]["aparicions"]
                ):
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

    # S7: pass dicts directly so the template can use {% json_script %},
    # which safely serialises into a <script type="application/json"> tag
    # instead of being injected verbatim into executable JS. Artist names
    # (user-submitted via PropostaArtista.nom) can otherwise be weaponised
    # for XSS even though Django would normally escape HTML, because the
    # |safe filter disables that escaping.
    return render(
        request,
        "web/mapa.html",
        {
            "comarques_data": comarques_data,
            "municipis_data": municipis_data,
        },
    )


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


# ── Φ4 · public-facing transparency pages ────────────────────────────────


def com_funciona(request: HttpRequest) -> HttpResponse:
    """The editorial explanation page: how TopQuaranta computes its ranking.

    Always reflects the LIVE ConfiguracioGlobal values so the page is
    always honest about what's in effect right now. The per-week
    coefficient snapshots live on RankingSetmanal (R1) and could be
    surfaced alongside each week if we ever want to; the linked
    /com-funciona/historial/ page is a lighter stepping stone.
    """
    return render(
        request,
        "web/com_funciona.html",
        {
            "coeficients": _coeficients_context(),
        },
    )


def com_funciona_historial(request: HttpRequest) -> HttpResponse:
    """Anonymised public history of ConfiguracioGlobal changes.

    Reads StaffAuditLog rows with action='config_update' and exposes the
    diff metadata; actor email is stripped. Rationale: users have a
    right to know WHEN and HOW the algorithm changed, but the identity
    of the staff member who ran the edit is a staff concern, not public.
    """
    entries = StaffAuditLog.objects.filter(action="config_update").order_by(
        "-created_at"
    )[:100]
    # Flatten the diff metadata for the template. Each entry becomes a
    # dict with date + a list of (field, human_label, before, after).
    rows = []
    for e in entries:
        diff_map = (e.metadata or {}).get("diff") or {}
        changes = []
        for field, beforeafter in diff_map.items():
            meta = COEFICIENTS_DESCRIPCIO.get(field, {"label": field, "blurb": ""})
            changes.append(
                {
                    "field": field,
                    "label": meta["label"],
                    "before": beforeafter.get("before", "—"),
                    "after": beforeafter.get("after", "—"),
                }
            )
        if changes:
            rows.append({"date": e.created_at, "changes": changes})

    return render(
        request,
        "web/com_funciona_historial.html",
        {
            "rows": rows,
        },
    )
