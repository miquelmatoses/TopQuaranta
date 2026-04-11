from django.contrib import admin
from django.utils.html import format_html

from .models import IngestaDiari


@admin.register(IngestaDiari)
class IngestaDiariAdmin(admin.ModelAdmin):
    list_display = ("canco", "data", "lastfm_playcount", "lastfm_listeners", "error")
    list_filter = ("data", "error")
    search_fields = ("canco__nom", "canco__artista__nom")
    ordering = ("-data", "-lastfm_playcount")
    raw_id_fields = ("canco",)
    list_per_page = 50


# Add ranking provisional link to admin index
admin.site.index_template = None  # use default
admin.site.site_header = "TopQuaranta Admin"
admin.site.index_title = format_html(
    'Administració &nbsp;|&nbsp; <a href="ranking-provisional/">Ranking Provisional</a>'
)
