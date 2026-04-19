"""Staff views for pending (auto-discovered) artist approval."""

import json

from django.db import transaction
from django.db.models import Count, F, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from music.audit import log_staff_action
from music.models import Artista, ArtistaLocalitat, Municipi
from web.api.views import (  # noqa: F401 — re-exported for staff URL routing
    api_comarques,
    api_municipi_lookup,
    api_municipis,
    api_territoris,
)

from . import apply_ordering, paginate, staff_required

PENDENTS_ORDER_FIELDS = {
    "nom": "nom",
    "nb_verif": "nb_verif",
}


@staff_required
def llista(request: HttpRequest) -> HttpResponse:
    """List pending auto-discovered artists."""
    qs = (
        Artista.objects.filter(aprovat=False, auto_descobert=True)
        .select_related()
        .prefetch_related("territoris", "deezer_ids", "localitats__municipi")
        .annotate(
            nb_verif_main=Count("cancons", filter=Q(cancons__verificada=True)),
            nb_verif_col=Count(
                "participacions", filter=Q(participacions__verificada=True)
            ),
        )
        .annotate(nb_verif=F("nb_verif_main") + F("nb_verif_col"))
    )

    qs, current_order, current_dir = apply_ordering(
        request, qs, PENDENTS_ORDER_FIELDS, default="-nb_verif"
    )
    page = paginate(request, qs, per_page=50)

    return render(
        request,
        "web/staff/pendents.html",
        {
            "staff_section": "pendents",
            "page": page,
            "total": qs.count(),
            "current_order": current_order,
            "current_dir": current_dir,
        },
    )


@staff_required
def api_aprovar(request: HttpRequest, pk: int) -> JsonResponse:
    """AJAX: approve a pending artist with location."""
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

    municipi_id = data.get("municipi_id")
    comarca = data.get("comarca", "").strip()
    localitat = data.get("localitat", "").strip()

    if not municipi_id and (not comarca or not localitat):
        return JsonResponse({"error": "Cal seleccionar un municipi"}, status=400)

    with transaction.atomic():
        # R11: only ArtistaLocalitat is updated; legacy fields are gone.
        if municipi_id:
            try:
                municipi = Municipi.objects.get(pk=int(municipi_id))
            except Municipi.DoesNotExist:
                return JsonResponse({"error": "Municipi no trobat"}, status=404)
            ArtistaLocalitat.objects.create(artista=artista, municipi=municipi)
            audit_loc = f"{municipi.nom}, {municipi.comarca}"
            territori = municipi.territori_id
        else:
            # Fallback: try to match by name+comarca
            try:
                municipi = Municipi.objects.get(nom=localitat, comarca=comarca)
                ArtistaLocalitat.objects.create(artista=artista, municipi=municipi)
                audit_loc = f"{municipi.nom}, {municipi.comarca}"
                territori = municipi.territori_id
            except Municipi.DoesNotExist:
                # Manual entry — Municipi unknown, store free text
                ArtistaLocalitat.objects.create(
                    artista=artista,
                    municipi=None,
                    localitat_manual=f"{localitat}, {comarca}",
                )
                audit_loc = f"{localitat}, {comarca} (manual)"
                territori = "ALT"

        artista.aprovat = True
        artista.save(update_fields=["aprovat"])
        # Signal auto-syncs territories

    log_staff_action(
        request,
        "pendent_aprovar",
        target=artista,
        territori=territori,
        localitat=audit_loc,
    )
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
        log_staff_action(
            request,
            "pendent_descartar",
            target=artista,
            action_taken="kept_auto_descobert_false",
            reason="had verified tracks",
        )
        return JsonResponse({"ok": True, "action": "kept"})
    else:
        # Snapshot before delete so the audit row remains meaningful.
        label = str(artista)
        pk_val = artista.pk
        artista.delete()
        log_staff_action(
            request,
            "pendent_descartar",
            target=None,
            action_taken="deleted",
            target_id_deleted=pk_val,
            target_label_deleted=label,
        )
        return JsonResponse({"ok": True, "action": "deleted"})
