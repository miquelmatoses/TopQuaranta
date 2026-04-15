from django.urls import path

from . import dashboard
from . import artistes
from . import cancons
from . import eines
from . import pendents
from . import ranking

app_name = "staff"

urlpatterns = [
    path("", dashboard.dashboard, name="dashboard"),
    # P2: Cançons
    path("cancons/", cancons.llista, name="cancons"),
    path("cancons/accio/", cancons.accio, name="cancons_accio"),
    # P3: Ranking provisional
    path("ranking/", ranking.llista, name="ranking"),
    path("ranking/accio/", ranking.accio, name="ranking_accio"),
    # P4: Artistes
    path("artistes/", artistes.llista, name="artistes"),
    path("artistes/accio/", artistes.accio, name="artistes_accio"),
    path("artistes/<int:pk>/editar/", artistes.editar, name="artista_editar"),
    # P5: Artistes pendents
    path("artistes/pendents/", pendents.llista, name="artistes_pendents"),
    path("artistes/pendents/api/territoris/", pendents.api_territoris, name="api_territoris"),
    path("artistes/pendents/api/comarques/", pendents.api_comarques, name="api_comarques"),
    path("artistes/pendents/api/municipis/", pendents.api_municipis, name="api_municipis"),
    path("artistes/pendents/<int:pk>/aprovar/", pendents.api_aprovar, name="api_aprovar"),
    path("artistes/pendents/<int:pk>/descartar/", pendents.api_descartar, name="api_descartar"),
    # P6: Eines restants
    path("historial/", eines.historial, name="historial"),
    path("senyal/", eines.senyal, name="senyal"),
    path("verificacio/", eines.verificacio_artistes, name="verificacio_artistes"),
    path("verificacio/<int:pk>/toggle/", eines.verificacio_toggle, name="verificacio_toggle"),
    path("configuracio/", eines.configuracio, name="configuracio"),
]
