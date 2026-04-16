"""Staff views for album management."""

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from music.audit import log_staff_action
from music.models import Album

from . import staff_required


@staff_required
def editar(request: HttpRequest, pk: int) -> HttpResponse:
    """Edit a single album."""
    album = get_object_or_404(Album.objects.select_related("artista"), pk=pk)
    cancons = album.cancons.select_related("artista").order_by("nom")

    if request.method == "POST":
        was_descartat = album.descartat
        album.nom = request.POST.get("nom", album.nom).strip()
        dl = request.POST.get("data_llancament", "").strip()
        album.data_llancament = dl if dl else None
        album.tipus = request.POST.get("tipus", album.tipus).strip()
        dz = request.POST.get("deezer_id", "").strip()
        album.deezer_id = int(dz) if dz else None
        album.imatge_url = request.POST.get("imatge_url", "").strip()
        album.descartat = "descartat" in request.POST
        album.save()

        # Record a plain edit; if descartat just flipped to True, record
        # the dedicated action too so the audit view highlights it.
        log_staff_action(request, "album_edit", target=album)
        if album.descartat and not was_descartat:
            log_staff_action(request, "album_descartar", target=album)

        messages.success(request, f"Àlbum «{album.nom}» actualitzat.")
        return redirect("staff:album_editar", pk=album.pk)

    return render(request, "web/staff/album_edit.html", {
        "staff_section": "cancons",
        "album": album,
        "cancons": cancons,
    })
