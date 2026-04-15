"""Staff views for remaining tools: historial, senyal, UserArtista, configuració."""

from django.contrib import messages
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from comptes.models import UserArtista
from music.models import HistorialRevisio
from ranking.models import ConfiguracioGlobal, SenyalDiari

from . import paginate, staff_required


# ── HistorialRevisio ──


@staff_required
def historial(request: HttpRequest) -> HttpResponse:
    """Read-only log of approval/rejection decisions."""
    qs = HistorialRevisio.objects.all().order_by("-created_at")

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

    page = paginate(request, qs)

    return render(request, "web/staff/historial.html", {
        "staff_section": "historial",
        "page": page,
        "decisio": decisio,
        "motiu": motiu,
        "cerca": cerca,
    })


# ── SenyalDiari ──


@staff_required
def senyal(request: HttpRequest) -> HttpResponse:
    """Daily Last.fm signal data."""
    qs = SenyalDiari.objects.select_related("canco", "canco__artista").order_by(
        "-data", "-lastfm_playcount"
    )

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

    page = paginate(request, qs)

    return render(request, "web/staff/senyal.html", {
        "staff_section": "senyal",
        "page": page,
        "data_filtre": data_filtre,
        "errors_only": errors_only,
        "cerca": cerca,
    })


# ── UserArtista (verification requests) ──


@staff_required
def verificacio_artistes(request: HttpRequest) -> HttpResponse:
    """Manage artist verification requests."""
    qs = UserArtista.objects.select_related("usuari", "artista").order_by("-created_at")

    verificat = request.GET.get("verificat", "")
    if verificat == "0":
        qs = qs.filter(verificat=False)
    elif verificat == "1":
        qs = qs.filter(verificat=True)

    page = paginate(request, qs, per_page=25)

    return render(request, "web/staff/verificacio.html", {
        "staff_section": "verificacio",
        "page": page,
        "verificat": verificat,
    })


@staff_required
def verificacio_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """Toggle verification status for a UserArtista."""
    if request.method != "POST":
        return redirect("staff:verificacio_artistes")

    try:
        ua = UserArtista.objects.get(pk=pk)
    except UserArtista.DoesNotExist:
        messages.error(request, "Sol·licitud no trobada.")
        return redirect("staff:verificacio_artistes")

    ua.verificat = not ua.verificat
    ua.save(update_fields=["verificat"])
    estat = "verificat" if ua.verificat else "desverificat"
    messages.success(request, f"{ua.artista.nom} ({ua.usuari.email}): {estat}.")
    return redirect("staff:verificacio_artistes")


# ── ConfiguracioGlobal ──


@staff_required
def configuracio(request: HttpRequest) -> HttpResponse:
    """Edit ranking algorithm coefficients."""
    config = ConfiguracioGlobal.load()

    if request.method == "POST":
        fields = [f for f in ConfiguracioGlobal._meta.get_fields()
                  if hasattr(f, "attname") and f.attname != "id"]
        for field in fields:
            val = request.POST.get(field.attname, "").strip()
            if val:
                try:
                    setattr(config, field.attname, type(getattr(config, field.attname))(val))
                except (ValueError, TypeError):
                    pass
        config.save()
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
