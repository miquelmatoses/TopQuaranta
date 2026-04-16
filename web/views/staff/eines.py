"""Staff views for remaining tools: historial, senyal, UserArtista, propostes, configuracio."""

import json

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from comptes.models import PropostaArtista, UserArtista
from music.audit import log_staff_action
from music.models import Artista, ArtistaDeezer, ArtistaLocalitat, HistorialRevisio, Municipi, StaffAuditLog, Territori
from ranking.models import ConfiguracioGlobal, SenyalDiari

from . import apply_ordering, paginate, staff_required


# ── HistorialRevisio ──

HISTORIAL_ORDER_FIELDS = {
    "canco": "canco_nom",
    "artista": "artista_nom",
    "decisio": "decisio",
    "motiu": "motiu",
    "data": "created_at",
}


@staff_required
def historial(request: HttpRequest) -> HttpResponse:
    """Read-only log of approval/rejection decisions."""
    qs = HistorialRevisio.objects.all()

    decisio = request.GET.get("decisio", "")
    if decisio in ("aprovada", "rebutjada"):
        qs = qs.filter(decisio=decisio)

    motiu = request.GET.get("motiu", "")
    if motiu:
        qs = qs.filter(motiu=motiu)

    cerca = request.GET.get("q", "").strip()
    if cerca:
        qs = qs.filter(
            Q(canco_nom__icontains=cerca) | Q(artista_nom__icontains=cerca)
        )

    qs, current_order, current_dir = apply_ordering(
        request, qs, HISTORIAL_ORDER_FIELDS, default="-created_at"
    )
    page = paginate(request, qs)

    return render(request, "web/staff/historial.html", {
        "staff_section": "historial",
        "page": page,
        "decisio": decisio,
        "motiu": motiu,
        "cerca": cerca,
        "current_order": current_order,
        "current_dir": current_dir,
    })


# ── SenyalDiari ──

SENYAL_ORDER_FIELDS = {
    "canco": "canco__nom",
    "artista": "canco__artista__nom",
    "data": "data",
    "playcount": "lastfm_playcount",
    "listeners": "lastfm_listeners",
    "score": "score_entrada",
}


@staff_required
def senyal(request: HttpRequest) -> HttpResponse:
    """Daily Last.fm signal data."""
    qs = SenyalDiari.objects.select_related("canco", "canco__artista")

    data_filtre = request.GET.get("data", "")
    if data_filtre:
        qs = qs.filter(data=data_filtre)

    errors_only = request.GET.get("errors", "")
    if errors_only == "1":
        qs = qs.filter(error=True)

    cerca = request.GET.get("q", "").strip()
    if cerca:
        qs = qs.filter(
            Q(canco__nom__icontains=cerca) | Q(canco__artista__nom__icontains=cerca)
        )

    qs, current_order, current_dir = apply_ordering(
        request, qs, SENYAL_ORDER_FIELDS, default="-data"
    )
    page = paginate(request, qs)

    return render(request, "web/staff/senyal.html", {
        "staff_section": "senyal",
        "page": page,
        "data_filtre": data_filtre,
        "errors_only": errors_only,
        "cerca": cerca,
        "current_order": current_order,
        "current_dir": current_dir,
    })


# ── UserArtista (verification requests) ──

VERIFICACIO_ORDER_FIELDS = {
    "usuari": "usuari__email",
    "artista": "artista__nom",
    "data": "created_at",
    "verificat": "verificat",
}


@staff_required
def verificacio_artistes(request: HttpRequest) -> HttpResponse:
    """Manage artist verification requests."""
    qs = UserArtista.objects.select_related("usuari", "artista")

    verificat = request.GET.get("verificat", "")
    if verificat == "0":
        qs = qs.filter(verificat=False)
    elif verificat == "1":
        qs = qs.filter(verificat=True)

    qs, current_order, current_dir = apply_ordering(
        request, qs, VERIFICACIO_ORDER_FIELDS, default="-created_at"
    )
    page = paginate(request, qs, per_page=25)

    return render(request, "web/staff/verificacio.html", {
        "staff_section": "verificacio",
        "page": page,
        "verificat": verificat,
        "current_order": current_order,
        "current_dir": current_dir,
    })


@staff_required
def verificacio_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """Toggle verification status for a UserArtista."""
    if request.method != "POST":
        return redirect("staff:verificacio_artistes")

    try:
        ua = UserArtista.objects.get(pk=pk)
    except UserArtista.DoesNotExist:
        messages.error(request, "Sol\u00b7licitud no trobada.")
        return redirect("staff:verificacio_artistes")

    ua.verificat = not ua.verificat
    ua.estat = "aprovat" if ua.verificat else "pendent"
    ua.save(update_fields=["verificat", "estat"])
    estat_text = "aprovat" if ua.verificat else "desaprovat"
    log_staff_action(
        request,
        "sollicitud_aprovar" if ua.verificat else "sollicitud_rebutjar",
        target=ua,
        nou_estat=ua.estat,
        artista=ua.artista.nom,
        usuari=ua.usuari.email,
    )
    messages.success(request, f"{ua.artista.nom} ({ua.usuari.email}): {estat_text}.")
    return redirect("staff:verificacio_artistes")


@staff_required
def verificacio_rebutjar(request: HttpRequest, pk: int) -> HttpResponse:
    """Reject a UserArtista request (marks as rejected, keeps record)."""
    if request.method != "POST":
        return redirect("staff:verificacio_artistes")

    try:
        ua = UserArtista.objects.select_related("usuari", "artista").get(pk=pk)
    except UserArtista.DoesNotExist:
        messages.error(request, "Sol\u00b7licitud no trobada.")
        return redirect("staff:verificacio_artistes")

    ua.estat = "rebutjat"
    ua.save(update_fields=["estat"])
    log_staff_action(
        request, "sollicitud_rebutjar", target=ua,
        artista=ua.artista.nom, usuari=ua.usuari.email,
    )
    info = f"{ua.artista.nom} ({ua.usuari.email})"
    messages.success(request, f"Sol\u00b7licitud rebutjada: {info}.")
    return redirect("staff:verificacio_artistes")


# ── PropostaArtista (new artist proposals from users) ──

PROPOSTES_ORDER_FIELDS = {
    "nom": "nom",
    "usuari": "usuari__email",
    "data": "created_at",
    "estat": "estat",
}


@staff_required
def propostes_artistes(request: HttpRequest) -> HttpResponse:
    """Manage new artist proposals from users."""
    qs = PropostaArtista.objects.select_related("usuari", "artista_creat")

    estat = request.GET.get("estat", "")
    if estat in ("pendent", "aprovat", "rebutjat"):
        qs = qs.filter(estat=estat)

    qs, current_order, current_dir = apply_ordering(
        request, qs, PROPOSTES_ORDER_FIELDS, default="-created_at"
    )
    page = paginate(request, qs, per_page=25)

    return render(request, "web/staff/propostes.html", {
        "staff_section": "propostes",
        "page": page,
        "estat": estat,
        "current_order": current_order,
        "current_dir": current_dir,
    })


@staff_required
def proposta_detall(request: HttpRequest, pk: int) -> HttpResponse:
    """View details of a new artist proposal."""
    try:
        proposta = PropostaArtista.objects.select_related("usuari", "artista_creat").get(pk=pk)
    except PropostaArtista.DoesNotExist:
        messages.error(request, "Proposta no trobada.")
        return redirect("staff:propostes_artistes")

    # Parse locations
    localitzacions = []
    if proposta.localitzacions_json:
        try:
            locs = json.loads(proposta.localitzacions_json)
            for loc in locs:
                if "municipi_id" in loc:
                    try:
                        m = Municipi.objects.get(pk=loc["municipi_id"])
                        localitzacions.append(f"{m.nom}, {m.comarca} ({m.territori_id})")
                    except Municipi.DoesNotExist:
                        localitzacions.append(f"Municipi ID {loc['municipi_id']} (no trobat)")
                elif "manual" in loc:
                    localitzacions.append(f"{loc['manual']} (manual)")
        except (json.JSONDecodeError, TypeError):
            pass

    # Parse Deezer IDs
    deezer_ids = proposta.get_deezer_id_list()

    # Social links
    social_links = []
    for field_name, label in Artista.SOCIAL_LINK_FIELDS:
        val = getattr(proposta, field_name, "")
        if val:
            social_links.append({"label": label, "url": val})

    return render(request, "web/staff/proposta_detall.html", {
        "staff_section": "propostes",
        "proposta": proposta,
        "localitzacions": localitzacions,
        "deezer_ids": deezer_ids,
        "social_links": social_links,
    })


@staff_required
def proposta_aprovar(request: HttpRequest, pk: int) -> HttpResponse:
    """Approve a proposal: create the artist and link it."""
    if request.method != "POST":
        return redirect("staff:propostes_artistes")

    try:
        proposta = PropostaArtista.objects.select_related("usuari").get(pk=pk)
    except PropostaArtista.DoesNotExist:
        messages.error(request, "Proposta no trobada.")
        return redirect("staff:propostes_artistes")

    if proposta.estat != PropostaArtista.ESTAT_PENDENT:
        messages.info(request, "Aquesta proposta ja ha estat processada.")
        return redirect("staff:propostes_artistes")

    with transaction.atomic():
        # Create the artist
        artista = Artista.objects.create(
            nom=proposta.nom,
            lastfm_nom=proposta.nom,
            aprovat=True,
            auto_descobert=False,
            font_descoberta="proposta_usuari",
        )

        # Copy social links
        for field_name, _ in Artista.SOCIAL_LINK_FIELDS:
            val = getattr(proposta, field_name, "")
            if val:
                setattr(artista, field_name, val)
        artista.save()

        # Create Deezer IDs
        deezer_ids = proposta.get_deezer_id_list()
        for i, dz_id in enumerate(deezer_ids):
            try:
                ArtistaDeezer.objects.create(
                    artista=artista, deezer_id=dz_id, principal=(i == 0),
                )
            except Exception:
                pass
        if deezer_ids:
            artista.deezer_id = deezer_ids[0]
            artista.save(update_fields=["deezer_id"])

        # Create locations
        if proposta.localitzacions_json:
            try:
                locs = json.loads(proposta.localitzacions_json)
                first_loc = None
                for loc in locs:
                    if "municipi_id" in loc:
                        try:
                            m = Municipi.objects.get(pk=loc["municipi_id"])
                            al = ArtistaLocalitat.objects.create(artista=artista, municipi=m)
                            if not first_loc:
                                first_loc = al
                        except Municipi.DoesNotExist:
                            pass
                    elif "manual" in loc:
                        al = ArtistaLocalitat.objects.create(
                            artista=artista, municipi=None,
                            localitat_manual=loc["manual"],
                        )
                        if not first_loc:
                            first_loc = al

                # Update legacy fields
                if first_loc and first_loc.municipi:
                    artista.localitat = first_loc.municipi.nom
                    artista.comarca = first_loc.municipi.comarca
                elif first_loc:
                    artista.localitat = first_loc.localitat_manual
                    artista.comarca = "Altres"
                artista.save(update_fields=["localitat", "comarca"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Update proposal
        proposta.estat = PropostaArtista.ESTAT_APROVAT
        proposta.artista_creat = artista
        proposta.save(update_fields=["estat", "artista_creat"])

    log_staff_action(
        request, "proposta_aprovar", target=proposta,
        artista_creat_id=artista.pk,
        artista_nom=artista.nom,
        deezer_ids=deezer_ids,
        usuari_proposant=proposta.usuari.email,
    )
    messages.success(request, f"Artista \u00ab{artista.nom}\u00bb creat des de la proposta.")
    return redirect("staff:propostes_artistes")


@staff_required
def proposta_rebutjar(request: HttpRequest, pk: int) -> HttpResponse:
    """Reject a proposal."""
    if request.method != "POST":
        return redirect("staff:propostes_artistes")

    try:
        proposta = PropostaArtista.objects.get(pk=pk)
    except PropostaArtista.DoesNotExist:
        messages.error(request, "Proposta no trobada.")
        return redirect("staff:propostes_artistes")

    proposta.estat = PropostaArtista.ESTAT_REBUTJAT
    proposta.save(update_fields=["estat"])
    log_staff_action(
        request, "proposta_rebutjar", target=proposta,
        artista_nom=proposta.nom,
        usuari_proposant=proposta.usuari.email,
    )
    messages.success(request, f"Proposta \u00ab{proposta.nom}\u00bb rebutjada.")
    return redirect("staff:propostes_artistes")


# ── ConfiguracioGlobal ──


@staff_required
def configuracio(request: HttpRequest) -> HttpResponse:
    """Edit ranking algorithm coefficients."""
    config = ConfiguracioGlobal.load()

    if request.method == "POST":
        fields = [f for f in ConfiguracioGlobal._meta.get_fields()
                  if hasattr(f, "attname") and f.attname != "id"]

        # Snapshot before values so we can record a field-level diff.
        before = {f.attname: getattr(config, f.attname) for f in fields}

        for field in fields:
            val = request.POST.get(field.attname, "").strip()
            if val:
                try:
                    setattr(config, field.attname, type(getattr(config, field.attname))(val))
                except (ValueError, TypeError):
                    pass
        # R8: full_clean() in ConfiguracioGlobal.save() will raise
        # ValidationError if any coefficient is out of range. Surface the
        # error to the staff user instead of 500-ing.
        from django.core.exceptions import ValidationError
        try:
            config.save()
        except ValidationError as exc:
            for field_name, msgs in exc.message_dict.items():
                for msg in msgs:
                    messages.error(request, f"{field_name}: {msg}")
            return redirect("staff:configuracio")

        # Build the diff (only fields that actually changed).
        after = {f.attname: getattr(config, f.attname) for f in fields}
        diff = {
            name: {"before": str(before[name]), "after": str(after[name])}
            for name in before if str(before[name]) != str(after[name])
        }
        if diff:
            log_staff_action(
                request, "config_update", target=config,
                changed_fields=list(diff.keys()),
                diff=diff,
            )
        messages.success(request, "Configuració actualitzada.")
        return redirect("staff:configuracio")

    fields_data = []
    for field in ConfiguracioGlobal._meta.get_fields():
        if hasattr(field, "attname") and field.attname != "id":
            fields_data.append({
                "name": field.attname,
                "label": field.attname.replace("_", " ").title(),
                "value": getattr(config, field.attname),
                "help": getattr(field, "help_text", ""),
            })

    return render(request, "web/staff/configuracio.html", {
        "staff_section": "configuracio",
        "config": config,
        "fields": fields_data,
    })


# ── StaffAuditLog (read-only view) ──


@staff_required
def auditlog(request: HttpRequest) -> HttpResponse:
    """Read-only view of the staff action log (R9)."""
    qs = StaffAuditLog.objects.select_related("actor").order_by("-created_at")

    action = request.GET.get("action", "")
    if action:
        qs = qs.filter(action=action)

    actor_email = request.GET.get("actor", "").strip()
    if actor_email:
        qs = qs.filter(actor__email__icontains=actor_email)

    cerca = request.GET.get("q", "").strip()
    if cerca:
        qs = qs.filter(target_label__icontains=cerca)

    page = paginate(request, qs, per_page=50)

    return render(request, "web/staff/auditlog.html", {
        "staff_section": "auditlog",
        "page": page,
        "action": action,
        "actor_email": actor_email,
        "cerca": cerca,
        "action_choices": StaffAuditLog.ACTION_CHOICES,
    })
