"""Staff views for track (cançó) management."""

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from music.constants import MOTIUS_REBUIG, MOTIUS_VALIDS
from music.ml import recalcular_ml_si_cal
from music.models import Album, Artista, Canco
from music.services import aprovar_canco, rebutjar_album, rebutjar_artista, rebutjar_canco

from . import paginate, staff_required


@staff_required
def llista(request: HttpRequest) -> HttpResponse:
    """List tracks with filters, search, and bulk actions."""
    qs = Canco.objects.select_related("artista", "album").prefetch_related(
        "artista__territoris"
    )

    # Filter: verificada (defaults to non-verified)
    verificada = request.GET.get("verificada", "0")
    if verificada == "0":
        qs = qs.filter(verificada=False)
    elif verificada == "1":
        qs = qs.filter(verificada=True)

    # Filter: ml_classe
    ml_classe = request.GET.get("ml_classe", "")
    if ml_classe in ("A", "B", "C"):
        qs = qs.filter(ml_classe=ml_classe)

    # Filter: data_llancament year
    any_filtre = request.GET.get("any", "")
    if any_filtre.isdigit():
        qs = qs.filter(data_llancament__year=int(any_filtre))

    # Search
    cerca = request.GET.get("q", "").strip()
    if cerca:
        qs = qs.filter(Q(nom__icontains=cerca) | Q(artista__nom__icontains=cerca))

    qs = qs.order_by("-ml_confianca")
    page = paginate(request, qs)

    return render(request, "web/staff/cancons.html", {
        "staff_section": "cancons",
        "page": page,
        "verificada": verificada,
        "ml_classe": ml_classe,
        "any_filtre": any_filtre,
        "cerca": cerca,
        "motius": MOTIUS_REBUIG,
    })


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
        recalcular_ml_si_cal()
        messages.success(request, f"{cancons_qs.count()} cançons aprovades.")
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
                    msgs.append(f"{count} cançons de {artista.nom}")
            elif motiu == "album_incorrecte":
                album_ids = set(cancons_qs.values_list("album_id", flat=True))
                for album in Album.objects.filter(pk__in=album_ids):
                    count = rebutjar_album(album, motiu)
                    msgs.append(f"{count} cançons de l'àlbum {album.nom}")
            else:
                for canco in cancons_qs:
                    rebutjar_canco(canco, motiu)
                msgs.append(f"{cancons_qs.count()} cançons rebutjades")
        recalcular_ml_si_cal()
        messages.success(request, f"Motiu: {motiu}. " + "; ".join(msgs) + ".")

    elif action == "rebutjar_album":
        album_ids = set(cancons_qs.values_list("album_id", flat=True).distinct())
        msgs = []
        with transaction.atomic():
            if motiu == "artista_incorrecte":
                artista_ids = set(
                    Canco.objects.filter(album_id__in=album_ids, verificada=False)
                    .values_list("artista_id", flat=True)
                )
                for artista in Artista.objects.filter(pk__in=artista_ids):
                    count = rebutjar_artista(artista, motiu)
                    msgs.append(f"{count} cançons de {artista.nom}")
            else:
                for album in Album.objects.filter(pk__in=album_ids):
                    count = rebutjar_album(album, motiu)
                    msgs.append(f"{count} cançons de l'àlbum {album.nom}")
        recalcular_ml_si_cal()
        messages.success(request, f"Motiu: {motiu}. " + "; ".join(msgs) + ".")

    else:
        messages.error(request, "Acció desconeguda.")

    return redirect("staff:cancons")
