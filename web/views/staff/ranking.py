"""Staff views for provisional ranking review."""

from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from music.audit import log_staff_action
from music.constants import MOTIUS_REBUIG, MOTIUS_VALIDS, TERRITORI_NOMS
from music.ml import recalcular_ml_si_cal
from music.models import Artista
from music.services import rebutjar_artista, rebutjar_canco
from ranking.models import RankingProvisional

from . import apply_ordering, paginate, staff_required

# Display order: fixed territories first, then aggregates and optional.
TERRITORIS = [
    (codi, TERRITORI_NOMS[codi])
    for codi in ("CAT", "VAL", "BAL", "CNO", "AND", "FRA", "ALG", "CAR", "ALT", "PPCC")
]

RANKING_ORDER_FIELDS = {
    "posicio": "posicio",
    "artista": "canco__artista__nom",
    "canco": "canco__nom",
    "playcount": "lastfm_playcount",
    "dies": "dies_en_top",
}


@staff_required
def llista(request: HttpRequest) -> HttpResponse:
    """List provisional ranking for a territory."""
    territori = request.GET.get("territori", "CAT")
    if territori not in {t[0] for t in TERRITORIS}:
        territori = "CAT"

    qs = (
        RankingProvisional.objects.filter(territori=territori)
        .select_related("canco", "canco__artista")
    )

    qs, current_order, current_dir = apply_ordering(
        request, qs, RANKING_ORDER_FIELDS, default="posicio"
    )

    return render(request, "web/staff/ranking.html", {
        "staff_section": "ranking",
        "ranking": qs,
        "territori": territori,
        "territoris": TERRITORIS,
        "motius": MOTIUS_REBUIG,
        "current_order": current_order,
        "current_dir": current_dir,
    })


@staff_required
def accio(request: HttpRequest) -> HttpResponse:
    """Handle ranking rejection actions."""
    if request.method != "POST":
        return redirect("staff:ranking")

    action = request.POST.get("action", "")
    ids = request.POST.getlist("ids")
    motiu = request.POST.get("motiu", "")

    if not ids:
        messages.error(request, "No has seleccionat cap entrada.")
        return redirect("staff:ranking")

    if motiu not in MOTIUS_VALIDS:
        messages.error(request, "Has de seleccionar un motiu de rebuig.")
        return redirect("staff:ranking")

    entries = RankingProvisional.objects.filter(pk__in=ids).select_related(
        "canco__artista", "canco__album"
    )

    if action == "rebutjar_canco":
        total = 0
        with transaction.atomic():
            for rp in entries:
                rebutjar_canco(rp.canco, motiu)
                log_staff_action(
                    request, "canco_rebutjar", target=rp.canco,
                    motiu=motiu, source="provisional_ranking",
                )
                rp.delete()
                total += 1
        recalcular_ml_si_cal()
        messages.success(request, f"{total} cancons rebutjades (verificada=False).")

    elif action == "rebutjar_artista":
        artista_ids = set(entries.values_list("canco__artista_id", flat=True))
        total_cancons = 0
        with transaction.atomic():
            for artista in Artista.objects.filter(pk__in=artista_ids):
                count = rebutjar_artista(artista, motiu)
                total_cancons += count
                log_staff_action(
                    request, "artista_rebutjar", target=artista,
                    motiu=motiu, cancons_afectades=count,
                    source="provisional_ranking",
                )
            RankingProvisional.objects.filter(
                canco__artista_id__in=artista_ids
            ).delete()
        recalcular_ml_si_cal()
        messages.success(
            request,
            f"{len(artista_ids)} artistes rebutjats, {total_cancons} cancons esborrades.",
        )
    else:
        messages.error(request, "Acció desconeguda.")

    return redirect("staff:ranking")
