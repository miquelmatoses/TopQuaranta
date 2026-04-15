from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.homepage, name="homepage"),
    path("ranking/<str:territori>/", views.ranking_territori, name="ranking"),
    path(
        "ranking/<str:territori>/<str:setmana_str>/",
        views.ranking_territori,
        name="ranking_setmana",
    ),
    path("artistes/", views.directori_artistes, name="artistes"),
    path("artista/<slug:slug>/", views.perfil_artista, name="artista"),
    path("mapa/", views.mapa, name="mapa"),
]
