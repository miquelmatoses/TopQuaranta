from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.homepage, name="homepage"),
    # New single ranking page with territory selector
    path("ranking/", views.ranking_page, name="ranking"),
    # Legacy URL redirects (permanent 301)
    path(
        "ranking/<str:territori>/",
        views.ranking_territori_redirect,
        name="ranking_territori_redirect",
    ),
    path(
        "ranking/<str:territori>/<str:setmana_str>/",
        views.ranking_territori_redirect,
        name="ranking_setmana_redirect",
    ),
    path("artistes/", views.directori_artistes, name="artistes"),
    path("artista/<slug:slug>/", views.perfil_artista, name="artista"),
    path("album/<slug:slug>/", views.perfil_album, name="album"),
    path("mapa/", views.mapa, name="mapa"),
    # Φ4 · public algorithm transparency
    path("com-funciona/", views.com_funciona, name="com_funciona"),
    path("com-funciona/historial/", views.com_funciona_historial, name="com_funciona_historial"),
]
