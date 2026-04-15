"""Template tags for staff views."""

from django import template
from django.utils.html import format_html, mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def query_string(context, **kwargs):
    """Build query string preserving current GET params, overriding with kwargs."""
    request = context["request"]
    params = request.GET.copy()
    for key, value in kwargs.items():
        params[key] = value
    return mark_safe(params.urlencode())


@register.filter
def lastfm_encode(value):
    """Encode a string for Last.fm URL path segments (spaces → +)."""
    from urllib.parse import quote
    return quote(str(value), safe="")


@register.simple_tag
def ml_badge(canco):
    """Render ML classification badge with color."""
    if not canco.ml_classe:
        return format_html('<span class="staff-ml staff-ml--none">-</span>')
    css = {"A": "good", "B": "caution", "C": "bad"}.get(canco.ml_classe, "none")
    pct = f"{canco.ml_confianca * 100:.0f}" if canco.ml_confianca is not None else "?"
    return format_html(
        '<span class="staff-ml staff-ml--{}">{} ({}%)</span>',
        css, canco.ml_classe, pct,
    )


@register.simple_tag
def territori_list(artista):
    """Render comma-separated territory codes."""
    codes = list(artista.territoris.values_list("codi", flat=True))
    return ", ".join(codes) if codes else "-"
