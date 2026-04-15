"""Staff views for approved artist management."""

from django.contrib import messages
from django.db import connection, transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from music.constants import MOTIUS_REBUIG
from music.ml import recalcular_ml_si_cal
from music.models import Artista, Canco, Territori
from music.services import rebutjar_artista

from . import paginate, staff_required

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
    """Build comarca→territory code map from municipis table (cached)."""
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
    """List approved artists with filters and search."""
    qs = Artista.objects.prefetch_related("territoris")

    # Filters
    aprovat = request.GET.get("aprovat", "1")
    if aprovat == "1":
        qs = qs.filter(aprovat=True)
    elif aprovat == "0":
        qs = qs.filter(aprovat=False)

    deezer = request.GET.get("deezer", "")
    if deezer == "si":
        qs = qs.filter(deezer_id__isnull=False)
    elif deezer == "no":
        qs = qs.filter(deezer_no_trobat=True)

    territori = request.GET.get("territori", "")
    if territori:
        qs = qs.filter(territoris__codi=territori)

    cerca = request.GET.get("q", "").strip()
    if cerca:
        qs = qs.filter(nom__icontains=cerca)

    qs = qs.distinct().order_by("nom")
    page = paginate(request, qs)

    return render(request, "web/staff/artistes.html", {
        "staff_section": "artistes",
        "page": page,
        "aprovat": aprovat,
        "deezer": deezer,
        "territori": territori,
        "cerca": cerca,
    })


@staff_required
def editar(request: HttpRequest, pk: int) -> HttpResponse:
    """Edit a single artist."""
    artista = get_object_or_404(Artista, pk=pk)
    territoris_actuals = list(artista.territoris.values_list("codi", flat=True))
    tots_territoris = Territori.objects.all().order_by("codi")

    if request.method == "POST":
        artista.nom = request.POST.get("nom", artista.nom).strip()
        artista.lastfm_nom = request.POST.get("lastfm_nom", artista.lastfm_nom).strip()
        artista.localitat = request.POST.get("localitat", "").strip()
        artista.comarca = request.POST.get("comarca", "").strip()

        deezer_id_str = request.POST.get("deezer_id", "").strip()
        old_deezer_id = artista.deezer_id
        if deezer_id_str:
            try:
                artista.deezer_id = int(deezer_id_str)
            except ValueError:
                pass
        else:
            artista.deezer_id = None

        artista.aprovat = "aprovat" in request.POST
        artista.save()

        # Update territories
        terr_codis = request.POST.getlist("territoris")
        if terr_codis:
            artista.territoris.set(Territori.objects.filter(codi__in=terr_codis))

        # Auto-assign territory from comarca if territories were empty
        if not terr_codis and artista.comarca:
            comarca_map = _get_comarca_map()
            codi = comarca_map.get(artista.comarca.strip())
            if codi:
                t = Territori.objects.filter(codi=codi).first()
                if t:
                    artista.territoris.set([t])

        # If deezer_id changed, clean up old unverified tracks
        if old_deezer_id != artista.deezer_id and artista.deezer_id is not None:
            deleted, _ = Canco.objects.filter(
                artista=artista, verificada=False
            ).delete()
            artista.deezer_no_trobat = False
            artista.save(update_fields=["deezer_no_trobat"])
            if deleted:
                messages.info(request, f"{deleted} cançons antigues (no verificades) esborrades.")

        messages.success(request, f"Artista «{artista.nom}» actualitzat.")
        return redirect("staff:artista_editar", pk=artista.pk)

    return render(request, "web/staff/artista_edit.html", {
        "staff_section": "artistes",
        "artista": artista,
        "territoris_actuals": territoris_actuals,
        "tots_territoris": tots_territoris,
    })


@staff_required
def accio(request: HttpRequest) -> HttpResponse:
    """Handle bulk actions on artists."""
    if request.method != "POST":
        return redirect("staff:artistes")

    action = request.POST.get("action", "")
    ids = request.POST.getlist("ids")

    if not ids:
        messages.error(request, "No has seleccionat cap artista.")
        return redirect("staff:artistes")

    queryset = Artista.objects.filter(pk__in=ids)

    if action == "marcar_sense_deezer":
        motiu = request.POST.get("motiu", "artista_incorrecte")
        total_cancons = 0
        with transaction.atomic():
            for artista in queryset:
                total_cancons += rebutjar_artista(artista, motiu)
        recalcular_ml_si_cal()
        messages.success(
            request,
            f"{queryset.count()} artistes marcats sense Deezer, "
            f"{total_cancons} cançons esborrades.",
        )

    elif action == "aprovar":
        ok = 0
        errors = []
        comarca_map = _get_comarca_map()
        for artista in queryset:
            if not artista.localitat or not artista.comarca:
                errors.append(f"{artista.nom}: falta localitat o comarca")
                continue
            artista.aprovat = True
            artista.save(update_fields=["aprovat"])
            codi = comarca_map.get(artista.comarca.strip())
            if codi:
                t = Territori.objects.filter(codi=codi).first()
                if t:
                    artista.territoris.set([t])
            ok += 1
        if errors:
            messages.error(request, "; ".join(errors))
        if ok:
            messages.success(request, f"{ok} artistes aprovats.")

    else:
        messages.error(request, "Acció desconeguda.")

    return redirect("staff:artistes")
