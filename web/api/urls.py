from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("mapa/artistes/", views.mapa_artistes, name="mapa_artistes"),
    # Location API — reference data, no auth required
    path("localitzacio/territoris/", views.api_territoris, name="api_territoris"),
    path("localitzacio/comarques/", views.api_comarques, name="api_comarques"),
    path("localitzacio/municipis/", views.api_municipis, name="api_municipis"),
    path(
        "localitzacio/municipi-lookup/",
        views.api_municipi_lookup,
        name="api_municipi_lookup",
    ),
]
