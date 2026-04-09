from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView, TemplateView
from django.views.static import serve as media_serve
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls
from home import views as home_views

urlpatterns = [
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        name="robots_txt",
    ),
    path(
        "favicon.ico",
        RedirectView.as_view(url=static("img/favicon.ico"), permanent=True),
        name="favicon",
    ),
    path("django-admin/", admin.site.urls),
    path("admin/home/geo-choices/", home_views.geo_choices, name="home_geo_choices"),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("accounts/", include("allauth.urls")),
]

# En dev pot afegir rutes (quan DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# **CLAU**: Servir MEDIA també en producció (sempre), ABANS del catch-all de Wagtail
urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$", media_serve, {"document_root": settings.MEDIA_ROOT}
    ),  # ← AFEGIT
]

# Catch-all de Wagtail (ha d’anar l’últim)
urlpatterns += [
    path("", include(wagtail_urls)),
]
