from django.contrib import admin

from .models import UserArtista


@admin.register(UserArtista)
class UserArtistaAdmin(admin.ModelAdmin):
    list_display = ("usuari", "artista", "verificat", "created_at")
    list_filter = ("verificat",)
    list_editable = ("verificat",)
    search_fields = ("usuari__email", "artista__nom")
    raw_id_fields = ("usuari", "artista")
    readonly_fields = ("created_at",)
