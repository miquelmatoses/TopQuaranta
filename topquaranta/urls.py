from django.contrib import admin
from django.urls import include, path

from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from ranking.views import ranking_provisional

urlpatterns = [
    path("django-admin/ranking-provisional/", ranking_provisional, name="ranking-provisional"),
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("api/v1/", include("web.api.urls")),
    path("compte/", include("comptes.urls")),
    path("staff/", include("web.views.staff.urls")),
    path("", include("web.urls")),
    path("", include(wagtail_urls)),
]
