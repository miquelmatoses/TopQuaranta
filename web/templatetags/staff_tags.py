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
    from urllib.parse import quote_plus

    return quote_plus(str(value))


@register.simple_tag
def ml_badge(canco):
    """Render ML classification badge with color."""
    if not canco.ml_classe:
        return format_html('<span class="staff-ml staff-ml--none">-</span>')
    css = {"A": "good", "B": "caution", "C": "bad"}.get(canco.ml_classe, "none")
    pct = f"{canco.ml_confianca * 100:.0f}" if canco.ml_confianca is not None else "?"
    return format_html(
        '<span class="staff-ml staff-ml--{}">{} ({}%)</span>',
        css,
        canco.ml_classe,
        pct,
    )


@register.simple_tag
def silero_badge(canco):
    """Render a compact Silero VAD badge.

    - "—" if the track has not been analysed yet.
    - "🎵 N%" if voice fraction < 0.10 (likely instrumental).
    - "🎤 N%" if voice fraction ≥ 0.10 (some voice, possibly vocal).
    Color: red for likely-instrumental, green for clearly-vocal,
    yellow for the uncertain middle band.
    """
    if canco.silero_processat_at is None:
        return format_html('<span class="staff-ml staff-ml--none">—</span>')
    vf = canco.silero_veu_probabilitat
    if vf is None:
        return format_html('<span class="staff-ml staff-ml--none">⚠</span>')
    pct = int(round(vf * 100))
    if vf < 0.10:
        css, icon = "bad", "🎵"  # likely instrumental
    elif vf < 0.40:
        css, icon = "caution", "🎤"  # voice but low coverage
    else:
        css, icon = "good", "🎤"  # clearly vocal
    return format_html(
        '<span class="staff-ml staff-ml--{}" title="Silero voice fraction">'
        "{} {}%</span>",
        css,
        icon,
        pct,
    )


@register.simple_tag
def territori_list(artista):
    """Render comma-separated territory codes."""
    codes = list(artista.territoris.values_list("codi", flat=True))
    return ", ".join(codes) if codes else "-"


@register.filter
def getattr_filter(obj, attr):
    """Get an attribute from an object by name."""
    return getattr(obj, attr, "")


# Register with the common name 'getattr' for template usage
register.filter("getattr", getattr_filter)


@register.simple_tag(takes_context=True)
def sort_header(context, field, label):
    """Render a sortable column header link.

    If the column is currently sorted, show direction arrow and link to toggle.
    Preserves existing GET params (filters, search, etc.).
    """
    request = context["request"]
    current_order = context.get("current_order", "")
    current_dir = context.get("current_dir", "asc")

    params = request.GET.copy()
    params["order"] = field

    if current_order == field:
        # Toggle direction
        new_dir = "desc" if current_dir == "asc" else "asc"
        arrow = " ↑" if current_dir == "asc" else " ↓"
    else:
        new_dir = "asc"
        arrow = ""

    params["dir"] = new_dir
    # Remove page when changing sort
    params.pop("page", None)
    url = "?" + params.urlencode()

    return format_html(
        '<a href="{}" class="staff-sort-link{}">{}{}</a>',
        url,
        " is-active" if current_order == field else "",
        label,
        arrow,
    )
