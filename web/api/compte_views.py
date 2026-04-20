"""Authenticated /compte/ endpoints for the React SPA.

GET /api/v1/compte/dashboard/   — list of managed artists + proposals + stats
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from comptes.models import PropostaArtista, UserArtista
from ranking.models import RankingSetmanal


def _serialize_user_artista(ua) -> dict:
    a = ua.artista
    return {
        "pk": ua.pk,
        "estat": ua.estat,
        "verificat": ua.verificat,
        "created_at": ua.created_at.isoformat() if ua.created_at else None,
        "artista": {
            "slug": a.slug,
            "nom": a.nom,
        },
    }


def _serialize_proposta(p) -> dict:
    return {
        "pk": p.pk,
        "nom": p.nom,
        "estat": p.estat,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "justificacio": p.justificacio,
        "artista_creat": (
            {"slug": p.artista_creat.slug, "nom": p.artista_creat.nom}
            if p.artista_creat
            else None
        ),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request: Request) -> Response:
    user = request.user
    gestio_list = list(
        UserArtista.objects.filter(usuari=user)
        .select_related("artista")
        .order_by("-created_at")
    )
    propostes_list = list(
        PropostaArtista.objects.filter(usuari=user)
        .select_related("artista_creat")
        .order_by("-created_at")
    )
    artista_verificat = next((ua for ua in gestio_list if ua.verificat), None)

    # Artist stats, only if the user manages a verified artist.
    stats = None
    if artista_verificat:
        qs = RankingSetmanal.objects.filter(canco__artista=artista_verificat.artista)
        stats = {
            "setmanes_al_ranking": qs.values("setmana").distinct().count(),
            "millor_posicio": qs.order_by("posicio")
            .values_list("posicio", flat=True)
            .first(),
            "cancons_al_ranking": qs.values("canco_id").distinct().count(),
            "territoris_presents": qs.values("territori").distinct().count(),
        }

    return Response(
        {
            "user": {
                "email": user.email,
                "username": user.username,
                "date_joined": (
                    user.date_joined.isoformat() if user.date_joined else None
                ),
                "is_staff": bool(user.is_staff),
            },
            "gestio_list": [_serialize_user_artista(u) for u in gestio_list],
            "propostes_list": [_serialize_proposta(p) for p in propostes_list],
            "artista_verificat": (
                _serialize_user_artista(artista_verificat)
                if artista_verificat
                else None
            ),
            "stats": stats,
        }
    )
