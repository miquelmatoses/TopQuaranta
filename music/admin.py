from django.contrib import admin

from .models import Artista, Territori


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
