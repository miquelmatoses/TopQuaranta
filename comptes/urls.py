"""URL patterns served by Django under `/compte/`.

After Sprint 4's React flip, the SPA owns `/compte`, `/compte/accedir`,
`/compte/dashboard`, `/compte/perfil` and the two artist-CTA forms.
What remains here are the flows that still rely on server-rendered
HTML + POST cycles:

  * /compte/registre/               — signup form (the account is
                                      still Django session-based).
  * /compte/activar/<uid>/<token>/  — email verification landing.
  * /compte/login/ + /compte/logout/ — TQLoginView/TQLogoutView
                                       drive the axes + django-otp
                                       chain; React login UI hits
                                       /api/v1/auth/login/ directly
                                       but these URLs stay live
                                       because /compte/2fa/verificar/
                                       posts to /compte/login/ on
                                       2FA-required redirects.
  * /compte/2fa/{configurar,verificar,gestio}/ — TOTP enrollment,
                                                 verification and
                                                 management. React
                                                 AdminRoute bounces
                                                 unverified staff
                                                 here.

Every path above is in the Caddy allow-list (deploy/Caddyfile); any
route not listed here is served by the SPA instead.
"""

from django.urls import path

from . import views

app_name = "comptes"

urlpatterns = [
    path("registre/", views.registre, name="registre"),
    path("activar/<str:uidb64>/<str:token>/", views.activar, name="activar"),
    path("login/", views.TQLoginView.as_view(), name="login"),
    path("logout/", views.TQLogoutView.as_view(), name="logout"),
    # S11 · 2FA
    path("2fa/configurar/", views.dos_fa_configurar, name="dos_fa_configurar"),
    path("2fa/verificar/", views.dos_fa_verificar, name="dos_fa_verificar"),
    path("2fa/", views.dos_fa_gestio, name="dos_fa_gestio"),
]
