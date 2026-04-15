from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("mapa/artistes/", views.mapa_artistes, name="mapa_artistes"),
]
