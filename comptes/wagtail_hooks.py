from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import UserArtista


class UserArtistaViewSet(SnippetViewSet):
    model = UserArtista
    icon = "user"
    menu_label = "Verificació artistes"
    menu_order = 300
    list_display = ("usuari", "artista", "verificat", "created_at")
    list_filter = ("verificat",)
    search_fields = ("usuari__email", "artista__nom")


register_snippet(UserArtistaViewSet)
