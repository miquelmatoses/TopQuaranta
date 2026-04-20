from django.urls import path

from . import (
    album_views,
    artistes_views,
    auth_views,
    canco_views,
    compte_views,
    ranking_views,
    staff_views,
    views,
)

app_name = "api"

urlpatterns = [
    # Auth (consumed by the React SPA)
    path("auth/me/", auth_views.me, name="auth_me"),
    path("auth/login/", auth_views.login_view, name="auth_login"),
    path("auth/logout/", auth_views.logout_view, name="auth_logout"),
    # Authenticated user area
    path("compte/dashboard/", compte_views.dashboard, name="compte_dashboard"),
    path("compte/perfil/", compte_views.perfil, name="compte_perfil"),
    path(
        "compte/propostes/",
        compte_views.proposta_crear,
        name="compte_proposta_crear",
    ),
    path(
        "compte/solicituds/",
        compte_views.solicitud_crear,
        name="compte_solicitud_crear",
    ),
    # Public feedback (authenticated, any user)
    path("feedback/", compte_views.feedback_crear, name="feedback_crear"),
    # ── Staff (is_staff required) ──
    path("staff/dashboard/", staff_views.dashboard, name="staff_dashboard"),
    # Pendents
    path("staff/pendents/", staff_views.pendents_list, name="staff_pendents_list"),
    path(
        "staff/pendents/<int:pk>/aprovar/",
        staff_views.pendent_aprovar,
        name="staff_pendent_aprovar",
    ),
    path(
        "staff/pendents/<int:pk>/descartar/",
        staff_views.pendent_descartar,
        name="staff_pendent_descartar",
    ),
    # Artistes
    path("staff/artistes/", staff_views.artistes_list, name="staff_artistes_list"),
    path(
        "staff/artistes/crear/",
        staff_views.artista_crear,
        name="staff_artista_crear",
    ),
    path(
        "staff/artistes/<int:pk>/",
        staff_views.artista_detail,
        name="staff_artista_detail",
    ),
    # Cançons
    path("staff/cancons/", staff_views.cancons_list, name="staff_cancons_list"),
    path("staff/cancons/accio/", staff_views.cancons_accio, name="staff_cancons_accio"),
    path(
        "staff/cancons/<int:pk>/",
        staff_views.canco_detail,
        name="staff_canco_detail",
    ),
    # Albums
    path("staff/albums/", staff_views.albums_list, name="staff_albums_list"),
    path(
        "staff/albums/<int:pk>/",
        staff_views.album_detail,
        name="staff_album_detail",
    ),
    # Ranking provisional
    path("staff/ranking/", staff_views.ranking_list, name="staff_ranking_list"),
    path("staff/ranking/accio/", staff_views.ranking_accio, name="staff_ranking_accio"),
    # Propostes
    path("staff/propostes/", staff_views.propostes_list, name="staff_propostes_list"),
    path(
        "staff/propostes/<int:pk>/",
        staff_views.proposta_detail,
        name="staff_proposta_detail",
    ),
    path(
        "staff/propostes/<int:pk>/aprovar/",
        staff_views.proposta_aprovar,
        name="staff_proposta_aprovar",
    ),
    path(
        "staff/propostes/<int:pk>/rebutjar/",
        staff_views.proposta_rebutjar,
        name="staff_proposta_rebutjar",
    ),
    # Sol·licituds de gestió
    path(
        "staff/solicituds/", staff_views.solicituds_list, name="staff_solicituds_list"
    ),
    path(
        "staff/solicituds/<int:pk>/toggle/",
        staff_views.solicitud_toggle,
        name="staff_solicitud_toggle",
    ),
    path(
        "staff/solicituds/<int:pk>/rebutjar/",
        staff_views.solicitud_rebutjar,
        name="staff_solicitud_rebutjar",
    ),
    # Senyal diari
    path("staff/senyal/", staff_views.senyal_list, name="staff_senyal_list"),
    path(
        "staff/senyal/<int:canco_pk>/acceptar-correccio/",
        staff_views.senyal_acceptar_correccio,
        name="staff_senyal_acceptar_correccio",
    ),
    # Historial
    path("staff/historial/", staff_views.historial_list, name="staff_historial_list"),
    # Configuració
    path("staff/configuracio/", staff_views.configuracio, name="staff_configuracio"),
    # Auditoria
    path("staff/auditlog/", staff_views.auditlog, name="staff_auditlog"),
    # Feedback (user-filed corrections)
    path(
        "staff/feedback/",
        staff_views.feedback_list,
        name="staff_feedback_list",
    ),
    path(
        "staff/feedback/<int:pk>/resolve/",
        staff_views.feedback_resolve,
        name="staff_feedback_resolve",
    ),
    # Usuaris
    path("staff/usuaris/", staff_views.usuaris_list, name="staff_usuaris_list"),
    path(
        "staff/usuaris/<int:pk>/",
        staff_views.usuari_detail,
        name="staff_usuari_detail",
    ),
    path(
        "staff/usuaris/<int:pk>/toggle-actiu/",
        staff_views.usuari_toggle_actiu,
        name="staff_usuari_toggle_actiu",
    ),
    path(
        "staff/usuaris/<int:pk>/reset-2fa/",
        staff_views.usuari_reset_2fa,
        name="staff_usuari_reset_2fa",
    ),
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
