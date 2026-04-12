from django.contrib import admin
from django.db import transaction
from django.template.response import TemplateResponse
from django.utils.html import format_html

from .ml import classificar_i_guardar, recalcular_ml_si_cal
from .models import Album, Artista, Canco, HistorialRevisio, Territori
from .verificacio import crear_historial


MOTIUS_REBUIG_CANCO = [
    ("no_catala", "La cançó no és en català"),
    ("artista_incorrecte", "El perfil Deezer no és el nostre artista"),
    ("album_incorrecte", "L'àlbum sencer no pertany al nostre artista"),
    ("no_musica", "No és música (podcast, audiollibre...)"),
]

MOTIUS_REBUIG_ALBUM = [
    ("artista_incorrecte", "El perfil Deezer no és el nostre artista"),
    ("album_incorrecte", "L'àlbum sencer no pertany al nostre artista"),
]

MOTIUS_REBUIG_ARTISTA = [
    ("artista_incorrecte", "El perfil Deezer no és el nostre artista"),
]


class TerritoriInline(admin.TabularInline):
    model = Artista.territoris.through
    extra = 1
    verbose_name = "Territori"
    verbose_name_plural = "Territoris"


@admin.register(Artista)
class ArtistaAdmin(admin.ModelAdmin):
    list_display = ("nom", "get_territoris_display", "deezer_id", "deezer_no_trobat", "aprovat")
    list_editable = ("deezer_id",)
    list_filter = ("deezer_no_trobat", "aprovat", "territoris")
    search_fields = ("nom",)
    readonly_fields = ("deezer_link",)
    inlines = [TerritoriInline]
    exclude = ("territoris",)
    actions = ["marcar_sense_deezer_i_netejar"]

    @admin.display(description="Territoris")
    def get_territoris_display(self, obj):
        return ", ".join(obj.territoris.values_list("codi", flat=True))

    @admin.display(description="Deezer")
    def deezer_link(self, obj):
        if not obj.deezer_id:
            return "-"
        url = f"https://www.deezer.com/artist/{obj.deezer_id}"
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, url)

    @admin.action(description="Marcar sense Deezer i netejar")
    def marcar_sense_deezer_i_netejar(self, request, queryset):
        if "confirmar" not in request.POST:
            cancons = Canco.objects.filter(
                artista__in=queryset, verificada=False
            )
            return TemplateResponse(
                request,
                "admin/music/confirmar_rebuig.html",
                {
                    "action_name": "marcar_sense_deezer_i_netejar",
                    "queryset": queryset,
                    "total_cancons": cancons.count(),
                    "total_albums": 0,
                    "motius": MOTIUS_REBUIG_ARTISTA,
                    "cancel_url": request.get_full_path(),
                },
            )

        motiu = request.POST.get("motiu", "artista_incorrecte")
        total_cancons = 0
        with transaction.atomic():
            for artista in queryset:
                cancons = Canco.objects.filter(
                    artista=artista, verificada=False
                )
                for canco in cancons.iterator():
                    crear_historial(canco, "rebutjada", motiu)
                deleted = cancons.count()
                cancons.delete()
                total_cancons += deleted
            updated = queryset.update(deezer_id=None, deezer_no_trobat=True)
        recalcular_ml_si_cal()
        self.message_user(
            request,
            f"{updated} artistes marcats sense Deezer, "
            f"{total_cancons} cançons no verificades esborrades.",
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and "deezer_id" in form.changed_data and obj.deezer_id is not None:
            deleted, _ = Canco.objects.filter(
                artista=obj, verificada=False
            ).delete()
            obj.deezer_no_trobat = False
            obj.save(update_fields=["deezer_no_trobat"])
            if deleted:
                self.message_user(
                    request,
                    f"{obj.nom}: deezer_id canviat, {deleted} cançons antigues "
                    f"(no verificades) esborrades, deezer_no_trobat=False.",
                )


class VerificadaFilter(admin.SimpleListFilter):
    title = "verificada"
    parameter_name = "verificada"

    def lookups(self, request, model_admin):
        return [("0", "No verificada"), ("1", "Verificada")]

    def queryset(self, request, queryset):
        if self.value() == "0":
            return queryset.filter(verificada=False)
        if self.value() == "1":
            return queryset.filter(verificada=True)
        return queryset

    def choices(self, changelist):
        yield {
            "selected": self.value() is None,
            "query_string": changelist.get_query_string(remove=[self.parameter_name]),
            "display": "Totes",
        }
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == str(lookup),
                "query_string": changelist.get_query_string({self.parameter_name: lookup}),
                "display": title,
            }

    def value(self):
        val = super().value()
        if val is None:
            return "0"
        return val


@admin.register(Canco)
class CancoAdmin(admin.ModelAdmin):
    list_display = (
        "ml_display",
        "nom",
        "artista",
        "album_nom",
        "data_llancament",
        "deezer_track_link",
        "deezer_artista_link",
        "viasona_link",
        "isrc",
        "verificada",
        "get_territoris_display",
    )
    list_display_links = ("nom",)
    list_filter = (VerificadaFilter, "ml_classe", "data_llancament")
    search_fields = ("nom", "artista__nom")
    ordering = ("ml_classe", "-data_llancament")
    list_per_page = 50
    raw_id_fields = ("artista", "album")
    actions = ["marcar_verificada", "rebutjar_esborrar", "rebutjar_album_sencer"]

    @admin.display(description="ML", ordering="ml_classe")
    def ml_display(self, obj):
        if not obj.ml_classe:
            return "-"
        colors = {"A": "#28a745", "B": "#fd7e14", "C": "#dc3545"}
        color = colors.get(obj.ml_classe, "#666")
        pct = f"{obj.ml_confianca * 100:.0f}" if obj.ml_confianca is not None else "?"
        return format_html(
            '<span style="color:{};font-weight:bold">{} ({}%)</span>',
            color,
            obj.ml_classe,
            pct,
        )

    @admin.display(description="Àlbum")
    def album_nom(self, obj):
        return obj.album.nom

    @admin.display(description="Deezer track")
    def deezer_track_link(self, obj):
        if not obj.deezer_id:
            return "-"
        url = f"https://www.deezer.com/track/{obj.deezer_id}"
        return format_html('<a href="{}" target="_blank" rel="noopener">&#x1F517;</a>', url)

    @admin.display(description="Deezer artista")
    def deezer_artista_link(self, obj):
        if not obj.artista.deezer_id:
            return "-"
        url = f"https://www.deezer.com/artist/{obj.artista.deezer_id}"
        return format_html('<a href="{}" target="_blank" rel="noopener">&#x1F517;</a>', url)

    @admin.display(description="Viasona")
    def viasona_link(self, obj):
        from django.utils.http import urlencode
        q = f"{obj.artista.nom} {obj.nom}"
        url = "https://www.viasona.cat/cerca?" + urlencode({"que": q})
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" '
            'style="font-size:12px">\U0001f50d</a>',
            url,
        )

    @admin.display(description="Territoris")
    def get_territoris_display(self, obj):
        return ", ".join(obj.artista.territoris.values_list("codi", flat=True))

    @admin.action(description="Aprovar cançó")
    def marcar_verificada(self, request, queryset):
        with transaction.atomic():
            for canco in queryset.iterator():
                crear_historial(canco, "aprovada", "ok")
            updated = queryset.update(verificada=True)
        recalcular_ml_si_cal()
        self.message_user(request, f"{updated} cançons marcades com a verificades.")

    @admin.action(description="Rebutjar (esborrar)")
    def rebutjar_esborrar(self, request, queryset):
        if "confirmar" not in request.POST:
            return TemplateResponse(
                request,
                "admin/music/confirmar_rebuig.html",
                {
                    "action_name": "rebutjar_esborrar",
                    "queryset": queryset,
                    "total_cancons": queryset.count(),
                    "total_albums": queryset.values("album_id").distinct().count(),
                    "motius": MOTIUS_REBUIG_CANCO,
                    "cancel_url": request.get_full_path(),
                },
            )

        motiu = request.POST.get("motiu", "no_catala")
        msgs = []
        with transaction.atomic():
            # Record historial for selected cancons
            for canco in queryset.select_related("artista", "album"):
                crear_historial(canco, "rebutjada", motiu)

            if motiu == "artista_incorrecte":
                artista_ids = set(queryset.values_list("artista_id", flat=True))
                for artista in Artista.objects.filter(pk__in=artista_ids):
                    to_delete = Canco.objects.filter(artista=artista, verificada=False)
                    count = to_delete.count()
                    to_delete.delete()
                    artista.deezer_no_trobat = True
                    artista.deezer_id = None
                    artista.save(update_fields=["deezer_no_trobat", "deezer_id"])
                    msgs.append(f"{count} cançons esborrades de l'artista {artista.nom}")
            elif motiu == "album_incorrecte":
                album_ids = set(queryset.values_list("album_id", flat=True))
                for album in Album.objects.filter(pk__in=album_ids):
                    to_delete = Canco.objects.filter(album=album, verificada=False)
                    count = to_delete.count()
                    to_delete.delete()
                    msgs.append(f"{count} cançons esborrades de l'àlbum {album.nom}")
            else:
                count = queryset.count()
                queryset.delete()
                msgs.append(f"{count} cançons esborrades")
        recalcular_ml_si_cal()
        self.message_user(request, f"Motiu: {motiu}. " + "; ".join(msgs) + ".")

    @admin.action(description="Rebutjar àlbum sencer")
    def rebutjar_album_sencer(self, request, queryset):
        album_ids = set(queryset.values_list("album_id", flat=True).distinct())
        cancons = Canco.objects.filter(album_id__in=album_ids, verificada=False)

        if "confirmar" not in request.POST:
            return TemplateResponse(
                request,
                "admin/music/confirmar_rebuig.html",
                {
                    "action_name": "rebutjar_album_sencer",
                    "queryset": queryset,
                    "total_cancons": cancons.count(),
                    "total_albums": len(album_ids),
                    "motius": MOTIUS_REBUIG_ALBUM,
                    "cancel_url": request.get_full_path(),
                },
            )

        motiu = request.POST.get("motiu", "album_incorrecte")
        msgs = []
        with transaction.atomic():
            # Record historial for selected cancons
            for canco in cancons.select_related("artista", "album"):
                crear_historial(canco, "rebutjada", motiu)

            if motiu == "artista_incorrecte":
                artista_ids = set(cancons.values_list("artista_id", flat=True))
                for artista in Artista.objects.filter(pk__in=artista_ids):
                    to_delete = Canco.objects.filter(artista=artista, verificada=False)
                    count = to_delete.count()
                    to_delete.delete()
                    artista.deezer_no_trobat = True
                    artista.deezer_id = None
                    artista.save(update_fields=["deezer_no_trobat", "deezer_id"])
                    msgs.append(f"{count} cançons de l'artista {artista.nom}")
            else:
                deleted, _ = Canco.objects.filter(
                    album_id__in=album_ids, verificada=False
                ).delete()
                msgs.append(f"{deleted} cançons de {len(album_ids)} àlbums")
        recalcular_ml_si_cal()
        self.message_user(request, f"Motiu: {motiu}. Esborrades: " + "; ".join(msgs) + ".")


@admin.register(HistorialRevisio)
class HistorialRevisioAdmin(admin.ModelAdmin):
    list_display = ("canco_nom", "artista_nom", "decisio", "motiu", "created_at")
    list_filter = ("decisio", "motiu")
    search_fields = ("canco_nom", "artista_nom")
    readonly_fields = [f.name for f in HistorialRevisio._meta.get_fields()]
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
