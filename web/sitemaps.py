"""SEO sitemap for TopQuaranta.

Django still serves `/sitemap.xml` (via Caddy passthrough) so search
engines can index the public surface even though the UI now lives in
the React SPA. Paths are hardcoded here because the SPA owns the
client-side routes — Django has no URL patterns for them anymore.

If we ever want per-artist/album/canço sitemaps (one row per slug),
extend this with extra Sitemap subclasses that iterate the relevant
querysets.
"""

from django.contrib.sitemaps import Sitemap


class StaticSitemap(Sitemap):
    """Top-level entry points exposed by the SPA."""

    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    # Hardcoded paths served by the React SPA at the Caddy level. The
    # location() method below returns these literally; `reverse()` is
    # no longer applicable since Django has no URL patterns for `/`,
    # `/top`, etc.
    URLS = [
        ("/", 1.0, "daily"),
        ("/top", 1.0, "daily"),
        ("/artistes", 0.8, "weekly"),
        ("/mapa", 0.6, "weekly"),
        ("/com-funciona", 0.5, "monthly"),
    ]

    def items(self):
        return self.URLS

    def location(self, obj):
        return obj[0]

    def priority(self, obj):
        return obj[1]

    def changefreq(self, obj):
        return obj[2]


sitemaps = {
    "static": StaticSitemap,
}
