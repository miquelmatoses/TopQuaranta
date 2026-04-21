"""Django request handlers that still run after Sprint 4's React flip.

The public website + staff panel moved to `web-react/` (React SPA)
in April 2026; every former template view in this module (homepage,
ranking, artistes, perfil_artista, perfil_album, mapa, com_funciona,
com_funciona_historial) was removed along with `web/urls.py`. What
remains here is Django's trio of error-page handlers referenced from
`topquaranta/urls.py` via `handler404/500/403`.

These fire only on Django-side paths (`/api/*`, `/compte/2fa/*`,
`/compte/activar/*`, `/compte/registre/`, `/compte/login/`,
`/compte/logout/`, `/sitemap.xml`, `/robots.txt`) — everything else
hits the SPA at Caddy level and React renders its own 404 client-side.

The templates live at `web/templates/web/{403,404,500}.html` and are
kept intentionally minimal after the React flip.
"""

from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseServerError,
)
from django.template import loader


def handler_404(request: HttpRequest, exception=None) -> HttpResponse:
    template = loader.get_template("web/404.html")
    return HttpResponseNotFound(template.render({"request": request}, request))


def handler_500(request: HttpRequest) -> HttpResponse:
    template = loader.get_template("web/500.html")
    return HttpResponseServerError(template.render({"request": request}, request))


def handler_403(request: HttpRequest, exception=None) -> HttpResponse:
    template = loader.get_template("web/403.html")
    return HttpResponseForbidden(template.render({"request": request}, request))
