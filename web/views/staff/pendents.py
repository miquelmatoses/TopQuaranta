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
    """List artists awaiting staff review.

    Filter: `aprovat=False AND auto_descobert=True`. The `auto_descobert`
    flag is read here as "in the pendents queue" rather than strictly
    "auto-discovered" — it is also set by the bulk-un-approval action
    that sweeps approved artists missing Deezer or localitat data back
    into this list for re-review.
    """
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

    # Pre-populate data for JS: per-pk deezer_id + localitat principal.
    existing_data = {}
    for artista in page.object_list:
        loc = artista.localitats.select_related("municipi__territori").first()
        entry = {
            "deezer_id": artista.deezer_id_principal or "",
            "loc": None,
        }
        if loc:
            if loc.municipi:
                entry["loc"] = {
                    "municipi_id": loc.municipi.pk,
                    "municipi_nom": loc.municipi.nom,
                    "comarca": loc.municipi.comarca,
                    "territori": loc.municipi.territori_id,
                    "manual": "",
                }
            elif loc.localitat_manual:
                entry["loc"] = {
                    "municipi_id": None,
                    "municipi_nom": "",
                    "comarca": "",
                    "territori": "ALT",
                    "manual": loc.localitat_manual,
                }
        existing_data[artista.pk] = entry

    return render(
        request,
        "web/staff/pendents.html",
        {
            "staff_section": "pendents",
            "page": page,
            "total": qs.count(),
            "current_order": current_order,
            "current_dir": current_dir,
            "existing_data_json": json.dumps(existing_data),
        },
    )


@staff_required
def api_aprovar(request: HttpRequest, pk: int) -> JsonResponse:
    """AJAX: approve a pending artist, optionally adding Deezer id + location.

    Accepts in the JSON body:
      - `deezer_id`   (optional): new Deezer artist id to attach. Skipped
        if the artist already has that id.
      - `municipi_id` / `comarca` + `localitat` (optional if the artist
        already has a localitat, required otherwise).
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        artista = Artista.objects.get(pk=pk)
    except Artista.DoesNotExist:
        return JsonResponse({"error": "Artista not found"}, status=404)

    from music.models import ArtistaDeezer  # avoid circular

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}

    deezer_id_raw = str(data.get("deezer_id", "")).strip()
    municipi_id = data.get("municipi_id")
    comarca = data.get("comarca", "").strip()
    localitat = data.get("localitat", "").strip()

    cascade_selected = bool(municipi_id) or (bool(comarca) and bool(localitat))
    has_existing_loc = artista.localitats.exists()
    if not cascade_selected and not has_existing_loc:
        return JsonResponse({"error": "Cal seleccionar un municipi"}, status=400)

    deezer_id: int | None = None
    if deezer_id_raw:
        try:
            deezer_id = int(deezer_id_raw)
        except ValueError:
            return JsonResponse({"error": "Deezer ID invàlid"}, status=400)

    audit_loc = None
    territori = None

    with transaction.atomic():
        # ── Deezer link (optional; skipped if duplicate) ──
        if deezer_id is not None:
            if not artista.deezer_ids.filter(deezer_id=deezer_id).exists():
                ArtistaDeezer.objects.create(
                    artista=artista,
                    deezer_id=deezer_id,
                    principal=not artista.deezer_ids.exists(),
                )
                # Signal `clear_deezer_no_trobat_on_ad_save` also syncs
                # the legacy flag.

        # ── Localitat (optional if artist already has one) ──
        if cascade_selected:
            if municipi_id:
                try:
                    municipi = Municipi.objects.get(pk=int(municipi_id))
                except Municipi.DoesNotExist:
                    return JsonResponse({"error": "Municipi no trobat"}, status=404)
                ArtistaLocalitat.objects.create(artista=artista, municipi=municipi)
                audit_loc = f"{municipi.nom}, {municipi.comarca}"
                territori = municipi.territori_id
            else:
                try:
                    municipi = Municipi.objects.get(nom=localitat, comarca=comarca)
                    ArtistaLocalitat.objects.create(artista=artista, municipi=municipi)
                    audit_loc = f"{municipi.nom}, {municipi.comarca}"
                    territori = municipi.territori_id
                except Municipi.DoesNotExist:
                    ArtistaLocalitat.objects.create(
                        artista=artista,
                        municipi=None,
                        localitat_manual=f"{localitat}, {comarca}",
                    )
                    audit_loc = f"{localitat}, {comarca} (manual)"
                    territori = "ALT"
        else:
            loc = artista.localitats.select_related("municipi__territori").first()
            if loc and loc.municipi:
                audit_loc = f"{loc.municipi.nom}, {loc.municipi.comarca} (existent)"
                territori = loc.municipi.territori_id
            elif loc:
                audit_loc = f"{loc.localitat_manual} (existent, manual)"
                territori = "ALT"

        artista.aprovat = True
        # Also clear auto_descobert so the artist drops out of the pendents
        # queue (symmetric with the descartar-with-verified-tracks path).
        artista.auto_descobert = False
        artista.save(update_fields=["aprovat", "auto_descobert"])
        # Signal auto-syncs territories from localitats.

    log_staff_action(
        request,
        "pendent_aprovar",
        target=artista,
        territori=territori,
        localitat=audit_loc,
        deezer_id_afegit=deezer_id,
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
