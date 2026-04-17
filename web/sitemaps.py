"""F3: sitemap.xml generation for indexing by search engines.

Four entries: static pages + every approved artist + every album with a
verified track + one entry per ranking territory. Changefreq=weekly for
pages driven by the weekly ranking; monthly for artist/album profiles
that mostly change when new tracks get verified.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from music.constants import TERRITORIS_VALIDS
from music.models import Album, Artista


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9
    i18n = False
    protocol = "https"

    def items(self):
        return [
            "web:homepage",
            "web:ranking",
            "web:artistes",
            "web:mapa",
            "web:com_funciona",
            "web:com_funciona_historial",
        ]

    def location(self, item):
        return reverse(item)


class RankingByTerritoriSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    i18n = False
    protocol = "https"

    def items(self):
        return [t for t in TERRITORIS_VALIDS]

    def location(self, territori):
        return f"{reverse('web:ranking')}?t={territori.lower()}"


class ArtistSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7
    i18n = False
    protocol = "https"

    def items(self):
        return Artista.objects.filter(aprovat=True).only("slug")

    def location(self, obj):
        return reverse("web:artista", kwargs={"slug": obj.slug})


class AlbumSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5
    i18n = False
    protocol = "https"

    def items(self):
        # Only albums with at least one verified track are publicly linked.
        return Album.objects.filter(cancons__verificada=True).distinct().only("slug")

    def location(self, obj):
        return reverse("web:album", kwargs={"slug": obj.slug})


sitemaps = {
    "static": StaticSitemap,
    "rankings": RankingByTerritoriSitemap,
    "artistes": ArtistSitemap,
    "albums": AlbumSitemap,
}
