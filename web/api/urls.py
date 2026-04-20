from django.urls import path

from . import (
    album_views,
    artistes_views,
    auth_views,
    canco_views,
    ranking_views,
    views,
)

app_name = "api"

urlpatterns = [
    # Auth (consumed by the React SPA)
    path("auth/me/", auth_views.me, name="auth_me"),
    path("auth/login/", auth_views.login_view, name="auth_login"),
    path("auth/logout/", auth_views.logout_view, name="auth_logout"),
    # Ranking (top 40 per territory + week)
    path("ranking/", ranking_views.ranking, name="ranking"),
    # Artistes
    path("artistes/", artistes_views.artistes_list, name="artistes_list"),
    path("artistes/<slug:slug>/", artistes_views.artista_detail, name="artista_detail"),
    # Albums
    path("albums/<slug:slug>/", album_views.album_detail, name="album_detail"),
    # Cançons
    path("cancons/<slug:slug>/", canco_views.canco_detail, name="canco_detail"),
    # Mapa (existing)
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
