"""Staff views for user management (read-heavy, mutation-poor).

Visibility of the ~N registered users plus two safe-to-flip mutations:
  * is_active (deactivate spam / abusive accounts)
  * reset 2FA (equivalent to `manage.py reset_2fa`)

Intentionally NOT exposed from the UI:
  * toggling is_staff — remains a deliberate SSH-only operation so a
    compromised staff session can't self-elevate or create new admins.
  * password reset of other users — end-users go through their own flow.
  * viewing / exporting email lists beyond the screen — no bulk export.

All mutations log through music.audit.log_staff_action to make this
page itself auditable via /staff/auditlog/.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from comptes.models import PropostaArtista, UserArtista
from music.audit import log_staff_action
from music.models import StaffAuditLog

from . import apply_ordering, paginate, staff_required

Usuari = get_user_model()


USUARIS_ORDER_FIELDS = {
    "email": "email",
    "username": "username",
    "registrat": "date_joined",
    "ultim": "last_login",
}


@staff_required
def llista(request: HttpRequest) -> HttpResponse:
    """List registered users with status counts.

    Annotates #propostes_total, #sollicituds_aprovades and a has_totp flag
    (only meaningful for staff users). Keeps the queryset lean — no FK
    data is pulled here beyond the scalar counts.
    """
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

    cerca = request.GET.get("q", "").strip()
    if cerca:
        qs = qs.filter(Q(email__icontains=cerca) | Q(username__icontains=cerca))

    qs, current_order, current_dir = apply_ordering(
        request,
        qs,
        USUARIS_ORDER_FIELDS,
        default="-date_joined",
    )
    page = paginate(request, qs, per_page=50)

    return render(
        request,
        "web/staff/usuaris.html",
        {
            "staff_section": "usuaris",
            "page": page,
            "estat": estat,
            "rol": rol,
            "cerca": cerca,
            "current_order": current_order,
            "current_dir": current_dir,
        },
    )


@staff_required
def detall(request: HttpRequest, pk: int) -> HttpResponse:
    """Full view of one user: propostes, sol·licituds, verified artists, audit."""
    usuari = get_object_or_404(Usuari, pk=pk)

    propostes = list(
        PropostaArtista.objects.filter(usuari=usuari)
        .select_related("artista_creat")
        .order_by("-created_at")
    )
    sollicituds = list(
        UserArtista.objects.filter(usuari=usuari)
        .select_related("artista")
        .order_by("-created_at")
    )
    artistes_verificats = [ua.artista for ua in sollicituds if ua.verificat]

    # Staff audit rows ABOUT this user (target_type='usuari' with matching pk).
    audit_sobre = (
        StaffAuditLog.objects.filter(
            target_type="usuari",
            target_id=usuari.pk,
        )
        .select_related("actor")
        .order_by("-created_at")[:30]
    )

    # Staff audit rows the user themselves performed (if they are staff).
    audit_per_usuari = None
    if usuari.is_staff:
        audit_per_usuari = StaffAuditLog.objects.filter(
            actor=usuari,
        ).order_by(
            "-created_at"
        )[:30]

    has_totp = TOTPDevice.objects.filter(user=usuari, confirmed=True).exists()

    return render(
        request,
        "web/staff/usuari_detall.html",
        {
            "staff_section": "usuaris",
            "usuari": usuari,
            "propostes": propostes,
            "sollicituds": sollicituds,
            "artistes_verificats": artistes_verificats,
            "audit_sobre": audit_sobre,
            "audit_per_usuari": audit_per_usuari,
            "has_totp": has_totp,
        },
    )


@staff_required
def toggle_actiu(request: HttpRequest, pk: int) -> HttpResponse:
    """Toggle is_active for a user. Never self-target (UI prevents it too)."""
    if request.method != "POST":
        return redirect("staff:usuaris")

    usuari = get_object_or_404(Usuari, pk=pk)

    if usuari.pk == request.user.pk:
        messages.error(request, "No pots desactivar-te a tu mateix.")
        return redirect("staff:usuari_detall", pk=pk)

    if usuari.is_staff:
        messages.error(
            request,
            "No es pot desactivar un usuari staff des del panell. "
            "Cal treure-li primer l'atribut is_staff via SSH.",
        )
        return redirect("staff:usuari_detall", pk=pk)

    usuari.is_active = not usuari.is_active
    usuari.save(update_fields=["is_active"])

    action = "usuari_reactivar" if usuari.is_active else "usuari_desactivar"
    log_staff_action(
        request,
        action,
        target=usuari,
        email=usuari.email,
        nou_estat_actiu=usuari.is_active,
    )

    estat_text = "reactivat" if usuari.is_active else "desactivat"
    messages.success(request, f"Usuari {usuari.email} {estat_text}.")
    return redirect("staff:usuari_detall", pk=pk)


@staff_required
def reset_2fa(request: HttpRequest, pk: int) -> HttpResponse:
    """Remove TOTP and backup-codes devices from a user.

    Staff self-reset is allowed; staff losing their own phone without
    backup codes still has the SSH `manage.py reset_2fa` escape hatch,
    but letting a verified session reset itself is fine too — the
    session is already authenticated + OTP-verified at this point.
    """
    if request.method != "POST":
        return redirect("staff:usuaris")

    usuari = get_object_or_404(Usuari, pk=pk)

    totp_n = TOTPDevice.objects.filter(user=usuari).count()
    static_n = StaticDevice.objects.filter(user=usuari).count()

    if totp_n == 0 and static_n == 0:
        messages.info(request, f"{usuari.email} no té cap dispositiu 2FA.")
        return redirect("staff:usuari_detall", pk=pk)

    TOTPDevice.objects.filter(user=usuari).delete()
    StaticDevice.objects.filter(user=usuari).delete()

    log_staff_action(
        request,
        "usuari_reset_2fa",
        target=usuari,
        email=usuari.email,
        totp_removed=totp_n,
        static_removed=static_n,
    )
    messages.success(
        request,
        f"2FA eliminat per a {usuari.email}. Hauran de tornar a enrolar-se.",
    )
    return redirect("staff:usuari_detall", pk=pk)
