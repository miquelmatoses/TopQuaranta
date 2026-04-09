from allauth.account.signals import user_signed_up
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.dispatch import receiver
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet
from .models import CmsArtista

class ArtistaViewSet(SnippetViewSet):
    model = CmsArtista
    add_to_admin_menu = True
    menu_label = "Artistes"
    menu_icon = "user"
    list_display = ("nom", "territori", "comarca", "localitat", "popularitat")
    search_fields = ("nom", "territori", "comarca", "localitat")
    list_per_page = 50

# Registre del snippet via funció (recomanat en 6.x)
register_snippet(ArtistaViewSet)

@receiver(user_signed_up)
def _tq_add_user_to_usuaris(request, user, **kwargs):
    """
    Quan un usuari es registra (signup normal o social), afegir-lo al grup "Usuaris".
    Ens assegurem també que el grup tinga el permís 'wagtailadmin.access_admin'
    per poder accedir al panell d'admin de Wagtail (sense cap altre permís).
    """
    group, _ = Group.objects.get_or_create(name="Usuaris")

    # Garantir el permís d'accés a Wagtail admin en el grup
    try:
        ct = ContentType.objects.get(app_label="wagtailadmin", model="admin")
        perm = Permission.objects.get(content_type=ct, codename="access_admin")
    except (ContentType.DoesNotExist, Permission.DoesNotExist):
        # En instal·lacions Wagtail modernes sempre existix; si no, no fem res extra
        perm = None

    if perm and perm not in group.permissions.all():
        group.permissions.add(perm)

    # Afegir l'usuari al grup "Usuaris"
    user.groups.add(group)
