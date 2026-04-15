from django.urls import include, path

urlpatterns = [
    path("api/v1/", include("web.api.urls")),
    path("compte/", include("comptes.urls")),
    path("staff/", include("web.views.staff.urls")),
    path("", include("web.urls")),
]
