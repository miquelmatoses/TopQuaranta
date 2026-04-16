from django.urls import include, path

urlpatterns = [
    path("api/v1/", include("web.api.urls")),
    path("compte/", include("comptes.urls")),
    path("staff/", include("web.views.staff.urls")),
    path("", include("web.urls")),
]

# S13: custom branded error pages (only used when DEBUG=False).
handler404 = "web.views.handler_404"
handler500 = "web.views.handler_500"
handler403 = "web.views.handler_403"
