from urllib.parse import quote

from django.contrib import admin, messages
from django.db import transaction
from django.template.response import TemplateResponse
from django.utils.html import format_html

from music.constants import MOTIUS_REBUIG
from music.ml import recalcular_ml_si_cal
from music.models import Artista, Canco
from music.services import rebutjar_artista, rebutjar_canco

from .models import RankingProvisional, SenyalDiari


@admin.register(SenyalDiari)
class SenyalDiariAdmin(admin.ModelAdmin):
    list_display = ("canco", "data", "lastfm_playcount", "lastfm_listeners", "error")
    list_filter = ("data", "error")
    search_fields = ("canco__nom", "canco__artista__nom")
    ordering = ("-data", "-lastfm_playcount")
    raw_id_fields = ("canco",)
    list_per_page = 50


class TerritoriProvisionalFilter(admin.SimpleListFilter):
    title = "territori"
    parameter_name = "territori"

    def lookups(self, request, model_admin):
        return [
            ("CAT", "Catalunya"),
            ("VAL", "País Valencià"),
            ("BAL", "Illes Balears"),
            ("CNO", "Catalunya del Nord"),
            ("AND", "Andorra"),
            ("FRA", "Franja de Ponent"),
            ("ALG", "L'Alguer"),
            ("CAR", "El Carxe"),
            ("ALT", "Altres"),
            ("PPCC", "Països Catalans"),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(territori=self.value())
        return queryset.filter(territori="CAT")

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == str(lookup) or (self.value() is None and lookup == "CAT"),
                "query_string": changelist.get_query_string({self.parameter_name: lookup}),
                "display": title,
            }


@admin.register(RankingProvisional)
class RankingProvisionalAdmin(admin.ModelAdmin):
    list_display = (
        "posicio",
        "artista_nom",
        "canco_nom",
        "lastfm_playcount",
        "dies_en_top",
        "territori",
        "deezer_link",
        "lastfm_link",
    )
    list_filter = (TerritoriProvisionalFilter,)
    list_per_page = 40
    ordering = ("posicio",)
    search_fields = ("canco__nom", "canco__artista__nom")
    actions = ["rebutjar_canco_action", "rebutjar_artista_action"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Artista")
    def artista_nom(self, obj):
        return obj.canco.artista.nom

    @admin.display(description="Cançó")
    def canco_nom(self, obj):
        return obj.canco.nom

    @admin.display(description="Deezer")
    def deezer_link(self, obj):
        if not obj.canco.deezer_id:
            return "-"
        url = f"https://www.deezer.com/track/{obj.canco.deezer_id}"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">\U0001f517</a>', url
        )

    @admin.display(description="Last.fm")
    def lastfm_link(self, obj):
        artist = quote(obj.canco.artista.nom, safe="")
        track = quote(obj.canco.nom, safe="")
        url = f"https://www.last.fm/music/{artist}/_/{track}"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">\U0001f3b5</a>', url
        )

    @admin.action(description="Rebutjar cançó (no verificada)")
    def rebutjar_canco_action(self, request, queryset):
        if "confirmar" not in request.POST:
            return TemplateResponse(
                request,
                "admin/music/confirmar_rebuig.html",
                {
                    "action_name": "rebutjar_canco_action",
                    "queryset": queryset,
                    "total_cancons": queryset.count(),
                    "total_albums": 0,
                    "motius": MOTIUS_REBUIG,
                    "cancel_url": request.get_full_path(),
                },
            )

        motiu = request.POST.get("motiu", "")
        if motiu not in {m[0] for m in MOTIUS_REBUIG}:
            self.message_user(
                request, "Has de seleccionar un motiu de rebuig.", level=messages.ERROR
            )
            return

        total = 0
        with transaction.atomic():
            for rp in queryset.select_related("canco__artista", "canco__album"):
                rebutjar_canco(rp.canco, motiu)
                rp.delete()
                total += 1
        recalcular_ml_si_cal()
        self.message_user(request, f"{total} cançons rebutjades (verificada=False).")

    @admin.action(description="Rebutjar totes les cançons de l'artista")
    def rebutjar_artista_action(self, request, queryset):
        if "confirmar" not in request.POST:
            artista_ids = set(
                queryset.values_list("canco__artista_id", flat=True)
            )
            total_cancons = Canco.objects.filter(
                artista_id__in=artista_ids, verificada=False
            ).count()
            return TemplateResponse(
                request,
                "admin/music/confirmar_rebuig.html",
                {
                    "action_name": "rebutjar_artista_action",
                    "queryset": queryset,
                    "total_cancons": total_cancons,
                    "total_albums": 0,
                    "motius": [("artista_incorrecte", "El perfil Deezer no és el nostre artista")],
                    "cancel_url": request.get_full_path(),
                },
            )

        motiu = request.POST.get("motiu", "artista_incorrecte")
        artista_ids = set(
            queryset.values_list("canco__artista_id", flat=True)
        )
        total_cancons = 0
        with transaction.atomic():
            for artista in Artista.objects.filter(pk__in=artista_ids):
                total_cancons += rebutjar_artista(artista, motiu)
            RankingProvisional.objects.filter(
                canco__artista_id__in=artista_ids
            ).delete()

        recalcular_ml_si_cal()
        self.message_user(
            request,
            f"{len(artista_ids)} artistes rebutjats, {total_cancons} cançons esborrades.",
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "canco", "canco__artista"
        )


admin.site.site_header = "TopQuaranta Admin"
