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
def deezer_artist_url(deezer_id):
    """Build a canonical Deezer artist URL.

    Five staff templates had `https://www.deezer.com/artist/{{ dz }}`
    hardcoded; this tag keeps the base URL in one place so a future
    Deezer path migration doesn't require a grep-and-replace. Empty
    input returns an empty string — `{% if dz %}` guards remain the
    caller's responsibility.
    """
    if not deezer_id:
        return ""
    return format_html("https://www.deezer.com/artist/{}", deezer_id)


@register.simple_tag
def whisper_badge(canco):
    """Render a compact Whisper LID badge.

    - "—" if the track hasn't been analysed yet.
    - "CA N%" in green if Whisper agrees with our catalogue (ca).
    - "XX N%" in orange if Whisper predicts a non-Catalan language —
      signal to staff that the verification may be wrong (as Whisper
      surfaced 2 real catalogue errors on the 48-clip eval set).
    Precision on the eval set is 100 %: if Whisper says `ca`, the
    track was really Catalan in every case measured.
    """
    if canco.whisper_processat_at is None:
        return format_html('<span class="staff-ml staff-ml--none">—</span>')
    lang = canco.whisper_lang or "?"
    prob = canco.whisper_p
    pct = f"{int(round(prob * 100))}" if prob is not None else "?"
    css = "good" if lang == "ca" else "caution"
    return format_html(
        '<span class="staff-ml staff-ml--{}" title="Whisper LID">{} {}%</span>',
        css,
        lang.upper(),
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
