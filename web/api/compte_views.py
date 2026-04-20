"""Authenticated /compte/ endpoints for the React SPA.

GET   /api/v1/compte/dashboard/   — managed artists + proposals + stats
GET   /api/v1/compte/perfil/      — current profile snapshot
PATCH /api/v1/compte/perfil/      — update email / username / password
POST  /api/v1/compte/propostes/   — submit a new-artist proposal
POST  /api/v1/compte/solicituds/  — submit a management request for an
                                    existing artist
"""

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from comptes.models import HTTP_ONLY_URL, PropostaArtista, UserArtista, Usuari
from music.models import Artista
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


def _profile_payload(user) -> dict:
    return {
        "email": user.email,
        "username": user.username,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        "is_staff": bool(user.is_staff),
        "is_superuser": bool(user.is_superuser),
    }


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def perfil(request: Request) -> Response:
    """Current user profile — read + partial update.

    PATCH accepts any subset of:
      email, username, password (requires current_password).

    Email changes are validated (syntax + uniqueness). Password change
    runs Django's full validator chain; on success we keep the session
    alive via `update_session_auth_hash` so the user doesn't get kicked
    out mid-edit.
    """
    user = request.user

    if request.method == "GET":
        return Response(_profile_payload(user))

    data = request.data or {}
    errors: dict[str, str] = {}

    new_email = (data.get("email") or "").strip().lower()
    if new_email and new_email != user.email:
        try:
            validate_email(new_email)
        except ValidationError:
            errors["email"] = "Correu no vàlid."
        else:
            if (
                Usuari.objects.filter(email__iexact=new_email)
                .exclude(pk=user.pk)
                .exists()
            ):
                errors["email"] = "Aquest correu ja està en ús."

    new_username = (data.get("username") or "").strip()
    if new_username and new_username != user.username:
        if len(new_username) < 3:
            errors["username"] = "Massa curt (mínim 3)."
        elif (
            Usuari.objects.filter(username__iexact=new_username)
            .exclude(pk=user.pk)
            .exists()
        ):
            errors["username"] = "Aquest nom d'usuari ja està en ús."

    new_password = data.get("password") or ""
    current_password = data.get("current_password") or ""
    if new_password:
        if not current_password or not user.check_password(current_password):
            errors["current_password"] = "La contrasenya actual és incorrecta."
        else:
            try:
                validate_password(new_password, user=user)
            except ValidationError as exc:
                errors["password"] = "; ".join(exc.messages)

    if errors:
        return Response({"errors": errors}, status=400)

    updated_fields: list[str] = []
    if new_email and new_email != user.email:
        user.email = new_email
        updated_fields.append("email")
    if new_username and new_username != user.username:
        user.username = new_username
        updated_fields.append("username")

    try:
        if updated_fields:
            user.save(update_fields=updated_fields)
        if new_password:
            user.set_password(new_password)
            user.save(update_fields=["password"])
            update_session_auth_hash(request, user)
    except IntegrityError:
        return Response(
            {"errors": {"__all__": "Error de validació al desar."}},
            status=400,
        )

    return Response(_profile_payload(user))


# ─────────────────────────────────────────────────────────────────────────
# Propostes d'artistes nous (user-submitted)
# ─────────────────────────────────────────────────────────────────────────

SOCIAL_FIELDS = [f for f, _ in Artista.SOCIAL_LINK_FIELDS]
# Subset of SOCIAL_FIELDS that also exists on PropostaArtista. Myspace
# lives on Artista only; skipping it here keeps setattr() safe.
PROPOSTA_SOCIAL_FIELDS = [
    "spotify_url",
    "viasona_url",
    "web_url",
    "bandcamp_url",
    "youtube_url",
    "viquipedia_url",
    "soundcloud_url",
    "tiktok_url",
    "facebook_url",
]


def _clean_url(raw: str) -> tuple[str, str | None]:
    """Validate a user-submitted URL. Returns (value, error)."""
    raw = (raw or "").strip()
    if not raw:
        return "", None
    try:
        HTTP_ONLY_URL(raw)
    except ValidationError:
        return raw, "URL no vàlida (només http/https)."
    return raw, None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def proposta_crear(request: Request) -> Response:
    """Create a PropostaArtista for the authenticated user.

    Body:
      nom            str, required
      justificacio   str, required
      <social>_url   optional URL fields (one per social network)
      deezer_ids     optional list of ints / numeric strings
      localitzacions optional list of {"municipi_id": int} or {"manual": str}
    """
    data = request.data or {}
    errors: dict[str, str] = {}

    nom = (data.get("nom") or "").strip()
    if not nom:
        errors["nom"] = "Obligatori."
    elif len(nom) > 255:
        errors["nom"] = "Massa llarg (màxim 255 caràcters)."

    justificacio = (data.get("justificacio") or "").strip()
    if not justificacio:
        errors["justificacio"] = "Obligatòria."

    socials: dict[str, str] = {}
    for f in PROPOSTA_SOCIAL_FIELDS:
        val, err = _clean_url(data.get(f, ""))
        if err:
            errors[f] = err
        socials[f] = val

    deezer_ids: list[int] = []
    for raw in data.get("deezer_ids") or []:
        try:
            deezer_ids.append(int(raw))
        except (TypeError, ValueError):
            errors["deezer_ids"] = "Un dels IDs no és un número."

    localitzacions: list[dict] = []
    for loc in data.get("localitzacions") or []:
        if not isinstance(loc, dict):
            continue
        if loc.get("municipi_id"):
            try:
                localitzacions.append({"municipi_id": int(loc["municipi_id"])})
            except (TypeError, ValueError):
                pass
        elif loc.get("manual"):
            manual = str(loc["manual"]).strip()
            if manual:
                localitzacions.append({"manual": manual})

    if errors:
        return Response({"errors": errors}, status=400)

    p = PropostaArtista.objects.create(
        usuari=request.user,
        nom=nom,
        justificacio=justificacio,
        deezer_ids=deezer_ids,
        localitzacions=localitzacions,
        **socials,
    )
    return Response({"ok": True, "pk": p.pk, "estat": p.estat}, status=201)


# ─────────────────────────────────────────────────────────────────────────
# Sol·licituds de gestió (UserArtista)
# ─────────────────────────────────────────────────────────────────────────


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def solicitud_crear(request: Request) -> Response:
    """Create a UserArtista request for the authenticated user.

    Body:
      artista_slug  str, required — must resolve to an aprovat=True artist
      sollicitud_text  str, required — why you should manage this artist
    """
    data = request.data or {}
    errors: dict[str, str] = {}

    slug = (data.get("artista_slug") or "").strip()
    text = (data.get("sollicitud_text") or "").strip()
    if not slug:
        errors["artista_slug"] = "Tria un artista."
    if not text:
        errors["sollicitud_text"] = "Cal una justificació."

    if errors:
        return Response({"errors": errors}, status=400)

    try:
        artista = Artista.objects.get(slug=slug, aprovat=True)
    except Artista.DoesNotExist:
        return Response(
            {"errors": {"artista_slug": "Artista no trobat o no aprovat."}},
            status=404,
        )

    # Deny duplicates: same user + same artist + still open.
    existing = UserArtista.objects.filter(
        usuari=request.user,
        artista=artista,
        estat__in=[UserArtista.ESTAT_PENDENT, UserArtista.ESTAT_APROVAT],
    ).first()
    if existing:
        return Response(
            {
                "errors": {
                    "artista_slug": (
                        "Ja tens una sol·licitud activa per a aquest artista."
                    )
                }
            },
            status=400,
        )

    ua = UserArtista.objects.create(
        usuari=request.user,
        artista=artista,
        sollicitud_text=text,
        estat=UserArtista.ESTAT_PENDENT,
    )
    return Response({"ok": True, "pk": ua.pk, "estat": ua.estat}, status=201)
