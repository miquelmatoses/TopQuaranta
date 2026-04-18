"""Staff views for track (canco) management."""

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from music.audit import log_staff_action
from music.constants import MOTIUS_REBUIG, MOTIUS_VALIDS
from music.ml import recalcular_ml_si_cal
from music.models import Album, Artista, Canco
from music.services import (
    aprovar_canco,
    rebutjar_album,
    rebutjar_artista,
    rebutjar_canco,
)

from . import apply_ordering, paginate, staff_required

CANCONS_ORDER_FIELDS = {
    "nom": "nom",
    "artista": "artista__nom",
    "album": "album__nom",
    "data": "data_llancament",
    "ml": "ml_confianca",
    "isrc": "isrc",
}


@staff_required
def llista(request: HttpRequest) -> HttpResponse:
    """List tracks with filters, search, and bulk actions."""
    qs = Canco.objects.select_related("artista", "album").prefetch_related(
        "artista__territoris"
    )

    # Filter: verificada (defaults to non-verified)
    verificada = request.GET.get("verificada", "0")
    if verificada == "0":
        qs = qs.filter(verificada=False, activa=True)
    elif verificada == "1":
        qs = qs.filter(verificada=True)
    # When "Totes" is selected, include inactive too (for debugging)

    # Filter: ml_classe
    ml_classe = request.GET.get("ml_classe", "")
    if ml_classe in ("A", "B", "C"):
        qs = qs.filter(ml_classe=ml_classe)

    # Filter: Silero VAD voice fraction (triage hint, not hard gate).
    # "inst" → probably instrumental (voice < 10%)
    # "dubte" → uncertain (10–40%)
    # "vocal" → clearly vocal (>= 40%)
    # "pendent" → not yet analysed by Silero
    silero = request.GET.get("silero", "")
    if silero == "inst":
        qs = qs.filter(silero_veu_probabilitat__lt=0.10)
    elif silero == "dubte":
        qs = qs.filter(
            silero_veu_probabilitat__gte=0.10, silero_veu_probabilitat__lt=0.40
        )
    elif silero == "vocal":
        qs = qs.filter(silero_veu_probabilitat__gte=0.40)
    elif silero == "pendent":
        qs = qs.filter(silero_processat_at__isnull=True)

    # Filter: date range
    data_des = request.GET.get("data_des", "")
    data_fins = request.GET.get("data_fins", "")
    if data_des:
        qs = qs.filter(data_llancament__gte=data_des)
    if data_fins:
        qs = qs.filter(data_llancament__lte=data_fins)

    # Search
    cerca = request.GET.get("q", "").strip()
    if cerca:
        qs = qs.filter(Q(nom__icontains=cerca) | Q(artista__nom__icontains=cerca))

    qs, current_order, current_dir = apply_ordering(
        request, qs, CANCONS_ORDER_FIELDS, default="-ml_confianca"
    )
    page = paginate(request, qs)

    return render(
        request,
        "web/staff/cancons.html",
        {
            "staff_section": "cancons",
            "page": page,
            "verificada": verificada,
            "ml_classe": ml_classe,
            "silero": silero,
            "data_des": data_des,
            "data_fins": data_fins,
            "cerca": cerca,
            "motius": MOTIUS_REBUIG,
            "current_order": current_order,
            "current_dir": current_dir,
        },
    )


@staff_required
def accio(request: HttpRequest) -> HttpResponse:
    """Handle bulk actions on tracks."""
    if request.method != "POST":
        return redirect("staff:cancons")

    action = request.POST.get("action", "")
    ids = request.POST.getlist("ids")
    if not ids:
        messages.error(request, "No has seleccionat cap cançó.")
        return redirect("staff:cancons")

    cancons_qs = Canco.objects.filter(pk__in=ids).select_related("artista", "album")

    if action == "aprovar":
        with transaction.atomic():
            for canco in cancons_qs:
                aprovar_canco(canco)
                log_staff_action(request, "canco_aprovar", target=canco)
        recalcular_ml_si_cal()
        messages.success(request, f"{cancons_qs.count()} cancons aprovades.")
        return redirect("staff:cancons")

    # All rejection actions require motiu
    motiu = request.POST.get("motiu", "")
    if motiu not in MOTIUS_VALIDS:
        messages.error(request, "Has de seleccionar un motiu de rebuig.")
        return redirect("staff:cancons")

    if action == "rebutjar":
        msgs = []
        with transaction.atomic():
            if motiu == "artista_incorrecte":
                artista_ids = set(cancons_qs.values_list("artista_id", flat=True))
                for artista in Artista.objects.filter(pk__in=artista_ids):
                    count = rebutjar_artista(artista, motiu)
                    log_staff_action(
                        request,
                        "artista_rebutjar",
                        target=artista,
                        motiu=motiu,
                        cancons_afectades=count,
                    )
                    msgs.append(f"{count} cancons de {artista.nom}")
            elif motiu == "album_incorrecte":
                album_ids = set(cancons_qs.values_list("album_id", flat=True))
                for album in Album.objects.filter(pk__in=album_ids):
                    count = rebutjar_album(album, motiu)
                    log_staff_action(
                        request,
                        "canco_rebutjar_album",
                        target=album,
                        motiu=motiu,
                        cancons_afectades=count,
                    )
                    msgs.append(f"{count} cancons de l'album {album.nom}")
            else:
                for canco in cancons_qs:
                    rebutjar_canco(canco, motiu)
                    log_staff_action(
                        request,
                        "canco_rebutjar",
                        target=canco,
                        motiu=motiu,
                    )
                msgs.append(f"{cancons_qs.count()} cancons rebutjades")
        recalcular_ml_si_cal()
        messages.success(request, f"Motiu: {motiu}. " + "; ".join(msgs) + ".")

    elif action == "rebutjar_album":
        album_ids = set(cancons_qs.values_list("album_id", flat=True).distinct())
        msgs = []
        with transaction.atomic():
            if motiu == "artista_incorrecte":
                artista_ids = set(
                    Canco.objects.filter(
                        album_id__in=album_ids, verificada=False
                    ).values_list("artista_id", flat=True)
                )
                for artista in Artista.objects.filter(pk__in=artista_ids):
                    count = rebutjar_artista(artista, motiu)
                    log_staff_action(
                        request,
                        "artista_rebutjar",
                        target=artista,
                        motiu=motiu,
                        cancons_afectades=count,
                    )
                    msgs.append(f"{count} cancons de {artista.nom}")
            else:
                for album in Album.objects.filter(pk__in=album_ids):
                    count = rebutjar_album(album, motiu)
                    log_staff_action(
                        request,
                        "canco_rebutjar_album",
                        target=album,
                        motiu=motiu,
                        cancons_afectades=count,
                    )
                    msgs.append(f"{count} cancons de l'album {album.nom}")
        recalcular_ml_si_cal()
        messages.success(request, f"Motiu: {motiu}. " + "; ".join(msgs) + ".")

    else:
        messages.error(request, "Acció desconeguda.")

    return redirect("staff:cancons")


@staff_required
def editar(request: HttpRequest, pk: int) -> HttpResponse:
    """Edit a single track."""
    canco = get_object_or_404(
        Canco.objects.select_related("artista", "album").prefetch_related(
            "artistes_col"
        ),
        pk=pk,
    )

    if request.method == "POST":
        canco.nom = request.POST.get("nom", canco.nom).strip()
        canco.isrc = request.POST.get("isrc", canco.isrc).strip()
        canco.lastfm_nom = request.POST.get("lastfm_nom", "").strip()
        # D2: lastfm_mbid / lastfm_verificat fields dropped.
        canco.verificada = "verificada" in request.POST
        canco.activa = "activa" in request.POST

        data_raw = request.POST.get("data_llancament", "").strip()
        if data_raw:
            canco.data_llancament = data_raw
        else:
            canco.data_llancament = None

        deezer_raw = request.POST.get("deezer_id", "").strip()
        if deezer_raw:
            try:
                canco.deezer_id = int(deezer_raw)
            except ValueError:
                messages.error(request, "Deezer ID ha de ser un nombre enter.")
                return redirect("staff:canco_editar", pk=canco.pk)
        else:
            canco.deezer_id = None

        canco.save()
        log_staff_action(request, "canco_edit", target=canco)
        messages.success(request, f"Cançó «{canco.nom}» actualitzada.")
        return redirect("staff:canco_editar", pk=canco.pk)

    return render(
        request,
        "web/staff/canco_edit.html",
        {
            "staff_section": "cancons",
            "canco": canco,
        },
    )
