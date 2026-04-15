"""Staff views for pending (auto-discovered) artist approval."""

import json

from django.db import connection, transaction
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from music.models import Artista, Territori

from . import staff_required

_MUNICIPIS_TERRITORI_MAP = {
    "Catalunya": "CAT",
    "País Valencià": "VAL",
    "Illes": "BAL",
    "Catalunya del Nord": "CNO",
    "Andorra": "AND",
    "Franja de Ponent": "FRA",
    "L'Alguer": "ALG",
    "El Carxe": "CAR",
}

_COMARCA_MAP: dict[str, str] | None = None


def _get_comarca_map() -> dict[str, str]:
    global _COMARCA_MAP
    if _COMARCA_MAP is None:
        _COMARCA_MAP = {}
        with connection.cursor() as cursor:
            cursor.execute('SELECT DISTINCT "Comarca", "Territori" FROM municipis')
            for comarca, territori in cursor.fetchall():
                codi = _MUNICIPIS_TERRITORI_MAP.get(territori)
                if codi and comarca:
                    _COMARCA_MAP[comarca.strip()] = codi
    return _COMARCA_MAP


@staff_required
def llista(request: HttpRequest) -> HttpResponse:
    """List pending auto-discovered artists."""
    qs = (
        Artista.objects.filter(aprovat=False, auto_descobert=True)
        .annotate(nb_verif=Count("cancons", filter=Q(cancons__verificada=True)))
        .order_by("-nb_verif")
    )

    return render(request, "web/staff/pendents.html", {
        "staff_section": "pendents",
        "artistes": qs,
    })


@staff_required
def api_territoris(request: HttpRequest) -> JsonResponse:
    """JSON API: list territories from municipis table."""
    result = []
    seen = set()
    with connection.cursor() as cursor:
        cursor.execute('SELECT DISTINCT "Territori" FROM municipis ORDER BY 1')
        for (territori,) in cursor.fetchall():
            codi = _MUNICIPIS_TERRITORI_MAP.get(territori)
            if codi and codi not in seen:
                result.append({"codi": codi, "nom": territori})
                seen.add(codi)
    return JsonResponse(result, safe=False)


@staff_required
def api_comarques(request: HttpRequest) -> JsonResponse:
    """JSON API: list comarques for a territory."""
    territori_codi = request.GET.get("territori", "")
    reverse_map = {v: k for k, v in _MUNICIPIS_TERRITORI_MAP.items()}
    territori_nom = reverse_map.get(territori_codi, "")
    if not territori_nom:
        return JsonResponse([], safe=False)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT DISTINCT "Comarca" FROM municipis WHERE "Territori" = %s ORDER BY 1',
            [territori_nom],
        )
        result = [row[0] for row in cursor.fetchall()]
    return JsonResponse(result, safe=False)


@staff_required
def api_municipis(request: HttpRequest) -> JsonResponse:
    """JSON API: list municipis for a comarca."""
    comarca = request.GET.get("comarca", "")
    if not comarca:
        return JsonResponse([], safe=False)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT "Municipi" FROM municipis WHERE "Comarca" = %s ORDER BY 1',
            [comarca],
        )
        result = [row[0] for row in cursor.fetchall()]
    return JsonResponse(result, safe=False)


@staff_required
def api_aprovar(request: HttpRequest, pk: int) -> JsonResponse:
    """AJAX: approve a pending artist."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        artista = Artista.objects.get(pk=pk)
    except Artista.DoesNotExist:
        return JsonResponse({"error": "Artista not found"}, status=404)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    comarca = data.get("comarca", "").strip()
    localitat = data.get("localitat", "").strip()
    if not comarca or not localitat:
        return JsonResponse({"error": "Cal comarca i localitat"}, status=400)

    artista.comarca = comarca
    artista.localitat = localitat
    artista.aprovat = True
    artista.save(update_fields=["aprovat", "localitat", "comarca"])

    comarca_map = _get_comarca_map()
    codi = comarca_map.get(comarca)
    territori = ""
    if codi:
        t = Territori.objects.filter(codi=codi).first()
        if t:
            artista.territoris.set([t])
            territori = codi
    return JsonResponse({"ok": True, "territori": territori})


@staff_required
def api_descartar(request: HttpRequest, pk: int) -> JsonResponse:
    """AJAX: discard a pending artist."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        artista = Artista.objects.get(pk=pk)
    except Artista.DoesNotExist:
        return JsonResponse({"error": "Artista not found"}, status=404)

    has_verified = artista.cancons.filter(verificada=True).exists()
    if has_verified:
        artista.auto_descobert = False
        artista.save(update_fields=["auto_descobert"])
        return JsonResponse({"ok": True, "action": "kept"})
    else:
        artista.delete()
        return JsonResponse({"ok": True, "action": "deleted"})
