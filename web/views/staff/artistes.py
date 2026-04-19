"""Staff views for approved artist management."""

import json
from collections import Counter

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from comptes.models import UserArtista
from music.audit import log_staff_action
from music.constants import MOTIUS_REBUIG
from music.ml import recalcular_ml_si_cal
from music.models import (
    Album,
    Artista,
    ArtistaDeezer,
    ArtistaLocalitat,
    Canco,
    HistorialRevisio,
    Municipi,
    Territori,
)
from music.services import rebutjar_artista
from music.utils import normalize_nom as _normalize_nom

from . import apply_ordering, paginate, staff_required

ARTISTES_ORDER_FIELDS = {
    "nom": "nom",
    "genere": "genere",
}


def _duplicate_nom_pks() -> list[int]:
    """Return the pks of every Artista whose normalised name is shared with
    at least one other Artista. Merge candidates, essentially.

    Runs a single values_list('pk', 'nom') over the full Artista table and
    does the grouping in Python — cheaper than a group-by + self-join at
    the current scale (~4 300 rows, <10 ms).
    """
    pairs = list(Artista.objects.values_list("pk", "nom"))
    keys = [(pk, _normalize_nom(nom)) for pk, nom in pairs]
    counts = Counter(k for _pk, k in keys)
    dupe_keys = {k for k, c in counts.items() if c > 1}
    return [pk for pk, k in keys if k in dupe_keys]


@staff_required
def llista(request: HttpRequest) -> HttpResponse:
    """List approved artists with filters and search."""
    qs = Artista.objects.prefetch_related("territoris", "localitats__municipi")

    # Filters
    aprovat = request.GET.get("aprovat", "1")
    if aprovat == "1":
        qs = qs.filter(aprovat=True)
    elif aprovat == "0":
        qs = qs.filter(aprovat=False)

    deezer = request.GET.get("deezer", "")
    if deezer == "si":
        qs = qs.filter(deezer_ids__isnull=False)
    elif deezer == "no":
        # Source of truth: absence of any ArtistaDeezer row.
        qs = qs.filter(deezer_ids__isnull=True)

    territori = request.GET.get("territori", "")
    if territori:
        qs = qs.filter(territoris__codi=territori)

    cerca = request.GET.get("q", "").strip()
    if cerca:
        qs = qs.filter(nom__icontains=cerca)

    # Duplicate-name filter: surface merge candidates. When active we
    # override the default ordering so that near-duplicates sit together
    # in the list (case-only and accent-only variants cluster after
    # lowercasing; true accent folding would need the unaccent extension
    # but this is good enough to spot the pairs at a glance).
    duplicats = request.GET.get("duplicats", "")
    if duplicats == "si":
        qs = qs.filter(pk__in=_duplicate_nom_pks())

    qs = qs.distinct()
    default_order = "nom" if duplicats != "si" else None
    if duplicats == "si" and not request.GET.get("order"):
        qs = qs.order_by(Lower("nom"), "nom", "pk")
        current_order, current_dir = "nom", "asc"
    else:
        qs, current_order, current_dir = apply_ordering(
            request, qs, ARTISTES_ORDER_FIELDS, default=default_order or "nom"
        )
    page = paginate(request, qs)

    return render(
        request,
        "web/staff/artistes.html",
        {
            "staff_section": "artistes",
            "page": page,
            "aprovat": aprovat,
            "deezer": deezer,
            "territori": territori,
            "duplicats": duplicats,
            "cerca": cerca,
            "current_order": current_order,
            "current_dir": current_dir,
        },
    )


@staff_required
def crear(request: HttpRequest) -> HttpResponse:
    """Create a new Artista manually.

    Minimal form: only `nom` is required. Everything else is optional and
    can be filled in on the standard edit screen after creation. If the
    user also supplies a Deezer ID, we wire it up as the principal
    ArtistaDeezer row. On success we redirect to the full edit page so
    the staff can add locations, social links, additional Deezer ids,
    etc., from the familiar form.
    """
    if request.method == "POST":
        nom = request.POST.get("nom", "").strip()
        if not nom:
            messages.error(request, "El nom és obligatori.")
            return redirect("staff:artista_crear")

        lastfm_nom = request.POST.get("lastfm_nom", "").strip() or nom
        deezer_raw = request.POST.get("deezer_id", "").strip()
        deezer_id = None
        if deezer_raw:
            try:
                deezer_id = int(deezer_raw)
            except ValueError:
                messages.error(request, "Deezer ID ha de ser un nombre enter.")
                return redirect("staff:artista_crear")

        # Surface duplicate-name warning unless the user has acknowledged it.
        force = request.POST.get("force") == "1"
        if not force:
            existing_pks = _duplicate_nom_pks()
            hits = Artista.objects.filter(
                pk__in=existing_pks, nom__iexact=nom
            ) | Artista.objects.annotate(norm=Lower("nom")).filter(norm=nom.lower())
            hits = hits.distinct()[:5]
            hit_list = list(hits)
            if hit_list:
                return render(
                    request,
                    "web/staff/artista_crear.html",
                    {
                        "staff_section": "artistes",
                        "form_values": {
                            "nom": nom,
                            "lastfm_nom": lastfm_nom,
                            "deezer_id": deezer_raw,
                        },
                        "existing_duplicates": hit_list,
                    },
                )

        with transaction.atomic():
            artista = Artista.objects.create(
                nom=nom,
                lastfm_nom=lastfm_nom,
                aprovat=True,
                auto_descobert=False,
                font_descoberta="manual",
            )
            if deezer_id is not None:
                ArtistaDeezer.objects.create(
                    artista=artista,
                    deezer_id=deezer_id,
                    principal=True,
                )
            log_staff_action(
                request,
                "artista_crear",
                target=artista,
                deezer_id=deezer_id,
            )
        messages.success(
            request,
            f"Artista «{artista.nom}» creat. Afegeix localitzacions i xarxes aquí.",
        )
        return redirect("staff:artista_editar", pk=artista.pk)

    # GET
    return render(
        request,
        "web/staff/artista_crear.html",
        {
            "staff_section": "artistes",
            "form_values": {"nom": "", "lastfm_nom": "", "deezer_id": ""},
            "existing_duplicates": None,
        },
    )


@staff_required
def editar(request: HttpRequest, pk: int) -> HttpResponse:
    """Edit a single artist with multiple locations, social links, multiple Deezer IDs."""
    artista = get_object_or_404(Artista, pk=pk)
    deezer_ids_actuals = list(artista.deezer_ids.values_list("deezer_id", flat=True))

    if request.method == "POST":
        artista.nom = request.POST.get("nom", artista.nom).strip()
        artista.lastfm_nom = request.POST.get("lastfm_nom", artista.lastfm_nom).strip()
        artista.genere = request.POST.get("genere", "").strip()
        artista.percentatge_femeni = request.POST.get("percentatge_femeni", "").strip()

        # Social links
        for field_name, _ in Artista.SOCIAL_LINK_FIELDS:
            setattr(artista, field_name, request.POST.get(field_name, "").strip())

        artista.aprovat = "aprovat" in request.POST
        artista.save()

        # ── Handle multiple locations ──
        # Each location is submitted as localitat_ids[] (municipi PKs) or
        # localitat_manual[] for free-text non-PPCC locations.
        # Empty entries are skipped; existing ArtistaLocalitat are replaced.
        loc_municipi_ids = request.POST.getlist("loc_municipi_id")
        loc_manuals = request.POST.getlist("loc_manual")

        # Clear existing and rebuild
        artista.localitats.all().delete()
        for i, mid in enumerate(loc_municipi_ids):
            mid = mid.strip()
            manual = loc_manuals[i].strip() if i < len(loc_manuals) else ""
            if mid:
                try:
                    municipi = Municipi.objects.get(pk=int(mid))
                    ArtistaLocalitat.objects.create(artista=artista, municipi=municipi)
                except (ValueError, Municipi.DoesNotExist):
                    messages.warning(request, f"Municipi ID {mid} no trobat.")
            elif manual:
                ArtistaLocalitat.objects.create(
                    artista=artista,
                    municipi=None,
                    localitat_manual=manual,
                )
        # Signal auto-syncs territories.
        # R11: legacy localitat/comarca/provincia gone — nothing to sync back.

        # ── Handle multiple Deezer IDs ──
        new_deezer_ids_raw = request.POST.getlist("deezer_ids")
        new_deezer_ids: list[int] = []
        for raw in new_deezer_ids_raw:
            raw = raw.strip()
            if raw:
                try:
                    new_deezer_ids.append(int(raw))
                except ValueError:
                    pass

        # Sync ArtistaDeezer entries
        existing_dz = set(artista.deezer_ids.values_list("deezer_id", flat=True))
        new_dz_set = set(new_deezer_ids)
        to_remove = existing_dz - new_dz_set
        if to_remove:
            artista.deezer_ids.filter(deezer_id__in=to_remove).delete()
        for i, dz_id in enumerate(new_deezer_ids):
            if dz_id not in existing_dz:
                try:
                    ArtistaDeezer.objects.create(
                        artista=artista,
                        deezer_id=dz_id,
                        principal=(i == 0),
                    )
                except Exception:
                    messages.warning(request, f"Deezer ID {dz_id} ja existeix.")

        # R10: legacy Artista.deezer_id removed; ArtistaDeezer above is the
        # single source of truth now — nothing to sync back.

        log_staff_action(request, "artista_edit", target=artista)
        messages.success(request, f"Artista \u00ab{artista.nom}\u00bb actualitzat.")
        return redirect("staff:artista_editar", pk=artista.pk)

    # GET — build context
    localitats = list(
        artista.localitats.select_related("municipi", "municipi__territori").all()
    )

    return render(
        request,
        "web/staff/artista_edit.html",
        {
            "staff_section": "artistes",
            "artista": artista,
            "localitats": localitats,
            "deezer_ids_actuals": deezer_ids_actuals,
            "social_fields": Artista.SOCIAL_LINK_FIELDS,
            "percentatge_choices": Artista.PERCENTATGE_FEMENI_CHOICES,
        },
    )


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
                count = rebutjar_artista(artista, motiu)
                total_cancons += count
                log_staff_action(
                    request,
                    "artista_marcar_sense_deezer",
                    target=artista,
                    motiu=motiu,
                    cancons_afectades=count,
                )
        recalcular_ml_si_cal()
        messages.success(
            request,
            f"{queryset.count()} artistes marcats sense Deezer, "
            f"{total_cancons} cançons esborrades.",
        )

    elif action == "aprovar":
        ok = 0
        errors = []
        for artista in queryset.prefetch_related("localitats"):
            # R11: only ArtistaLocalitat counts now (legacy fields gone).
            has_loc = artista.localitats.exists()
            if not has_loc:
                errors.append(f"{artista.nom}: falta localitat")
                continue
            artista.aprovat = True
            artista.save(update_fields=["aprovat"])
            log_staff_action(request, "artista_aprovar", target=artista)
            # Territory sync happens via signal if localitats exist
            ok += 1
        if errors:
            messages.error(request, "; ".join(errors))
        if ok:
            messages.success(request, f"{ok} artistes aprovats.")

    elif action == "fusionar":
        if len(ids) < 2:
            messages.error(request, "Cal seleccionar almenys 2 artistes per fusionar.")
            return redirect("staff:artistes")
        _fusionar_artistes(request, ids)

    else:
        messages.error(request, "Acció desconeguda.")

    return redirect("staff:artistes")


def _fusionar_artistes(request: HttpRequest, ids: list[str]) -> None:
    """Merge multiple artists into one (the first by PK keeps all data)."""
    artistes = list(Artista.objects.filter(pk__in=ids).order_by("pk"))
    if len(artistes) < 2:
        messages.error(request, "No s'han trobat prou artistes.")
        return

    target = artistes[0]
    sources = artistes[1:]
    source_names = [a.nom for a in sources]

    with transaction.atomic():
        for source in sources:
            # Move cancons (main artist). Note: .update() skips signals by
            # design, so it can silently create transient D5 violations
            # when a canco had artista=source AND target in artistes_col;
            # we repair those below.
            Canco.objects.filter(artista=source).update(artista=target)

            # Move cancons (collaborator).
            for canco in Canco.objects.filter(artistes_col=source):
                canco.artistes_col.remove(source)
                # D5: target can't be both the main artist and a collab
                # on the same track. Skip the add when that would happen
                # — target is already credited as main, no information
                # lost.
                if canco.artista_id != target.pk:
                    canco.artistes_col.add(target)

            # Repair post-.update() D5 violations: any canco now with
            # artista=target AND target in artistes_col (possible if
            # the source track already listed target as a collaborator
            # before the merge) — remove target from the col side.
            for canco in Canco.objects.filter(
                artista=target, artistes_col=target
            ).distinct():
                canco.artistes_col.remove(target)

            # Move albums
            Album.objects.filter(artista=source).update(artista=target)
            # Move Deezer IDs. Demote merged rows to principal=False so
            # target keeps its existing principal; if target had none we
            # fix that up after the loop ends.
            ArtistaDeezer.objects.filter(artista=source).update(
                artista=target,
                principal=False,
            )
            # Move UserArtista links
            UserArtista.objects.filter(artista=source).update(artista=target)
            # Move HistorialRevisio. The ML classifier's
            # `ratio_rebuig_artista` feature (top-5 importance) keys on
            # `artista_nom` — without this the target artist loses the
            # rejection history of its merged-away duplicate and the RF
            # treats it as a fresh artist.
            HistorialRevisio.objects.filter(artista_nom=source.nom).update(
                artista_nom=target.nom,
            )
            # Move ArtistaLocalitat entries (avoid duplicate municipis)
            target_municipis = set(
                target.localitats.filter(municipi__isnull=False).values_list(
                    "municipi_id", flat=True
                )
            )
            for al in source.localitats.all():
                if al.municipi_id and al.municipi_id in target_municipis:
                    al.delete()  # Duplicate
                else:
                    al.artista = target
                    al.save()
                    if al.municipi_id:
                        target_municipis.add(al.municipi_id)
            # Copy genre if target lacks it
            if not target.genere and source.genere:
                target.genere = source.genere
            # Delete source artist (cascade deletes remaining relations)
            source.delete()

        # Principal invariant: after all sources are merged, target must
        # have exactly one ArtistaDeezer with principal=True if it has any
        # ArtistaDeezer at all. Otherwise `deezer_id_principal` falls back
        # to an arbitrary `.first()` and the staff panel shows a random
        # Deezer link instead of the canonical one.
        target_ads = list(target.deezer_ids.order_by("created_at"))
        if target_ads and not any(ad.principal for ad in target_ads):
            first = target_ads[0]
            first.principal = True
            first.save(update_fields=["principal"])

        target.save()
        # Signal syncs territories from merged localitats

    log_staff_action(
        request,
        "artista_fusionar",
        target=target,
        sources_merged=[{"pk": a.pk, "nom": a.nom} for a in sources],
        target_artista_pk=target.pk,
    )
    messages.success(
        request,
        f"Artistes fusionats: {', '.join(source_names)} \u2192 {target.nom}.",
    )
