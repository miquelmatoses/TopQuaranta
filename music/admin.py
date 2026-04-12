from django.contrib import admin
from django.db import transaction
from django.utils.html import format_html

from .models import Album, Artista, Canco, Territori



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
    exclude = ("territoris",)  # managed via inline instead
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
        total_cancons = 0
        with transaction.atomic():
            for artista in queryset:
                deleted, _ = Canco.objects.filter(
                    artista=artista, verificada=False
                ).delete()
                total_cancons += deleted
            updated = queryset.update(deezer_id=None, deezer_no_trobat=True)
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
        "deezer_player",
        "nom",
        "artista",
        "album_nom",
        "data_llancament",
        "deezer_track_link",
        "deezer_artista_link",
        "isrc",
        "verificada",
        "get_territoris_display",
    )
    list_display_links = ("nom",)
    list_filter = (VerificadaFilter, "data_llancament")
    search_fields = ("nom", "artista__nom")
    ordering = ("-data_llancament",)
    list_per_page = 50
    raw_id_fields = ("artista", "album")
    actions = ["marcar_verificada", "rebutjar_esborrar", "rebutjar_album_sencer"]

    class Media:
        js = ("music/js/deezer_player.js",)

    @admin.display(description="▶")
    def deezer_player(self, obj):
        if not obj.deezer_id:
            return "-"
        return format_html(
            '<a href="#" class="dz-play-btn" data-deezer-id="{}" '
            'style="font-size:18px;text-decoration:none;cursor:pointer">'
            '\u25B6</a>',
            obj.deezer_id,
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

    @admin.display(description="Territoris")
    def get_territoris_display(self, obj):
        return ", ".join(obj.artista.territoris.values_list("codi", flat=True))

    @admin.action(description="Marcar com a verificada")
    def marcar_verificada(self, request, queryset):
        updated = queryset.update(verificada=True)
        self.message_user(request, f"{updated} cançons marcades com a verificades.")

    @admin.action(description="Rebutjar (esborrar)")
    def rebutjar_esborrar(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"{count} cançons esborrades.")

    @admin.action(description="Rebutjar àlbum sencer")
    def rebutjar_album_sencer(self, request, queryset):
        album_ids = set(
            queryset.values_list("album_id", flat=True).distinct()
        )
        with transaction.atomic():
            deleted, _ = Canco.objects.filter(
                album_id__in=album_ids, verificada=False
            ).delete()
        self.message_user(
            request,
            f"{len(album_ids)} àlbums afectats, {deleted} cançons no verificades esborrades.",
        )
