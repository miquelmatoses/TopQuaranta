from django.contrib import admin
from django.utils.html import format_html

from .models import Artista, Canco, Territori



class TerritoriInline(admin.TabularInline):
    model = Artista.territoris.through
    extra = 1
    verbose_name = "Territori"
    verbose_name_plural = "Territoris"


@admin.register(Artista)
class ArtistaAdmin(admin.ModelAdmin):
    list_display = ("nom", "get_territoris_display", "deezer_id", "deezer_no_trobat", "aprovat")
    list_filter = ("deezer_no_trobat", "aprovat", "territoris")
    search_fields = ("nom",)
    inlines = [TerritoriInline]
    exclude = ("territoris",)  # managed via inline instead

    @admin.display(description="Territoris")
    def get_territoris_display(self, obj):
        return ", ".join(obj.territoris.values_list("codi", flat=True))


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
        "isrc",
        "verificada",
        "get_territoris_display",
    )
    list_filter = (VerificadaFilter, "data_llancament")
    search_fields = ("nom", "artista__nom")
    ordering = ("-data_llancament",)
    list_per_page = 50
    raw_id_fields = ("artista", "album")
    actions = ["marcar_verificada", "rebutjar_esborrar"]

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
