"""Community-platform endpoints (Grup C).

All routes live under `/api/v1/`. This module owns:

  * `/compte/perfil-usuari/`         GET + PATCH — authenticated user's own profile
  * `/comunitat/directori/`          GET — listing of users with visible_directori=True
  * `/comunitat/publicacions/`       GET (list) + POST (create)
  * `/comunitat/publicacions/<pk>/`  GET + PATCH + DELETE (owner or staff)
  * `/comunitat/publicacions-publiques/`  GET — unauthenticated public feed
  * `/staff/publicacions/`           GET — staff moderation list
  * `/staff/publicacions/<pk>/decidir/`   POST — publicar / rebutjar
  * `/staff/directori-usuaris/`      GET + `/staff/directori-usuaris/<pk>/toggle/`

Visibility rules:

  - `interna` + `publicat` → visible to any authenticated user.
  - `publica` + `publicat` → visible to everyone (no auth needed).
  - `esborrany` / `pendent` / `rebutjat` → visible only to the author
    and to staff.

Staff bypass: staff posts skip the `pendent` step and land in `publicat`
immediately. Non-staff posts with `visibilitat=publica` start in
`pendent` and wait for staff review.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from comptes.models import (
    HTTP_ONLY_URL,
    PerfilUsuari,
    Publicacio,
    UserArtista,
)
from music.models import Municipi
from web.api.staff_views import IsStaff

# ═════════════════════════════════════════════════════════════════════════
# PerfilUsuari
# ═════════════════════════════════════════════════════════════════════════


def _serialize_perfil(p: PerfilUsuari, *, include_private: bool = False) -> dict:
    """Return a JSON-safe snapshot of a PerfilUsuari.

    `include_private` adds fields the owner (or staff) can see but which
    aren't safe to surface in the public directori — e.g. raw email or
    onboarding state.
    """
    loc = p.localitat
    row = {
        "usuari_id": p.usuari_id,
        "username": p.usuari.username,
        "nom_public": p.nom_public,
        "imatge_url": p.imatge_url or "",
        "bio": p.bio or "",
        "rol_musical": p.rol_musical,
        "instruments": p.instruments or "",
        "visible_directori": p.visible_directori,
        "obert_colaboracions": p.obert_colaboracions,
        "social": {f: getattr(p, f) or "" for f, _ in PerfilUsuari.SOCIAL_FIELDS},
        "localitat": (
            {
                "pk": loc.pk,
                "nom": loc.nom,
                "comarca": loc.comarca,
                "territori": loc.territori_id,
            }
            if loc
            else None
        ),
        "social_fields": list(PerfilUsuari.SOCIAL_FIELDS),
        "rol_choices": list(PerfilUsuari.ROL_CHOICES),
    }
    if include_private:
        row["email"] = p.usuari.email
        row["onboarding_complet"] = p.onboarding_complet
    return row


def _clean_url(raw: str) -> tuple[str, str | None]:
    raw = (raw or "").strip()
    if not raw:
        return "", None
    try:
        HTTP_ONLY_URL(raw)
    except ValidationError:
        return raw, "URL no vàlida (només http/https)."
    return raw, None


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def perfil_usuari(request: Request) -> Response:
    """Authenticated user's own PerfilUsuari — read + partial update.

    The signal on User creation guarantees `usuari.perfil` exists, so we
    can assume the OneToOne. If for any reason it doesn't we create it
    on-the-fly.
    """
    user = request.user
    perfil, _ = PerfilUsuari.objects.get_or_create(usuari=user)

    if request.method == "PATCH":
        data = request.data or {}
        errors: dict[str, str] = {}

        # Simple fields
        simple = {
            "nom_public": 120,
            "bio": 2000,
            "instruments": 255,
        }
        for field, maxlen in simple.items():
            if field in data:
                val = (data.get(field) or "").strip()
                if len(val) > maxlen:
                    errors[field] = f"Massa llarg (màxim {maxlen})."
                else:
                    setattr(perfil, field, val)

        # Image URL (optional)
        if "imatge_url" in data:
            val, err = _clean_url(data.get("imatge_url", ""))
            if err:
                errors["imatge_url"] = err
            else:
                perfil.imatge_url = val

        # Localitat: either municipi_id (int) or null
        if "localitat_pk" in data:
            raw = data.get("localitat_pk")
            if raw in (None, "", 0):
                perfil.localitat = None
            else:
                try:
                    perfil.localitat = Municipi.objects.get(pk=int(raw))
                except (ValueError, Municipi.DoesNotExist):
                    errors["localitat_pk"] = "Municipi no trobat."

        # Rol + instruments + visibility flags
        if "rol_musical" in data:
            v = (data.get("rol_musical") or "").strip()
            if v not in {k for k, _ in PerfilUsuari.ROL_CHOICES}:
                errors["rol_musical"] = "Valor no vàlid."
            else:
                perfil.rol_musical = v

        for flag in ("visible_directori", "obert_colaboracions", "onboarding_complet"):
            if flag in data:
                setattr(perfil, flag, bool(data.get(flag)))

        # Socials
        for field, _label in PerfilUsuari.SOCIAL_FIELDS:
            if field in data:
                val, err = _clean_url(data.get(field, ""))
                if err:
                    errors[field] = err
                else:
                    setattr(perfil, field, val)

        if errors:
            return Response({"errors": errors}, status=400)
        perfil.save()

    return Response(_serialize_perfil(perfil, include_private=True))


# ═════════════════════════════════════════════════════════════════════════
# Directori (authenticated users only)
# ═════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def directori(request: Request) -> Response:
    """Public-to-registered-users directory.

    Filters: q (name/username/instruments), rol, obert_colaboracions,
    territori (by localitat.municipi.territori). Page size 30.
    """
    qs = (
        PerfilUsuari.objects.filter(visible_directori=True, usuari__is_active=True)
        .select_related("usuari", "localitat", "localitat__territori")
        .prefetch_related("usuari__artistes_vinculats__artista")
    )
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(nom_public__icontains=q)
            | Q(usuari__username__icontains=q)
            | Q(instruments__icontains=q)
            | Q(bio__icontains=q)
        )
    rol = request.GET.get("rol", "")
    if rol in {k for k, _ in PerfilUsuari.ROL_CHOICES}:
        qs = qs.filter(rol_musical=rol)
    if request.GET.get("obert") == "1":
        qs = qs.filter(obert_colaboracions=True)
    territori = request.GET.get("territori", "")
    if territori:
        qs = qs.filter(localitat__territori_id=territori)

    qs = qs.order_by("nom_public", "usuari__username")

    try:
        per_page = min(int(request.GET.get("per_page") or 30), 100)
    except ValueError:
        per_page = 30
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page") or 1)

    rows = []
    for p in page.object_list:
        artistes_gestionats = [
            {"slug": ua.artista.slug, "nom": ua.artista.nom}
            for ua in p.usuari.artistes_vinculats.all()
            if ua.estat == UserArtista.ESTAT_APROVAT and ua.artista
        ]
        loc = p.localitat
        rows.append(
            {
                "usuari_id": p.usuari_id,
                "username": p.usuari.username,
                "nom_public": p.nom_public or p.usuari.username,
                "rol_musical": p.rol_musical,
                "instruments": p.instruments or "",
                "obert_colaboracions": p.obert_colaboracions,
                "imatge_url": p.imatge_url or "",
                "localitat": (
                    f"{loc.nom}, {loc.comarca} ({loc.territori_id})" if loc else ""
                ),
                "territori": loc.territori_id if loc else None,
                "artistes_gestionats": artistes_gestionats,
            }
        )

    return Response(
        {
            "results": rows,
            "page": page.number,
            "num_pages": paginator.num_pages,
            "total": paginator.count,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
            "rol_choices": list(PerfilUsuari.ROL_CHOICES),
        }
    )


# ═════════════════════════════════════════════════════════════════════════
# Publicacions
# ═════════════════════════════════════════════════════════════════════════


def _serialize_publicacio(pub: Publicacio, *, for_staff: bool = False) -> dict:
    row = {
        "pk": pub.pk,
        "titol": pub.titol,
        "cos": pub.cos,
        "visibilitat": pub.visibilitat,
        "estat": pub.estat,
        "created_at": pub.created_at.isoformat() if pub.created_at else None,
        "publicat_at": pub.publicat_at.isoformat() if pub.publicat_at else None,
        "updated_at": pub.updated_at.isoformat() if pub.updated_at else None,
        "autor": {
            "username": pub.autor.username,
            "nom_public": getattr(getattr(pub.autor, "perfil", None), "nom_public", "")
            or pub.autor.username,
            "is_staff": pub.autor.is_staff,
        },
    }
    if for_staff:
        row["notes_staff"] = pub.notes_staff or ""
    return row


def _validate_publicacio_body(data: dict) -> tuple[dict, dict]:
    """Common validation for create + edit. Returns (cleaned, errors)."""
    errors: dict[str, str] = {}
    titol = (data.get("titol") or "").strip()
    if not titol:
        errors["titol"] = "Obligatori."
    elif len(titol) > 200:
        errors["titol"] = "Massa llarg (màxim 200)."
    cos = (data.get("cos") or "").strip()
    if not cos:
        errors["cos"] = "El cos no pot ser buit."
    elif len(cos) > 20000:
        errors["cos"] = "Massa llarg (màxim 20 000 caràcters)."
    visibilitat = data.get("visibilitat", Publicacio.VISIBILITAT_INTERNA)
    if visibilitat not in {k for k, _ in Publicacio.VISIBILITAT_CHOICES}:
        errors["visibilitat"] = "Valor no vàlid."
    return {"titol": titol, "cos": cos, "visibilitat": visibilitat}, errors


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def publicacions(request: Request) -> Response:
    """List + create. List returns internal + public (authenticated view)."""
    if request.method == "POST":
        cleaned, errors = _validate_publicacio_body(request.data or {})
        save_as = (request.data or {}).get("save_as", "submit")
        if errors:
            return Response({"errors": errors}, status=400)
        user = request.user
        # Staff bypasses the pending queue for any visibility.
        # Regular users: `interna` → published directly;
        # `publica` → goes through the pending queue.
        if save_as == "draft":
            estat = Publicacio.ESTAT_ESBORRANY
            publicat_at = None
        elif user.is_staff or cleaned["visibilitat"] == Publicacio.VISIBILITAT_INTERNA:
            estat = Publicacio.ESTAT_PUBLICAT
            publicat_at = timezone.now()
        else:
            estat = Publicacio.ESTAT_PENDENT
            publicat_at = None

        pub = Publicacio.objects.create(
            autor=user,
            titol=cleaned["titol"],
            cos=cleaned["cos"],
            visibilitat=cleaned["visibilitat"],
            estat=estat,
            publicat_at=publicat_at,
        )
        return Response(_serialize_publicacio(pub), status=201)

    # ── GET: combined internal + own drafts/pending + public ───────────
    qs = Publicacio.objects.select_related("autor", "autor__perfil")
    # Show: (visibilitat=interna AND estat=publicat) + own in any state
    own = Q(autor=request.user)
    internal_published = Q(
        visibilitat=Publicacio.VISIBILITAT_INTERNA, estat=Publicacio.ESTAT_PUBLICAT
    )
    public_published = Q(
        visibilitat=Publicacio.VISIBILITAT_PUBLICA, estat=Publicacio.ESTAT_PUBLICAT
    )
    qs = qs.filter(own | internal_published | public_published)

    filter_mode = request.GET.get("filtre", "")
    if filter_mode == "meves":
        qs = qs.filter(autor=request.user)
    elif filter_mode == "internes":
        qs = qs.filter(internal_published)
    elif filter_mode == "publiques":
        qs = qs.filter(public_published)

    qs = qs.order_by("-publicat_at", "-created_at")
    try:
        per_page = min(int(request.GET.get("per_page") or 20), 100)
    except ValueError:
        per_page = 20
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page") or 1)
    return Response(
        {
            "results": [_serialize_publicacio(p) for p in page.object_list],
            "page": page.number,
            "num_pages": paginator.num_pages,
            "total": paginator.count,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
        }
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def publicacio_detail(request: Request, pk: int) -> Response:
    pub = get_object_or_404(
        Publicacio.objects.select_related("autor", "autor__perfil"), pk=pk
    )
    # Authorization: author can always see; staff can always see; other
    # users only if it's published.
    user = request.user
    can_view = (
        pub.autor_id == user.id
        or user.is_staff
        or pub.estat == Publicacio.ESTAT_PUBLICAT
    )
    if not can_view:
        return Response({"detail": "No trobat."}, status=404)

    if request.method == "DELETE":
        if pub.autor_id != user.id and not user.is_staff:
            return Response({"detail": "No autoritzat."}, status=403)
        pub.delete()
        return Response(status=204)

    if request.method == "PATCH":
        if pub.autor_id != user.id and not user.is_staff:
            return Response({"detail": "No autoritzat."}, status=403)
        cleaned, errors = _validate_publicacio_body(request.data or {})
        if errors:
            return Response({"errors": errors}, status=400)
        pub.titol = cleaned["titol"]
        pub.cos = cleaned["cos"]
        # Visibility change rules: staff free; author can only move
        # between esborrany/interna. Switching to `publica` resubmits
        # for approval unless staff.
        old_vis = pub.visibilitat
        pub.visibilitat = cleaned["visibilitat"]
        if not user.is_staff and old_vis != pub.visibilitat:
            if pub.visibilitat == Publicacio.VISIBILITAT_PUBLICA:
                pub.estat = Publicacio.ESTAT_PENDENT
                pub.publicat_at = None
            else:
                pub.estat = Publicacio.ESTAT_PUBLICAT
                pub.publicat_at = pub.publicat_at or timezone.now()
        pub.save()

    return Response(
        _serialize_publicacio(pub, for_staff=user.is_staff or pub.autor_id == user.id)
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def publicacions_publiques(request: Request) -> Response:
    """Public feed — visible without auth, only `publica + publicat`."""
    qs = (
        Publicacio.objects.filter(
            visibilitat=Publicacio.VISIBILITAT_PUBLICA,
            estat=Publicacio.ESTAT_PUBLICAT,
        )
        .select_related("autor", "autor__perfil")
        .order_by("-publicat_at")
    )
    try:
        per_page = min(int(request.GET.get("per_page") or 20), 100)
    except ValueError:
        per_page = 20
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page") or 1)
    return Response(
        {
            "results": [_serialize_publicacio(p) for p in page.object_list],
            "page": page.number,
            "num_pages": paginator.num_pages,
            "total": paginator.count,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
        }
    )


# ═════════════════════════════════════════════════════════════════════════
# Staff moderation
# ═════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([IsStaff])
def staff_publicacions(request: Request) -> Response:
    qs = Publicacio.objects.select_related("autor", "autor__perfil")
    estat = request.GET.get("estat", "pendent")
    if estat in {k for k, _ in Publicacio.ESTAT_CHOICES}:
        qs = qs.filter(estat=estat)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(titol__icontains=q)
            | Q(cos__icontains=q)
            | Q(autor__username__icontains=q)
            | Q(autor__email__icontains=q)
        )
    qs = qs.order_by("-created_at")
    try:
        per_page = min(int(request.GET.get("per_page") or 25), 100)
    except ValueError:
        per_page = 25
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page") or 1)
    return Response(
        {
            "results": [
                _serialize_publicacio(p, for_staff=True) for p in page.object_list
            ],
            "page": page.number,
            "num_pages": paginator.num_pages,
            "total": paginator.count,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
            "estat_choices": list(Publicacio.ESTAT_CHOICES),
        }
    )


@api_view(["POST"])
@permission_classes([IsStaff])
def staff_publicacio_decidir(request: Request, pk: int) -> Response:
    """Publish, reject or unpublish a publication.

    Body: {action: "publicar" | "rebutjar" | "despublicar", notes_staff?}.
    """
    pub = get_object_or_404(Publicacio, pk=pk)
    data = request.data or {}
    action = (data.get("action") or "").strip()
    notes = (data.get("notes_staff") or "").strip()

    if action == "publicar":
        pub.estat = Publicacio.ESTAT_PUBLICAT
        pub.publicat_at = pub.publicat_at or timezone.now()
    elif action == "rebutjar":
        pub.estat = Publicacio.ESTAT_REBUTJAT
        pub.publicat_at = None
    elif action == "despublicar":
        pub.estat = Publicacio.ESTAT_ESBORRANY
        pub.publicat_at = None
    else:
        return Response({"error": "Acció no vàlida."}, status=400)

    pub.notes_staff = notes
    pub.save()
    return Response(_serialize_publicacio(pub, for_staff=True))


@api_view(["GET"])
@permission_classes([IsStaff])
def staff_directori_usuaris(request: Request) -> Response:
    """Staff view over every PerfilUsuari regardless of visible_directori."""
    qs = (
        PerfilUsuari.objects.select_related("usuari", "localitat")
        .annotate(n_publicacions=Count("usuari__publicacions"))
        .order_by("usuari__username")
    )
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(usuari__username__icontains=q)
            | Q(usuari__email__icontains=q)
            | Q(nom_public__icontains=q)
        )
    visible = request.GET.get("visible", "")
    if visible == "1":
        qs = qs.filter(visible_directori=True)
    elif visible == "0":
        qs = qs.filter(visible_directori=False)

    try:
        per_page = min(int(request.GET.get("per_page") or 30), 100)
    except ValueError:
        per_page = 30
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page") or 1)
    rows = []
    for p in page.object_list:
        loc = p.localitat
        rows.append(
            {
                "usuari_id": p.usuari_id,
                "username": p.usuari.username,
                "email": p.usuari.email,
                "nom_public": p.nom_public,
                "rol_musical": p.rol_musical,
                "obert_colaboracions": p.obert_colaboracions,
                "visible_directori": p.visible_directori,
                "onboarding_complet": p.onboarding_complet,
                "localitat": (
                    f"{loc.nom}, {loc.comarca} ({loc.territori_id})" if loc else ""
                ),
                "n_publicacions": p.n_publicacions,
                "is_staff": p.usuari.is_staff,
                "is_active": p.usuari.is_active,
            }
        )
    return Response(
        {
            "results": rows,
            "page": page.number,
            "num_pages": paginator.num_pages,
            "total": paginator.count,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
        }
    )


@api_view(["POST"])
@permission_classes([IsStaff])
def staff_directori_toggle_visible(request: Request, usuari_id: int) -> Response:
    p = get_object_or_404(PerfilUsuari, usuari_id=usuari_id)
    p.visible_directori = not p.visible_directori
    p.save(update_fields=["visible_directori", "updated_at"])
    return Response({"usuari_id": usuari_id, "visible_directori": p.visible_directori})
