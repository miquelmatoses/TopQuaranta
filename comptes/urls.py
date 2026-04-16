from django.urls import path

from . import views

app_name = "comptes"

urlpatterns = [
    path("accedir/", views.accedir, name="accedir"),
    path("registre/", views.registre, name="registre"),
    path("activar/<str:uidb64>/<str:token>/", views.activar, name="activar"),
    path("login/", views.TQLoginView.as_view(), name="login"),
    path("logout/", views.TQLogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("perfil/", views.perfil, name="perfil"),
    path("artista/gestio/", views.sollicitud_gestio, name="sollicitud_gestio"),
    path("artista/proposta/", views.sollicitud_proposta, name="sollicitud_proposta"),
    path("artista/", views.portal_artista, name="portal_artista"),
    # Legacy redirect
    path("artista/sollicitud/", views.sollicitud_gestio, name="sollicitud_artista"),
]
