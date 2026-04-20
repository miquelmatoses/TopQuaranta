"""Staff-only endpoints for the React SPA.

One-file backend covering every /staff/* area so the React panel can
operate without falling back to the legacy Django templates. Grouped
by area with banner comments. All endpoints require `is_staff`.

Routes are wired in `web/api/urls.py`. The 2FA gate from
`web/views/staff/staff_required` is *not* re-applied here: we rely on
the same Django session that already passed the otp_login middleware.
An unverified staff session doesn't hold the `otp_device` attribute,
so `user.is_verified()` below enforces the same gate at the API edge.

The business logic calls the existing music services
(`aprovar_canco`, `rebutjar_canco`, `rebutjar_album`, `rebutjar_artista`,
`log_staff_action`) unchanged so the React flows behave identically
to the Django ones.
"""

from __future__ import annotations

import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, F, OuterRef, Q
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from comptes.models import Feedback, PropostaArtista, UserArtista
from music.audit import log_staff_action
from music.constants import MOTIUS_REBUIG, MOTIUS_VALIDS, TERRITORI_NOMS
from music.ml import recalcular_ml_si_cal
from music.models import (
    Album,
    Artista,
    ArtistaDeezer,
    ArtistaLocalitat,
    Canco,
    HistorialRevisio,
    Municipi,
    StaffAuditLog,
)
from music.services import (
    aprovar_canco,
    rebutjar_album,
    rebutjar_artista,
    rebutjar_canco,
)
from ranking.models import ConfiguracioGlobal, RankingProvisional, SenyalDiari

Usuari = get_user_model()


# ═════════════════════════════════════════════════════════════════════════
# Permission + shared helpers
# ═════════════════════════════════════════════════════════════════════════


class IsStaff(BasePermission):
    """Authenticated + is_staff + OTP-verified session."""

    message = "Staff access required."

    def has_permission(self, request, view):  # noqa: D401 — DRF signature
        user = request.user
        if not (user and user.is_authenticated and user.is_staff):
            return False
        # django-otp attaches is_verified(); missing attr means no OTP middleware.
        is_verified = getattr(user, "is_verified", None)
        return True if is_verified is None else bool(is_verified())


def _paginate(qs, request: Request, default_per_page: int = 50):
    """Return (page_obj, metadata dict) tuple for a queryset."""
    try:
        per_page = min(int(request.GET.get("per_page") or default_per_page), 200)
    except ValueError:
        per_page = default_per_page
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page") or 1)
    return page, {
        "page": page.number,
        "num_pages": paginator.num_pages,
        "total": paginator.count,
        "per_page": per_page,
        "has_next": page.has_next(),
        "has_previous": page.has_previous(),
    }


# ═════════════════════════════════════════════════════════════════════════
# Dashboard
# ═════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([IsStaff])
def dashboard(request: Request) -> Response:
    """Counters for every tool in one call."""
    return Response(
        {
            "artistes_pendents": Artista.objects.filter(
                aprovat=False, pendent_review=True
            ).count(),
            "cancons_no_verificades": Canco.objects.filter(
                verificada=False, activa=True
            ).count(),
            "propostes_obertes": PropostaArtista.objects.filter(
                estat=PropostaArtista.ESTAT_PENDENT
            ).count(),
            "solicituds_gestio_obertes": UserArtista.objects.filter(
                estat=UserArtista.ESTAT_PENDENT
            ).count(),
            "feedback_obert": Feedback.objects.filter(resolt=False).count(),
            "usuaris_total": Usuari.objects.filter(is_active=True).count(),
        }
    )


# ═════════════════════════════════════════════════════════════════════════
# Pendents — auto-discovered artists awaiting review
# ═════════════════════════════════════════════════════════════════════════


def _artista_card(a) -> dict:
    """Compact artist shape for staff tables (pendents + artistes)."""
    loc = a.localitats.select_related("municipi__territori").first()
    loc_out = None
    if loc:
        if loc.municipi:
            loc_out = {
                "municipi_id": loc.municipi.pk,
                "municipi_nom": loc.municipi.nom,
                "comarca": loc.municipi.comarca,
                "territori": loc.municipi.territori_id,
                "manual": "",
            }
        elif loc.localitat_manual:
            loc_out = {
                "municipi_id": None,
                "municipi_nom": "",
                "comarca": "",
                "territori": "ALT",
                "manual": loc.localitat_manual,
            }
    return {
        "pk": a.pk,
        "nom": a.nom,
        "slug": a.slug,
        "genere": a.genere or "",
        "aprovat": a.aprovat,
        "pendent_review": a.pendent_review,
        "auto_descobert": a.auto_descobert,
        "font_descoberta": a.font_descoberta or "",
        "deezer_ids": list(a.deezer_ids.values_list("deezer_id", flat=True)),
        "territoris": list(
            a.territoris.values_list("codi", flat=True).order_by("codi")
        ),
        "localitat": loc_out,
    }


@api_view(["GET"])
@permission_classes([IsStaff])
def pendents_list(request: Request) -> Response:
    qs = (
        Artista.objects.filter(aprovat=False, pendent_review=True)
        .prefetch_related("territoris", "deezer_ids", "localitats__municipi")
        .annotate(
            nb_verif_main=Count("cancons", filter=Q(cancons__verificada=True)),
            nb_verif_col=Count(
                "participacions", filter=Q(participacions__verificada=True)
            ),
        )
        .annotate(nb_verif=F("nb_verif_main") + F("nb_verif_col"))
        .order_by("-nb_verif", "nom")
    )
    cerca = (request.GET.get("q") or "").strip()
    if cerca:
        qs = qs.filter(nom__icontains=cerca)
    page, meta = _paginate(qs, request)
    rows = []
    for a in page.object_list:
        row = _artista_card(a)
        row["nb_verif"] = a.nb_verif
        rows.append(row)
    return Response({"results": rows, **meta})


@api_view(["POST"])
@permission_classes([IsStaff])
def pendent_aprovar(request: Request, pk: int) -> Response:
    """Approve a pending artist. Accepts deezer_id + municipi_id/comarca+localitat."""
    artista = get_object_or_404(Artista, pk=pk)
    data = request.data or {}

    deezer_id_raw = str(data.get("deezer_id", "")).strip()
    municipi_id = data.get("municipi_id")
    comarca = (data.get("comarca") or "").strip()
    localitat = (data.get("localitat") or "").strip()
    # Explicit shortcut used by the React cascade when territori=ALT:
    # there's no comarca/municipi then, just a free-text place name.
    manual_loc = (data.get("manual") or "").strip()

    cascade_selected = (
        bool(municipi_id) or (bool(comarca) and bool(localitat)) or bool(manual_loc)
    )
    has_existing_loc = artista.localitats.exists()
    if not cascade_selected and not has_existing_loc:
        return Response({"error": "Cal seleccionar un municipi"}, status=400)

    deezer_id: int | None = None
    if deezer_id_raw:
        try:
            deezer_id = int(deezer_id_raw)
        except ValueError:
            return Response({"error": "Deezer ID invàlid"}, status=400)

    audit_loc = None
    territori = None

    with transaction.atomic():
        if (
            deezer_id is not None
            and not artista.deezer_ids.filter(deezer_id=deezer_id).exists()
        ):
            try:
                with transaction.atomic():
                    ArtistaDeezer.objects.create(
                        artista=artista,
                        deezer_id=deezer_id,
                        principal=not artista.deezer_ids.exists(),
                    )
            except IntegrityError:
                owner = (
                    ArtistaDeezer.objects.filter(deezer_id=deezer_id)
                    .select_related("artista")
                    .first()
                )
                return Response(
                    {
                        "error": (
                            f"Deezer ID {deezer_id} ja pertany a "
                            f"«{owner.artista.nom if owner else '?'}». "
                            "Fusiona els dos artistes o canvia l'ID."
                        ),
                        "owner_pk": owner.artista.pk if owner else None,
                    },
                    status=409,
                )

        if cascade_selected:
            if municipi_id:
                try:
                    municipi = Municipi.objects.get(pk=int(municipi_id))
                except Municipi.DoesNotExist:
                    return Response({"error": "Municipi no trobat"}, status=404)
                ArtistaLocalitat.objects.create(artista=artista, municipi=municipi)
                audit_loc = f"{municipi.nom}, {municipi.comarca}"
                territori = municipi.territori_id
            elif manual_loc:
                ArtistaLocalitat.objects.create(
                    artista=artista,
                    municipi=None,
                    localitat_manual=manual_loc,
                )
                audit_loc = f"{manual_loc} (manual)"
                territori = "ALT"
            else:
                try:
                    municipi = Municipi.objects.get(nom=localitat, comarca=comarca)
                    ArtistaLocalitat.objects.create(artista=artista, municipi=municipi)
                    audit_loc = f"{municipi.nom}, {municipi.comarca}"
                    territori = municipi.territori_id
                except Municipi.DoesNotExist:
                    ArtistaLocalitat.objects.create(
                        artista=artista,
                        municipi=None,
                        localitat_manual=f"{localitat}, {comarca}",
                    )
                    audit_loc = f"{localitat}, {comarca} (manual)"
                    territori = "ALT"
        else:
            loc = artista.localitats.select_related("municipi__territori").first()
            if loc and loc.municipi:
                audit_loc = f"{loc.municipi.nom}, {loc.municipi.comarca} (existent)"
                territori = loc.municipi.territori_id
            elif loc:
                audit_loc = f"{loc.localitat_manual} (existent, manual)"
                territori = "ALT"

        artista.aprovat = True
        artista.pendent_review = False
        artista.save(update_fields=["aprovat", "pendent_review"])

    log_staff_action(
        request,
        "pendent_aprovar",
        target=artista,
        territori=territori,
        localitat=audit_loc,
        deezer_id_afegit=deezer_id,
    )
    return Response({"ok": True, "territori": territori})


@api_view(["POST"])
@permission_classes([IsStaff])
def pendent_descartar(request: Request, pk: int) -> Response:
    artista = get_object_or_404(Artista, pk=pk)
    has_verified = artista.cancons.filter(verificada=True).exists()
    if has_verified:
        artista.pendent_review = False
        artista.save(update_fields=["pendent_review"])
        recalcular_ml_si_cal()
        log_staff_action(
            request,
            "pendent_descartar",
            target=artista,
            action_taken="kept_pendent_review_false",
            reason="had verified tracks",
        )
        return Response({"ok": True, "action": "kept"})
    label = str(artista)
    pk_val = artista.pk
    artista.delete()
    log_staff_action(
        request,
        "pendent_descartar",
        target=None,
        action_taken="deleted",
        target_id_deleted=pk_val,
        target_label_deleted=label,
    )
    return Response({"ok": True, "action": "deleted"})


# ═════════════════════════════════════════════════════════════════════════
# Artistes — approved artists management
# ═════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([IsStaff])
def artistes_list(request: Request) -> Response:
    qs = Artista.objects.prefetch_related(
        "territoris", "localitats__municipi", "deezer_ids"
    )
    aprovat = request.GET.get("aprovat", "1")
    if aprovat == "1":
        qs = qs.filter(aprovat=True)
    elif aprovat == "0":
        qs = qs.filter(aprovat=False)
    deezer = request.GET.get("deezer", "")
    if deezer == "si":
        qs = qs.filter(deezer_ids__isnull=False)
    elif deezer == "no":
        qs = qs.filter(deezer_ids__isnull=True)
    territori = request.GET.get("territori", "")
    if territori:
        qs = qs.filter(territoris__codi=territori)
    cerca = (request.GET.get("q") or "").strip()
    if cerca:
        qs = qs.filter(nom__icontains=cerca)
    qs = qs.distinct().order_by(Lower("nom"))
    page, meta = _paginate(qs, request)
    return Response({"results": [_artista_card(a) for a in page.object_list], **meta})


@api_view(["GET"])
@permission_classes([IsStaff])
def artistes_search(request: Request) -> Response:
    """Light-weight lookup for the reassignment typeaheads.

    Returns up to 10 candidate artists (aprovats=True by default, but
    we surface pending/descartats too when the search is explicit, so
    staff can pick a pending artist to land a mis-assigned track on).
    """
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return Response({"results": []})
    qs = Artista.objects.filter(nom__icontains=q).order_by("-aprovat", "nom")[:10]
    return Response(
        {
            "results": [
                {
                    "pk": a.pk,
                    "nom": a.nom,
                    "slug": a.slug,
                    "aprovat": a.aprovat,
                    "pendent_review": a.pendent_review,
                }
                for a in qs
            ]
        }
    )


@api_view(["POST"])
@permission_classes([IsStaff])
def artista_crear(request: Request) -> Response:
    data = request.data or {}
    nom = (data.get("nom") or "").strip()
    if not nom:
        return Response({"error": "El nom és obligatori."}, status=400)
    lastfm_nom = (data.get("lastfm_nom") or "").strip() or nom
    deezer_raw = (data.get("deezer_id") or "").strip() if data.get("deezer_id") else ""
    deezer_id = None
    if deezer_raw:
        try:
            deezer_id = int(deezer_raw)
        except ValueError:
            return Response(
                {"error": "Deezer ID ha de ser un nombre enter."}, status=400
            )
    with transaction.atomic():
        artista = Artista.objects.create(
            nom=nom,
            lastfm_nom=lastfm_nom,
            aprovat=True,
            auto_descobert=False,
            font_descoberta="manual",
        )
        if deezer_id is not None:
            try:
                ArtistaDeezer.objects.create(
                    artista=artista, deezer_id=deezer_id, principal=True
                )
            except IntegrityError:
                return Response(
                    {"error": f"Deezer ID {deezer_id} ja pertany a un altre artista."},
                    status=409,
                )
        log_staff_action(request, "artista_crear", target=artista, deezer_id=deezer_id)
    return Response({"ok": True, "pk": artista.pk, "slug": artista.slug})


@api_view(["GET", "PATCH"])
@permission_classes([IsStaff])
def artista_detail(request: Request, pk: int) -> Response:
    artista = get_object_or_404(Artista, pk=pk)
    if request.method == "PATCH":
        data = request.data or {}
        simple_fields = [
            "nom",
            "lastfm_nom",
            "genere",
            "percentatge_femeni",
        ] + [f for f, _ in Artista.SOCIAL_LINK_FIELDS]
        for f in simple_fields:
            if f in data:
                setattr(artista, f, (data.get(f) or "").strip())
        if "aprovat" in data:
            artista.aprovat = bool(data["aprovat"])
            # Invariant enforced by `artista_no_aprovat_pendent_review`:
            # aprovat=True + pendent_review=True is not allowed. Clear
            # the queue flag so a PATCH that approves straight from the
            # edit page doesn't 500 on the CheckConstraint.
            if artista.aprovat and artista.pendent_review:
                artista.pendent_review = False
        artista.save()

        # Replace locations if sent (array of {municipi_id} or {manual}).
        if "localitats" in data:
            artista.localitats.all().delete()
            for loc in data["localitats"] or []:
                mid = loc.get("municipi_id")
                manual = (loc.get("manual") or "").strip()
                if mid:
                    try:
                        m = Municipi.objects.get(pk=int(mid))
                        ArtistaLocalitat.objects.create(artista=artista, municipi=m)
                    except (ValueError, Municipi.DoesNotExist):
                        pass
                elif manual:
                    ArtistaLocalitat.objects.create(
                        artista=artista, municipi=None, localitat_manual=manual
                    )

        # Replace Deezer IDs if sent (list of ints; first is principal).
        if "deezer_ids" in data:
            want = []
            for raw in data["deezer_ids"] or []:
                try:
                    want.append(int(raw))
                except (TypeError, ValueError):
                    pass
            existing = set(artista.deezer_ids.values_list("deezer_id", flat=True))
            want_set = set(want)
            if existing - want_set:
                artista.deezer_ids.filter(deezer_id__in=existing - want_set).delete()
            for i, dz_id in enumerate(want):
                if dz_id not in existing:
                    try:
                        ArtistaDeezer.objects.create(
                            artista=artista, deezer_id=dz_id, principal=(i == 0)
                        )
                    except IntegrityError:
                        pass
        log_staff_action(request, "artista_edit", target=artista)

    # Return full detail
    row = _artista_card(artista)
    row.update(
        {
            "lastfm_nom": artista.lastfm_nom or "",
            "percentatge_femeni": artista.percentatge_femeni or "",
            "social": {
                f: getattr(artista, f) or "" for f, _ in Artista.SOCIAL_LINK_FIELDS
            },
            "localitats": [
                {
                    "municipi_id": loc.municipi.pk if loc.municipi else None,
                    "municipi_nom": loc.municipi.nom if loc.municipi else "",
                    "comarca": loc.municipi.comarca if loc.municipi else "",
                    "territori": (loc.municipi.territori_id if loc.municipi else "ALT"),
                    "manual": loc.localitat_manual or "",
                }
                for loc in artista.localitats.select_related(
                    "municipi", "municipi__territori"
                ).all()
            ],
            "percentatge_choices": list(Artista.PERCENTATGE_FEMENI_CHOICES),
            "social_fields": list(Artista.SOCIAL_LINK_FIELDS),
        }
    )
    return Response(row)


# ═════════════════════════════════════════════════════════════════════════
# Cançons — track management
# ═════════════════════════════════════════════════════════════════════════


def _canco_row(c) -> dict:
    return {
        "pk": c.pk,
        "nom": c.nom,
        "slug": c.slug,
        "verificada": c.verificada,
        "activa": c.activa,
        "ml_classe": c.ml_classe or "",
        "ml_confianca": c.ml_confianca,
        "isrc": c.isrc or "",
        "deezer_id": c.deezer_id,
        "data_llancament": (
            c.data_llancament.isoformat() if c.data_llancament else None
        ),
        "lastfm_nom": c.lastfm_nom or "",
        "whisper_lang": c.whisper_lang or "",
        "artista": {"pk": c.artista_id, "nom": c.artista.nom if c.artista else ""},
        "album": (
            {"pk": c.album_id, "nom": c.album.nom, "slug": c.album.slug}
            if c.album
            else None
        ),
    }


@api_view(["GET"])
@permission_classes([IsStaff])
def cancons_list(request: Request) -> Response:
    qs = Canco.objects.select_related("artista", "album")
    verificada = request.GET.get("verificada", "0")
    if verificada == "0":
        qs = qs.filter(verificada=False, activa=True)
    elif verificada == "1":
        qs = qs.filter(verificada=True)
    ml_classe = request.GET.get("ml_classe", "")
    if ml_classe in ("A", "B", "C"):
        qs = qs.filter(ml_classe=ml_classe)
    whisper = request.GET.get("whisper", "")
    if whisper == "ca":
        qs = qs.filter(whisper_lang="ca")
    elif whisper == "no_ca":
        qs = qs.filter(whisper_processat_at__isnull=False).exclude(whisper_lang="ca")
    elif whisper == "pendent":
        qs = qs.filter(whisper_processat_at__isnull=True)
    # "Sense Deezer" — a verified track without a deezer_id is the
    # legacy/mis-ingest case worth auditing. `no` surfaces only those,
    # `si` only the tracks that do have an ID (rarely needed, handy
    # for QA).
    deezer = request.GET.get("deezer", "")
    if deezer == "no":
        qs = qs.filter(deezer_id__isnull=True)
    elif deezer == "si":
        qs = qs.filter(deezer_id__isnull=False)
    cerca = (request.GET.get("q") or "").strip()
    if cerca:
        qs = qs.filter(Q(nom__icontains=cerca) | Q(artista__nom__icontains=cerca))
    # Scope to a single artist (used by the "X cançons verificades" link
    # on the pendents page so staff can drill into exactly that list).
    artista_pk = request.GET.get("artista_pk", "")
    if artista_pk:
        try:
            qs = qs.filter(artista_id=int(artista_pk))
        except ValueError:
            pass
    # Sorting: `sort` accepts the same allow-list as the Django staff
    # view used to, prefixed with `-` for descending. Default keeps the
    # ML triage order so new users land on the highest-confidence work.
    sort_map = {
        "ml_confianca": "ml_confianca",
        "nom": "nom",
        "data_llancament": "data_llancament",
        "artista": "artista__nom",
        "album": "album__nom",
        "isrc": "isrc",
    }
    sort_raw = (request.GET.get("sort") or "-ml_confianca").strip()
    direction = ""
    key = sort_raw
    if sort_raw.startswith("-"):
        direction = "-"
        key = sort_raw[1:]
    if key not in sort_map:
        direction, key = "-", "ml_confianca"
    qs = qs.order_by(f"{direction}{sort_map[key]}", "nom")
    page, meta = _paginate(qs, request)
    return Response({"results": [_canco_row(c) for c in page.object_list], **meta})


@api_view(["POST"])
@permission_classes([IsStaff])
def cancons_accio(request: Request) -> Response:
    """Bulk aprovar / rebutjar. Body: {action, ids, motiu}."""
    data = request.data or {}
    action = data.get("action", "")
    ids = data.get("ids") or []
    if not ids:
        return Response({"error": "No has seleccionat cap cançó."}, status=400)
    qs = Canco.objects.filter(pk__in=ids).select_related("artista", "album")

    if action == "aprovar":
        with transaction.atomic():
            for c in qs:
                aprovar_canco(c)
                log_staff_action(request, "canco_aprovar", target=c)
        recalcular_ml_si_cal()
        return Response({"ok": True, "n": qs.count()})

    motiu = data.get("motiu", "")
    if motiu not in MOTIUS_VALIDS:
        return Response({"error": "Motiu invàlid."}, status=400)

    msgs: list[str] = []
    if action == "rebutjar":
        with transaction.atomic():
            if motiu == "artista_incorrecte":
                artista_ids = set(qs.values_list("artista_id", flat=True))
                for a in Artista.objects.filter(pk__in=artista_ids):
                    n = rebutjar_artista(a, motiu)
                    log_staff_action(
                        request,
                        "artista_rebutjar",
                        target=a,
                        motiu=motiu,
                        cancons_afectades=n,
                    )
                    msgs.append(f"{n} cançons de {a.nom}")
            elif motiu == "album_incorrecte":
                album_ids = set(qs.values_list("album_id", flat=True))
                for al in Album.objects.filter(pk__in=album_ids):
                    n = rebutjar_album(al, motiu)
                    log_staff_action(
                        request,
                        "canco_rebutjar_album",
                        target=al,
                        motiu=motiu,
                        cancons_afectades=n,
                    )
                    msgs.append(f"{n} cançons de l'àlbum {al.nom}")
            else:
                for c in qs:
                    rebutjar_canco(c, motiu)
                    log_staff_action(request, "canco_rebutjar", target=c, motiu=motiu)
                msgs.append(f"{qs.count()} cançons rebutjades")
        recalcular_ml_si_cal()
        return Response({"ok": True, "msg": "; ".join(msgs)})

    return Response({"error": "Acció desconeguda."}, status=400)


@api_view(["GET", "PATCH"])
@permission_classes([IsStaff])
def canco_detail(request: Request, pk: int) -> Response:
    canco = get_object_or_404(Canco.objects.select_related("artista", "album"), pk=pk)
    if request.method == "PATCH":
        data = request.data or {}
        if "nom" in data:
            canco.nom = (data.get("nom") or "").strip()
        if "isrc" in data:
            canco.isrc = (data.get("isrc") or "").strip()
        if "lastfm_nom" in data:
            canco.lastfm_nom = (data.get("lastfm_nom") or "").strip()
        if "verificada" in data:
            canco.verificada = bool(data["verificada"])
        if "activa" in data:
            canco.activa = bool(data["activa"])
        if "data_llancament" in data:
            raw = (data.get("data_llancament") or "").strip()
            # parse_date → date | None; avoids the "str has no isoformat"
            # 500 when the response serializer re-reads the field after save.
            canco.data_llancament = parse_date(raw) if raw else None
        if "deezer_id" in data:
            raw = str(data.get("deezer_id") or "").strip()
            if raw:
                try:
                    canco.deezer_id = int(raw)
                except ValueError:
                    return Response({"error": "Deezer ID invàlid."}, status=400)
            else:
                canco.deezer_id = None
        # Reassign to a different artist (when staff spots a mis-attribution).
        if "artista_pk" in data:
            raw = data.get("artista_pk")
            if raw in (None, ""):
                return Response({"error": "L'artista és obligatori."}, status=400)
            try:
                new_artista = Artista.objects.get(pk=int(raw))
            except (ValueError, Artista.DoesNotExist):
                return Response({"error": "Artista no trobat."}, status=404)
            if canco.artista_id != new_artista.pk:
                old_nom = canco.artista.nom if canco.artista else ""
                canco.artista = new_artista
                log_staff_action(
                    request,
                    "canco_edit",
                    target=canco,
                    field="artista",
                    old_artista=old_nom,
                    new_artista=new_artista.nom,
                )
        canco.save()
        log_staff_action(request, "canco_edit", target=canco)
    return Response(_canco_row(canco))


# ═════════════════════════════════════════════════════════════════════════
# Albums — list + simple edit
# ═════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([IsStaff])
def albums_list(request: Request) -> Response:
    """Album directory for staff. Filters: q, tipus, descartat, artista_pk."""
    qs = Album.objects.select_related("artista").annotate(
        n_cancons=Count("cancons"),
        n_verificades=Count("cancons", filter=Q(cancons__verificada=True)),
    )
    cerca = (request.GET.get("q") or "").strip()
    if cerca:
        qs = qs.filter(Q(nom__icontains=cerca) | Q(artista__nom__icontains=cerca))
    tipus = request.GET.get("tipus", "")
    if tipus in {"album", "single", "ep"}:
        qs = qs.filter(tipus=tipus)
    descartat = request.GET.get("descartat", "")
    if descartat == "1":
        qs = qs.filter(descartat=True)
    elif descartat == "0":
        qs = qs.filter(descartat=False)
    artista_pk = request.GET.get("artista_pk", "")
    if artista_pk:
        try:
            qs = qs.filter(artista_id=int(artista_pk))
        except ValueError:
            pass
    qs = qs.order_by("-data_llancament", "nom")
    page, meta = _paginate(qs, request)
    return Response(
        {
            "results": [
                {
                    "pk": a.pk,
                    "nom": a.nom,
                    "slug": a.slug,
                    "tipus": a.tipus,
                    "data_llancament": (
                        a.data_llancament.isoformat() if a.data_llancament else None
                    ),
                    "imatge_url": a.imatge_url or "",
                    "deezer_id": a.deezer_id,
                    "descartat": a.descartat,
                    "n_cancons": a.n_cancons,
                    "n_verificades": a.n_verificades,
                    "artista": {
                        "pk": a.artista_id,
                        "nom": a.artista.nom if a.artista else "",
                        "slug": a.artista.slug if a.artista else "",
                    },
                }
                for a in page.object_list
            ],
            **meta,
        }
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsStaff])
def album_detail(request: Request, pk: int) -> Response:
    album = get_object_or_404(Album.objects.select_related("artista"), pk=pk)
    if request.method == "PATCH":
        data = request.data or {}
        was_descartat = album.descartat
        if "nom" in data:
            album.nom = (data.get("nom") or "").strip()
        if "data_llancament" in data:
            raw = (data.get("data_llancament") or "").strip()
            # Parse to a real date object. Assigning the raw string works
            # for the SQL UPDATE (Django's DateField casts on write) but
            # leaves the in-memory attribute as a str, and the response
            # serializer below calls .isoformat() on it → 500. parse_date
            # returns None on empty or on invalid input.
            album.data_llancament = parse_date(raw) if raw else None
        if "tipus" in data:
            album.tipus = (data.get("tipus") or "").strip()
        if "deezer_id" in data:
            raw = str(data.get("deezer_id") or "").strip()
            album.deezer_id = int(raw) if raw else None
        if "imatge_url" in data:
            album.imatge_url = (data.get("imatge_url") or "").strip()
        if "descartat" in data:
            album.descartat = bool(data["descartat"])

        # Reassign to a different artist. `cascade_cancons` (default True)
        # also re-points every Canco whose current artista_id matches the
        # album's old artista_id — the common case after a mis-split. Set
        # to False to leave the tracks' attributions intact (rare, but
        # useful when an album mixes tracks from several artists).
        if "artista_pk" in data:
            raw = data.get("artista_pk")
            if raw in (None, ""):
                return Response({"error": "L'artista és obligatori."}, status=400)
            try:
                new_artista = Artista.objects.get(pk=int(raw))
            except (ValueError, Artista.DoesNotExist):
                return Response({"error": "Artista no trobat."}, status=404)
            if album.artista_id != new_artista.pk:
                old_id = album.artista_id
                old_nom = album.artista.nom if album.artista else ""
                album.artista = new_artista
                cancons_changed = 0
                if data.get("cascade_cancons", True):
                    cancons_changed = Canco.objects.filter(
                        album=album, artista_id=old_id
                    ).update(artista=new_artista)
                log_staff_action(
                    request,
                    "album_edit",
                    target=album,
                    field="artista",
                    old_artista=old_nom,
                    new_artista=new_artista.nom,
                    cancons_reassignades=cancons_changed,
                )
        album.save()
        log_staff_action(request, "album_edit", target=album)
        if album.descartat and not was_descartat:
            log_staff_action(request, "album_descartar", target=album)
    return Response(
        {
            "pk": album.pk,
            "nom": album.nom,
            "slug": album.slug,
            "data_llancament": (
                album.data_llancament.isoformat() if album.data_llancament else None
            ),
            "tipus": album.tipus or "",
            "deezer_id": album.deezer_id,
            "imatge_url": album.imatge_url or "",
            "descartat": album.descartat,
            "artista": {
                "pk": album.artista_id,
                "nom": album.artista.nom if album.artista else "",
                "slug": album.artista.slug if album.artista else "",
            },
            "cancons": [
                {
                    "pk": c.pk,
                    "nom": c.nom,
                    "slug": c.slug,
                    "verificada": c.verificada,
                }
                for c in album.cancons.order_by("nom").only(
                    "pk", "nom", "slug", "verificada"
                )
            ],
        }
    )


# ═════════════════════════════════════════════════════════════════════════
# Ranking provisional
# ═════════════════════════════════════════════════════════════════════════


RANKING_TERRITORIS = [
    (c, TERRITORI_NOMS[c])
    for c in ("CAT", "VAL", "BAL", "CNO", "AND", "FRA", "ALG", "CAR", "ALT", "PPCC")
]


@api_view(["GET"])
@permission_classes([IsStaff])
def ranking_list(request: Request) -> Response:
    territori = request.GET.get("territori", "CAT")
    if territori not in {c for c, _ in RANKING_TERRITORIS}:
        territori = "CAT"
    qs = (
        RankingProvisional.objects.filter(territori=territori)
        .select_related("canco", "canco__artista")
        .order_by("posicio")
    )
    return Response(
        {
            "territori": territori,
            "territoris": [{"codi": c, "nom": n} for c, n in RANKING_TERRITORIS],
            "motius": list(MOTIUS_REBUIG),
            "entries": [
                {
                    "pk": rp.pk,
                    "posicio": rp.posicio,
                    "canco_pk": rp.canco_id,
                    "canco_nom": rp.canco.nom if rp.canco else "",
                    "canco_slug": rp.canco.slug if rp.canco else None,
                    "artista_nom": (
                        rp.canco.artista.nom if rp.canco and rp.canco.artista else ""
                    ),
                    "artista_pk": (
                        rp.canco.artista_id if rp.canco and rp.canco.artista else None
                    ),
                    "lastfm_playcount": rp.lastfm_playcount,
                    "dies_en_top": rp.dies_en_top,
                }
                for rp in qs
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsStaff])
def ranking_accio(request: Request) -> Response:
    data = request.data or {}
    action = data.get("action", "")
    ids = data.get("ids") or []
    motiu = data.get("motiu", "")
    if not ids:
        return Response({"error": "No has seleccionat cap entrada."}, status=400)
    if motiu not in MOTIUS_VALIDS:
        return Response({"error": "Motiu invàlid."}, status=400)
    entries = RankingProvisional.objects.filter(pk__in=ids).select_related(
        "canco__artista", "canco__album"
    )
    if action == "rebutjar_canco":
        total = 0
        with transaction.atomic():
            for rp in entries:
                rebutjar_canco(rp.canco, motiu)
                log_staff_action(
                    request,
                    "canco_rebutjar",
                    target=rp.canco,
                    motiu=motiu,
                    source="provisional_ranking",
                )
                rp.delete()
                total += 1
        recalcular_ml_si_cal()
        return Response({"ok": True, "n": total})
    if action == "rebutjar_artista":
        artista_ids = set(entries.values_list("canco__artista_id", flat=True))
        total_cancons = 0
        with transaction.atomic():
            for a in Artista.objects.filter(pk__in=artista_ids):
                total_cancons += rebutjar_artista(a, motiu)
                log_staff_action(
                    request,
                    "artista_rebutjar",
                    target=a,
                    motiu=motiu,
                    source="provisional_ranking",
                )
            RankingProvisional.objects.filter(
                canco__artista_id__in=artista_ids
            ).delete()
        recalcular_ml_si_cal()
        return Response(
            {"ok": True, "n_artistes": len(artista_ids), "n_cancons": total_cancons}
        )
    return Response({"error": "Acció desconeguda."}, status=400)


# ═════════════════════════════════════════════════════════════════════════
# Propostes d'artistes
# ═════════════════════════════════════════════════════════════════════════


def _proposta_row(p) -> dict:
    return {
        "pk": p.pk,
        "nom": p.nom,
        "estat": p.estat,
        "usuari": {
            "pk": p.usuari_id,
            "email": p.usuari.email if p.usuari_id else "",
            "username": p.usuari.username if p.usuari_id else "",
        },
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "artista_creat": (
            {"pk": p.artista_creat.pk, "slug": p.artista_creat.slug}
            if p.artista_creat_id
            else None
        ),
    }


@api_view(["GET"])
@permission_classes([IsStaff])
def propostes_list(request: Request) -> Response:
    qs = PropostaArtista.objects.select_related("usuari", "artista_creat")
    estat = request.GET.get("estat", "")
    if estat in ("pendent", "aprovat", "rebutjat"):
        qs = qs.filter(estat=estat)
    qs = qs.order_by("-created_at")
    page, meta = _paginate(qs, request, default_per_page=25)
    return Response({"results": [_proposta_row(p) for p in page.object_list], **meta})


@api_view(["GET"])
@permission_classes([IsStaff])
def proposta_detail(request: Request, pk: int) -> Response:
    p = get_object_or_404(
        PropostaArtista.objects.select_related("usuari", "artista_creat"), pk=pk
    )
    localitzacions: list[str] = []
    for loc in p.localitzacions or []:
        if "municipi_id" in loc:
            try:
                m = Municipi.objects.get(pk=loc["municipi_id"])
                localitzacions.append(f"{m.nom}, {m.comarca} ({m.territori_id})")
            except Municipi.DoesNotExist:
                localitzacions.append(f"Municipi ID {loc['municipi_id']} (no trobat)")
        elif "manual" in loc:
            localitzacions.append(f"{loc['manual']} (manual)")
    row = _proposta_row(p)
    row.update(
        {
            "justificacio": p.justificacio or "",
            "localitzacions": localitzacions,
            "deezer_ids": p.get_deezer_id_list(),
            "social": {
                f: getattr(p, f, "") or ""
                for f, _ in Artista.SOCIAL_LINK_FIELDS
                if getattr(p, f, "")
            },
        }
    )
    return Response(row)


@api_view(["POST"])
@permission_classes([IsStaff])
def proposta_aprovar(request: Request, pk: int) -> Response:
    p = get_object_or_404(PropostaArtista.objects.select_related("usuari"), pk=pk)
    if p.estat != PropostaArtista.ESTAT_PENDENT:
        return Response({"error": "Ja processada."}, status=400)
    with transaction.atomic():
        artista = Artista.objects.create(
            nom=p.nom,
            lastfm_nom=p.nom,
            aprovat=True,
            auto_descobert=False,
            font_descoberta="proposta_usuari",
        )
        for f, _ in Artista.SOCIAL_LINK_FIELDS:
            val = getattr(p, f, "")
            if val:
                setattr(artista, f, val)
        artista.save()
        for i, dz in enumerate(p.get_deezer_id_list()):
            try:
                ArtistaDeezer.objects.create(
                    artista=artista, deezer_id=dz, principal=(i == 0)
                )
            except IntegrityError:
                pass
        for loc in p.localitzacions or []:
            if "municipi_id" in loc:
                try:
                    m = Municipi.objects.get(pk=loc["municipi_id"])
                    ArtistaLocalitat.objects.create(artista=artista, municipi=m)
                except Municipi.DoesNotExist:
                    pass
            elif "manual" in loc:
                ArtistaLocalitat.objects.create(
                    artista=artista, municipi=None, localitat_manual=loc["manual"]
                )
        p.estat = PropostaArtista.ESTAT_APROVAT
        p.artista_creat = artista
        p.save(update_fields=["estat", "artista_creat"])
    log_staff_action(
        request,
        "proposta_aprovar",
        target=p,
        artista_creat_id=artista.pk,
        artista_nom=artista.nom,
        usuari_proposant=p.usuari.email,
    )
    return Response({"ok": True, "artista_pk": artista.pk, "slug": artista.slug})


@api_view(["POST"])
@permission_classes([IsStaff])
def proposta_rebutjar(request: Request, pk: int) -> Response:
    p = get_object_or_404(PropostaArtista, pk=pk)
    p.estat = PropostaArtista.ESTAT_REBUTJAT
    p.save(update_fields=["estat"])
    log_staff_action(
        request,
        "proposta_rebutjar",
        target=p,
        artista_nom=p.nom,
        usuari_proposant=p.usuari.email if p.usuari_id else "",
    )
    return Response({"ok": True})


# ═════════════════════════════════════════════════════════════════════════
# Sol·licituds de gestió (UserArtista)
# ═════════════════════════════════════════════════════════════════════════


def _solicitud_row(ua) -> dict:
    return {
        "pk": ua.pk,
        "estat": ua.estat,
        "verificat": ua.verificat,
        "sollicitud_text": ua.sollicitud_text or "",
        "created_at": ua.created_at.isoformat() if ua.created_at else None,
        "usuari": {
            "pk": ua.usuari_id,
            "email": ua.usuari.email if ua.usuari_id else "",
            "username": ua.usuari.username if ua.usuari_id else "",
        },
        "artista": {
            "pk": ua.artista_id,
            "nom": ua.artista.nom if ua.artista_id else "",
            "slug": ua.artista.slug if ua.artista_id else "",
        },
    }


@api_view(["GET"])
@permission_classes([IsStaff])
def solicituds_list(request: Request) -> Response:
    qs = UserArtista.objects.select_related("usuari", "artista")
    verificat = request.GET.get("verificat", "")
    if verificat == "0":
        qs = qs.filter(verificat=False)
    elif verificat == "1":
        qs = qs.filter(verificat=True)
    qs = qs.order_by("-created_at")
    page, meta = _paginate(qs, request, default_per_page=25)
    return Response(
        {"results": [_solicitud_row(ua) for ua in page.object_list], **meta}
    )


@api_view(["POST"])
@permission_classes([IsStaff])
def solicitud_toggle(request: Request, pk: int) -> Response:
    ua = get_object_or_404(
        UserArtista.objects.select_related("usuari", "artista"), pk=pk
    )
    ua.verificat = not ua.verificat
    ua.estat = "aprovat" if ua.verificat else "pendent"
    ua.save(update_fields=["verificat", "estat"])
    log_staff_action(
        request,
        "sollicitud_aprovar" if ua.verificat else "sollicitud_rebutjar",
        target=ua,
        nou_estat=ua.estat,
        artista=ua.artista.nom,
        usuari=ua.usuari.email,
    )
    return Response({"ok": True, "estat": ua.estat, "verificat": ua.verificat})


@api_view(["POST"])
@permission_classes([IsStaff])
def solicitud_rebutjar(request: Request, pk: int) -> Response:
    ua = get_object_or_404(
        UserArtista.objects.select_related("usuari", "artista"), pk=pk
    )
    ua.estat = "rebutjat"
    ua.save(update_fields=["estat"])
    log_staff_action(
        request,
        "sollicitud_rebutjar",
        target=ua,
        artista=ua.artista.nom,
        usuari=ua.usuari.email,
    )
    return Response({"ok": True})


# ═════════════════════════════════════════════════════════════════════════
# Senyal diari (Last.fm raw feed)
# ═════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([IsStaff])
def senyal_list(request: Request) -> Response:
    qs = SenyalDiari.objects.select_related("canco", "canco__artista")
    data_filtre = request.GET.get("data", "")
    if data_filtre:
        qs = qs.filter(data=data_filtre)
    mena = request.GET.get("mena", "")
    if mena == "errors":
        qs = qs.filter(error=True)
    elif mena == "correccions":
        qs = qs.filter(corregit=True)
    elif mena == "confirmats":
        qs = qs.filter(canco__lastfm_confirmed=True)
    cerca = (request.GET.get("q") or "").strip()
    if cerca:
        qs = qs.filter(
            Q(canco__nom__icontains=cerca) | Q(canco__artista__nom__icontains=cerca)
        )
    qs = qs.order_by("-data")
    page, meta = _paginate(qs, request)
    rows = []
    for s in page.object_list:
        rows.append(
            {
                "pk": s.pk,
                "data": s.data.isoformat() if s.data else None,
                "canco_pk": s.canco_id,
                "canco_nom": s.canco.nom if s.canco else "",
                "canco_slug": s.canco.slug if s.canco else None,
                "artista_nom": (
                    s.canco.artista.nom if s.canco and s.canco.artista else ""
                ),
                "lastfm_playcount": s.lastfm_playcount,
                "lastfm_listeners": s.lastfm_listeners,
                "score_entrada": s.score_entrada,
                "error": s.error,
                "corregit": s.corregit,
                "lastfm_confirmed": (s.canco.lastfm_confirmed if s.canco else False),
            }
        )
    return Response({"results": rows, **meta})


@api_view(["POST"])
@permission_classes([IsStaff])
def senyal_acceptar_correccio(request: Request, canco_pk: int) -> Response:
    canco = get_object_or_404(Canco, pk=canco_pk)
    canco.lastfm_confirmed = True
    canco.save(update_fields=["lastfm_confirmed"])
    SenyalDiari.objects.filter(canco=canco, corregit=True).update(corregit=False)
    log_staff_action(
        request,
        "canco_edit",
        target=canco,
        field="lastfm_confirmed",
        new_value=True,
        source="senyal_accept_correction",
    )
    return Response({"ok": True})


# ═════════════════════════════════════════════════════════════════════════
# Historial (read-only)
# ═════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([IsStaff])
def historial_list(request: Request) -> Response:
    qs = HistorialRevisio.objects.all()
    decisio = request.GET.get("decisio", "")
    if decisio in ("aprovada", "rebutjada"):
        qs = qs.filter(decisio=decisio)
    motiu = request.GET.get("motiu", "")
    if motiu:
        qs = qs.filter(motiu=motiu)
    cerca = (request.GET.get("q") or "").strip()
    if cerca:
        qs = qs.filter(Q(canco_nom__icontains=cerca) | Q(artista_nom__icontains=cerca))
    qs = qs.order_by("-created_at")
    page, meta = _paginate(qs, request)
    return Response(
        {
            "motius": list(MOTIUS_REBUIG),
            "results": [
                {
                    "pk": h.pk,
                    "canco_nom": h.canco_nom or "",
                    "artista_nom": h.artista_nom or "",
                    "decisio": h.decisio,
                    "motiu": h.motiu or "",
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                }
                for h in page.object_list
            ],
            **meta,
        }
    )


# ═════════════════════════════════════════════════════════════════════════
# Configuració global
# ═════════════════════════════════════════════════════════════════════════


def _config_fields(config):
    out = []
    for field in ConfiguracioGlobal._meta.get_fields():
        if hasattr(field, "attname") and field.attname != "id":
            out.append(
                {
                    "name": field.attname,
                    "label": field.attname.replace("_", " ").title(),
                    "value": getattr(config, field.attname),
                    "help": getattr(field, "help_text", "") or "",
                    "type": field.get_internal_type(),
                }
            )
    return out


@api_view(["GET", "PATCH"])
@permission_classes([IsStaff])
def configuracio(request: Request) -> Response:
    config = ConfiguracioGlobal.load()
    if request.method == "PATCH":
        data = request.data or {}
        fields = [
            f
            for f in ConfiguracioGlobal._meta.get_fields()
            if hasattr(f, "attname") and f.attname != "id"
        ]
        before = {f.attname: getattr(config, f.attname) for f in fields}
        for f in fields:
            if f.attname not in data:
                continue
            raw = str(data.get(f.attname) or "").strip()
            if raw == "":
                continue
            try:
                setattr(config, f.attname, type(getattr(config, f.attname))(raw))
            except (TypeError, ValueError):
                return Response(
                    {"error": f"Valor invàlid per {f.attname}."}, status=400
                )
        try:
            config.save()
        except ValidationError as exc:
            return Response(
                {"error": "Validació fallada.", "details": exc.message_dict},
                status=400,
            )
        after = {f.attname: getattr(config, f.attname) for f in fields}
        diff = {
            n: {"before": str(before[n]), "after": str(after[n])}
            for n in before
            if str(before[n]) != str(after[n])
        }
        if diff:
            log_staff_action(
                request,
                "config_update",
                target=config,
                changed_fields=list(diff.keys()),
                diff=diff,
            )
    return Response({"fields": _config_fields(config)})


# ═════════════════════════════════════════════════════════════════════════
# Auditoria (StaffAuditLog)
# ═════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([IsStaff])
def auditlog(request: Request) -> Response:
    qs = StaffAuditLog.objects.select_related("actor").order_by("-created_at")
    action = request.GET.get("action", "")
    if action:
        qs = qs.filter(action=action)
    actor_email = (request.GET.get("actor") or "").strip()
    if actor_email:
        qs = qs.filter(actor__email__icontains=actor_email)
    cerca = (request.GET.get("q") or "").strip()
    if cerca:
        qs = qs.filter(target_label__icontains=cerca)
    page, meta = _paginate(qs, request)
    return Response(
        {
            "action_choices": [
                {"value": v, "label": lbl} for v, lbl in StaffAuditLog.ACTION_CHOICES
            ],
            "results": [
                {
                    "pk": r.pk,
                    "action": r.action,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "actor_email": r.actor.email if r.actor else "",
                    "target_type": r.target_type or "",
                    "target_id": r.target_id,
                    "target_label": r.target_label or "",
                    "metadata": r.metadata or {},
                }
                for r in page.object_list
            ],
            **meta,
        }
    )


# ═════════════════════════════════════════════════════════════════════════
# Usuaris
# ═════════════════════════════════════════════════════════════════════════


@api_view(["GET"])
@permission_classes([IsStaff])
def usuaris_list(request: Request) -> Response:
    totp_exists = TOTPDevice.objects.filter(user=OuterRef("pk"), confirmed=True)
    qs = Usuari.objects.annotate(
        n_propostes=Count("propostes_artista", distinct=True),
        n_sollicituds_aprovades=Count(
            "artistes_vinculats",
            filter=Q(artistes_vinculats__estat="aprovat"),
            distinct=True,
        ),
        has_totp=Exists(totp_exists),
    )
    estat = request.GET.get("estat", "")
    if estat == "actius":
        qs = qs.filter(is_active=True)
    elif estat == "inactius":
        qs = qs.filter(is_active=False)
    rol = request.GET.get("rol", "")
    if rol == "staff":
        qs = qs.filter(is_staff=True)
    elif rol == "usuari":
        qs = qs.filter(is_staff=False)
    cerca = (request.GET.get("q") or "").strip()
    if cerca:
        qs = qs.filter(Q(email__icontains=cerca) | Q(username__icontains=cerca))
    qs = qs.order_by("-date_joined")
    page, meta = _paginate(qs, request)
    return Response(
        {
            "results": [
                {
                    "pk": u.pk,
                    "email": u.email,
                    "username": u.username,
                    "is_active": u.is_active,
                    "is_staff": u.is_staff,
                    "has_totp": bool(u.has_totp),
                    "date_joined": (
                        u.date_joined.isoformat() if u.date_joined else None
                    ),
                    "last_login": (u.last_login.isoformat() if u.last_login else None),
                    "n_propostes": u.n_propostes,
                    "n_sollicituds_aprovades": u.n_sollicituds_aprovades,
                }
                for u in page.object_list
            ],
            **meta,
        }
    )


@api_view(["GET"])
@permission_classes([IsStaff])
def usuari_detail(request: Request, pk: int) -> Response:
    u = get_object_or_404(Usuari, pk=pk)
    propostes = list(
        PropostaArtista.objects.filter(usuari=u)
        .select_related("artista_creat")
        .order_by("-created_at")
    )
    sollicituds = list(
        UserArtista.objects.filter(usuari=u)
        .select_related("artista")
        .order_by("-created_at")
    )
    audit_sobre = (
        StaffAuditLog.objects.filter(target_type="usuari", target_id=u.pk)
        .select_related("actor")
        .order_by("-created_at")[:30]
    )
    audit_per = []
    if u.is_staff:
        audit_per = list(
            StaffAuditLog.objects.filter(actor=u).order_by("-created_at")[:30]
        )
    has_totp = TOTPDevice.objects.filter(user=u, confirmed=True).exists()
    return Response(
        {
            "pk": u.pk,
            "email": u.email,
            "username": u.username,
            "is_active": u.is_active,
            "is_staff": u.is_staff,
            "date_joined": u.date_joined.isoformat() if u.date_joined else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "has_totp": has_totp,
            "propostes": [_proposta_row(p) for p in propostes],
            "sollicituds": [_solicitud_row(s) for s in sollicituds],
            "audit_sobre": [
                {
                    "pk": r.pk,
                    "action": r.action,
                    "actor_email": r.actor.email if r.actor else "",
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "target_label": r.target_label or "",
                }
                for r in audit_sobre
            ],
            "audit_per_usuari": [
                {
                    "pk": r.pk,
                    "action": r.action,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "target_label": r.target_label or "",
                }
                for r in audit_per
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsStaff])
def usuari_toggle_actiu(request: Request, pk: int) -> Response:
    u = get_object_or_404(Usuari, pk=pk)
    if u.pk == request.user.pk:
        return Response({"error": "No pots desactivar-te a tu mateix."}, status=400)
    if u.is_staff:
        return Response(
            {
                "error": (
                    "No es pot desactivar un usuari staff des del panell. "
                    "Treu-li is_staff via SSH primer."
                )
            },
            status=400,
        )
    u.is_active = not u.is_active
    u.save(update_fields=["is_active"])
    action = "usuari_reactivar" if u.is_active else "usuari_desactivar"
    log_staff_action(
        request,
        action,
        target=u,
        email=u.email,
        nou_estat_actiu=u.is_active,
    )
    return Response({"ok": True, "is_active": u.is_active})


@api_view(["POST"])
@permission_classes([IsStaff])
def usuari_reset_2fa(request: Request, pk: int) -> Response:
    u = get_object_or_404(Usuari, pk=pk)
    totp_n = TOTPDevice.objects.filter(user=u).count()
    static_n = StaticDevice.objects.filter(user=u).count()
    if totp_n == 0 and static_n == 0:
        return Response({"ok": True, "msg": "L'usuari no té cap dispositiu 2FA."})
    TOTPDevice.objects.filter(user=u).delete()
    StaticDevice.objects.filter(user=u).delete()
    log_staff_action(
        request,
        "usuari_reset_2fa",
        target=u,
        email=u.email,
        totp_removed=totp_n,
        static_removed=static_n,
    )
    return Response({"ok": True, "totp_removed": totp_n, "static_removed": static_n})


# ═════════════════════════════════════════════════════════════════════════
# Feedback (staff-side review)
# ═════════════════════════════════════════════════════════════════════════


def _feedback_row(fb) -> dict:
    return {
        "pk": fb.pk,
        "url": fb.url,
        "target_type": fb.target_type,
        "target_pk": fb.target_pk,
        "target_slug": fb.target_slug or "",
        "target_label": fb.target_label or "",
        "missatge": fb.missatge,
        "resolt": fb.resolt,
        "notes_staff": fb.notes_staff or "",
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
        "resolt_at": fb.resolt_at.isoformat() if fb.resolt_at else None,
        "usuari": {
            "pk": fb.usuari_id,
            "email": fb.usuari.email if fb.usuari_id else "",
            "username": fb.usuari.username if fb.usuari_id else "",
        },
        "resolt_per": (
            {"pk": fb.resolt_per.pk, "email": fb.resolt_per.email}
            if fb.resolt_per_id
            else None
        ),
    }


@api_view(["GET"])
@permission_classes([IsStaff])
def feedback_list(request: Request) -> Response:
    qs = Feedback.objects.select_related("usuari", "resolt_per")
    resolt = request.GET.get("resolt", "0")
    if resolt == "0":
        qs = qs.filter(resolt=False)
    elif resolt == "1":
        qs = qs.filter(resolt=True)
    target_type = request.GET.get("target_type", "")
    if target_type in {t for t, _ in Feedback.TARGET_CHOICES}:
        qs = qs.filter(target_type=target_type)
    cerca = (request.GET.get("q") or "").strip()
    if cerca:
        qs = qs.filter(
            Q(missatge__icontains=cerca)
            | Q(target_label__icontains=cerca)
            | Q(usuari__email__icontains=cerca)
        )
    qs = qs.order_by("-created_at")
    page, meta = _paginate(qs, request)
    return Response({"results": [_feedback_row(fb) for fb in page.object_list], **meta})


@api_view(["POST"])
@permission_classes([IsStaff])
def feedback_resolve(request: Request, pk: int) -> Response:
    """Toggle a feedback entry's resolved state. Body: {resolt, notes_staff}."""
    from django.utils import timezone

    fb = get_object_or_404(Feedback, pk=pk)
    data = request.data or {}
    if "notes_staff" in data:
        fb.notes_staff = (data.get("notes_staff") or "").strip()
    if "resolt" in data:
        want = bool(data["resolt"])
        fb.resolt = want
        if want:
            fb.resolt_at = timezone.now()
            fb.resolt_per = request.user
        else:
            fb.resolt_at = None
            fb.resolt_per = None
    fb.save()
    log_staff_action(
        request,
        "feedback_resolt" if fb.resolt else "feedback_obert",
        target=fb,
        missatge_snippet=fb.missatge[:120],
    )
    return Response(_feedback_row(fb))
