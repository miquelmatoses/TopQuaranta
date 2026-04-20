"""Staff-only endpoints for the React SPA.

These endpoints gate on `user.is_staff` and feed the /staff/* React
routes. Each area of the staff panel gets its own view module
(incoming in subsequent sub-sprints); this first module wires only
the landing dashboard so we can validate auth + layout end-to-end.

GET /api/v1/staff/dashboard/  — counters for the landing tile grid
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from comptes.models import PropostaArtista, UserArtista, Usuari
from music.models import Artista, Canco


class IsStaff(BasePermission):
    """Allow only authenticated users flagged `is_staff`."""

    message = "Staff access required."

    def has_permission(self, request, view):  # noqa: D401 - DRF signature
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


@api_view(["GET"])
@permission_classes([IsStaff])
def dashboard(request: Request) -> Response:
    """Counters for every staff tool shown on the landing grid.

    The React dashboard renders one card per tool and overlays the
    open-items count. We compute all counts in a single response so
    the grid shows up in one round-trip.
    """
    return Response(
        {
            "artistes_pendents": Artista.objects.filter(
                aprovat=False, pendent_review=True
            ).count(),
            "cancons_no_verificades": Canco.objects.filter(verificada=False).count(),
            "propostes_obertes": PropostaArtista.objects.filter(
                estat=PropostaArtista.ESTAT_PENDENT
            ).count(),
            "solicituds_gestio_obertes": UserArtista.objects.filter(
                estat=UserArtista.ESTAT_PENDENT
            ).count(),
            "usuaris_total": Usuari.objects.filter(is_active=True).count(),
        }
    )
