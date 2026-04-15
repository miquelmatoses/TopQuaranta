from django.urls import path

from . import views

app_name = "comptes"

urlpatterns = [
    path("registre/", views.registre, name="registre"),
    path("activar/<str:uidb64>/<str:token>/", views.activar, name="activar"),
    path("login/", views.TQLoginView.as_view(), name="login"),
    path("logout/", views.TQLogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("artista/sol·licitud/", views.sollicitud_artista, name="sollicitud_artista"),
    path("artista/", views.portal_artista, name="portal_artista"),
]
