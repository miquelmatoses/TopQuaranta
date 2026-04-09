from django import template
from home.models import MainMenu
from wagtail.models import Site

register = template.Library()


@register.simple_tag(takes_context=True)
def get_main_menu(context):
    """
    Retorna el MainMenu del 'Site' actual, o None si no n'hi ha (fallback).
    """
    request = context.get("request")
    site = Site.find_for_request(request) if request else None
    if not site:
        return None
    try:
        return (
            MainMenu.objects.select_related("site")
            .prefetch_related("items__children")
            .get(site=site)
        )
    except MainMenu.DoesNotExist:
        return None
