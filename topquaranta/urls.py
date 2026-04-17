from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import TemplateView

from web.sitemaps import sitemaps

urlpatterns = [
    path("api/v1/", include("web.api.urls")),
    path("compte/", include("comptes.urls")),
    path("staff/", include("web.views.staff.urls")),
    # F3: SEO surface — sitemap.xml + robots.txt at the root of the site.
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="web/robots.txt",
            content_type="text/plain",
        ),
    ),
    path("", include("web.urls")),
]

# S13: custom branded error pages (only used when DEBUG=False).
handler404 = "web.views.handler_404"
handler500 = "web.views.handler_500"
handler403 = "web.views.handler_403"
