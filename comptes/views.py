import base64
import json
import logging
from io import BytesIO

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.core.mail import mail_admins, send_mail
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django_otp import login as otp_login
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from ranking.models import RankingProvisional, RankingSetmanal

from .forms import RegistreForm, SollicitudGestioForm
from .models import PropostaArtista, UserArtista
from .tokens import email_verification_token

Usuari = get_user_model()
logger = logging.getLogger(__name__)

# S11: number of single-use backup codes issued on enrollment.
BACKUP_CODES_COUNT = 10


def accedir(request: HttpRequest) -> HttpResponse:
    """Combined register/login entry page for anonymous users."""
    if request.user.is_authenticated:
        return redirect("comptes:dashboard")
    return render(request, "comptes/accedir.html")


def registre(request: HttpRequest) -> HttpResponse:
    """User registration: create inactive account and send verification email.

    Anti-enumeration (S5): we always show the same "check your email" page
    whether the address is new or already registered. If the email is taken
    we silently skip user creation and the verification mail, so an attacker
    cannot use the registration form to map existing accounts.
    """
    if request.user.is_authenticated:
        return redirect("comptes:dashboard")

    if request.method == "POST":
        form = RegistreForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            if not Usuari.objects.filter(email=email).exists():
                user = form.save()
                _send_verification_email(request, user)
            else:
                logger.info("Registration for existing email ignored: %s", email)
            return render(request, "comptes/registre_ok.html")
    else:
        form = RegistreForm()

    return render(request, "comptes/registre.html", {"form": form})


def _send_verification_email(request: HttpRequest, user) -> None:
    """Send email with activation link."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    link = request.build_absolute_uri(f"/compte/activar/{uid}/{token}/")
    subject = "Activa el teu compte TopQuaranta"
    body = f"Hola,\n\nActiva el teu compte fent clic aquí:\n{link}\n\nTopQuaranta"
    try:
        send_mail(subject, body, None, [user.email])
    except Exception:
        logger.exception("Failed to send verification email to %s", user.email)


def activar(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    """Activate user account from email verification link."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = Usuari.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Usuari.DoesNotExist):
        user = None

    if user and email_verification_token.check_token(user, token):
        user.is_active = True
        user.save(update_fields=["is_active"])
        login(request, user)
        return redirect("comptes:dashboard")

    return render(request, "comptes/activar_error.html")


class TQLoginView(LoginView):
    template_name = "comptes/login.html"
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        """Route staff through 2FA after successful password auth.

        S11: when a staff user logs in we distinguish three cases:

        1. User has NO confirmed TOTP device yet → send to enrollment.
        2. User has a confirmed device → send to the 2FA challenge with the
           intended destination in ?next=, session NOT yet marked verified.
        3. User is not staff → unchanged — password alone is sufficient.

        Non-staff users never see the 2FA pages. If 2FA is ever required for
        regular users, flip the branch here.
        """
        user = self.request.user
        next_url = self.request.GET.get("next") or self.request.POST.get("next") \
                   or "/compte/dashboard/"

        if user.is_staff:
            has_confirmed = TOTPDevice.objects.filter(
                user=user, confirmed=True,
            ).exists()
            if not has_confirmed:
                return f"/compte/2fa/configurar/?next={next_url}"
            return f"/compte/2fa/verificar/?next={next_url}"
        return next_url


class TQLogoutView(LogoutView):
    next_page = "/"


# ── S11 · 2FA (TOTP + backup codes) ──
#
# Flow:
#   Enrollment: /compte/2fa/configurar/
#     GET  → create an unconfirmed TOTPDevice, render a QR code.
#     POST → verify the 6-digit token; on success, mark the device
#            confirmed, create 10 single-use backup codes, and show them
#            ONCE. Session is marked OTP-verified.
#
#   Challenge: /compte/2fa/verificar/
#     GET  → render the code input.
#     POST → accept either a TOTP token or a StaticDevice backup code.
#            On success, mark the session verified and redirect to ?next=.
#
#   Management: /compte/2fa/
#     Shows device status, offers regenerate-backup-codes and remove-device
#     actions. Both require is_verified() in this session (i.e. the user
#     must have done 2FA already; you can't reset 2FA just by logging in).


def _generate_backup_codes(user) -> list[str]:
    """Replace any existing static device with a fresh set of 10 single-use codes.
    Returns the plain-text codes to show to the user ONCE.
    """
    # Remove any previous static device (we only keep one)
    StaticDevice.objects.filter(user=user).delete()
    device = StaticDevice.objects.create(user=user, name="backup-codes")
    codes = []
    for _ in range(BACKUP_CODES_COUNT):
        token = StaticToken.random_token()
        device.token_set.create(token=token)
        codes.append(token)
    return codes


@login_required(login_url="/compte/login/")
def dos_fa_configurar(request: HttpRequest) -> HttpResponse:
    """S11a · TOTP enrollment.

    Reuses an existing unconfirmed device if the user reloads; generates a
    new one otherwise. On successful token verification, we create the
    backup codes and show them exactly once.
    """
    user = request.user

    # Already enrolled → nothing to do, send to management page.
    if TOTPDevice.objects.filter(user=user, confirmed=True).exists():
        return redirect("comptes:dos_fa_gestio")

    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(user=user, name="default", confirmed=False)

    error = None
    backup_codes = None
    if request.method == "POST":
        token = (request.POST.get("token") or "").strip().replace(" ", "")
        if device.verify_token(token):
            device.confirmed = True
            device.save()
            backup_codes = _generate_backup_codes(user)
            # Mark this session verified so the user doesn't get bounced
            # to /verificar/ straight after enrollment.
            otp_login(request, device)
            logger.info("2FA enrolled for %s", user.email)
        else:
            error = "Codi incorrecte. Torna-ho a provar."

    # Build provisioning URI + QR image
    uri = device.config_url  # otpauth://totp/...?issuer=TopQuaranta
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return render(request, "comptes/dos_fa_configurar.html", {
        "qr_b64": qr_b64,
        "secret": device.bin_key.hex().upper(),
        "error": error,
        "backup_codes": backup_codes,
    })


@login_required(login_url="/compte/login/")
def dos_fa_verificar(request: HttpRequest) -> HttpResponse:
    """S11a · challenge screen — accepts TOTP or a single-use backup code."""
    user = request.user
    next_url = request.GET.get("next") or request.POST.get("next") \
               or "/compte/dashboard/"

    # If the session is already verified, skip straight to destination.
    if user.is_verified():
        return redirect(next_url)

    # Should not happen, but guard: if no device exists, send to enrollment.
    if not TOTPDevice.objects.filter(user=user, confirmed=True).exists():
        return redirect("comptes:dos_fa_configurar")

    error = None
    if request.method == "POST":
        token = (request.POST.get("token") or "").strip().replace(" ", "")
        verified_device = None
        # Try TOTP devices first
        for d in TOTPDevice.objects.filter(user=user, confirmed=True):
            if d.verify_token(token):
                verified_device = d
                break
        # Then backup codes (StaticDevice)
        if verified_device is None:
            for d in StaticDevice.objects.filter(user=user, confirmed=True):
                if d.verify_token(token):
                    verified_device = d
                    break
        if verified_device is not None:
            otp_login(request, verified_device)
            logger.info("2FA verified for %s (%s)", user.email, verified_device.name)
            return redirect(next_url)
        else:
            error = "Codi incorrecte."
            logger.warning("2FA failed for %s", user.email)

    return render(request, "comptes/dos_fa_verificar.html", {
        "error": error,
        "next": next_url,
    })


@login_required(login_url="/compte/login/")
def dos_fa_gestio(request: HttpRequest) -> HttpResponse:
    """S11c · status page + manage backup codes + remove device."""
    user = request.user
    has_totp = TOTPDevice.objects.filter(user=user, confirmed=True).exists()
    has_backup = StaticDevice.objects.filter(
        user=user, token_set__isnull=False,
    ).exists()

    new_codes = None
    if request.method == "POST":
        # Mutations require the session be 2FA-verified.
        if not user.is_verified():
            return redirect(
                f"/compte/2fa/verificar/?next=/compte/2fa/"
            )
        action = request.POST.get("action", "")
        if action == "regenerar_codis":
            new_codes = _generate_backup_codes(user)
            messages.success(
                request,
                "Codis de recuperació regenerats. Desa'ls ara — no podràs "
                "tornar-los a veure.",
            )
        elif action == "eliminar_dispositiu":
            # Only allow if user supplied their password again
            password = request.POST.get("password", "")
            if user.check_password(password):
                TOTPDevice.objects.filter(user=user).delete()
                StaticDevice.objects.filter(user=user).delete()
                messages.success(
                    request, "Dispositiu 2FA eliminat. Hauràs de tornar a configurar-lo.",
                )
                return redirect("comptes:dos_fa_configurar")
            else:
                messages.error(request, "Contrasenya incorrecta.")

    return render(request, "comptes/dos_fa_gestio.html", {
        "has_totp": has_totp,
        "has_backup": has_backup,
        "is_verified": user.is_verified(),
        "new_codes": new_codes,
    })


@login_required(login_url="/compte/login/")
def dashboard(request: HttpRequest) -> HttpResponse:
    """User dashboard — card-based landing page with two solicitud flows."""
    gestio_list = list(
        UserArtista.objects.filter(usuari=request.user)
        .select_related("artista")
        .order_by("-created_at")
    )
    propostes_list = list(
        PropostaArtista.objects.filter(usuari=request.user)
        .select_related("artista_creat")
        .order_by("-created_at")
    )
    # For the artist portal card, find first verified link
    artista_verificat = next(
        (ua for ua in gestio_list if ua.verificat), None
    )

    return render(request, "comptes/dashboard.html", {
        "gestio_list": gestio_list,
        "propostes_list": propostes_list,
        "artista_verificat": artista_verificat,
    })


@login_required(login_url="/compte/login/")
def perfil(request: HttpRequest) -> HttpResponse:
    """User profile page with account details and artist stats."""
    user_artista = (
        UserArtista.objects.filter(usuari=request.user, verificat=True)
        .select_related("artista")
        .first()
    )

    stats = None
    if user_artista:
        artista = user_artista.artista
        ranking_qs = RankingSetmanal.objects.filter(canco__artista=artista)
        setmanes = ranking_qs.values("setmana").distinct().count()
        millor = ranking_qs.order_by("posicio").values_list("posicio", flat=True).first()
        cancons = ranking_qs.values("canco_id").distinct().count()
        territoris = ranking_qs.values("territori").distinct().count()
        stats = {
            "setmanes_al_ranking": setmanes,
            "millor_posicio": millor,
            "cancons_al_ranking": cancons,
            "territoris_presents": territoris,
        }

    return render(request, "comptes/perfil.html", {
        "user_artista": user_artista,
        "stats": stats,
    })


@login_required(login_url="/compte/login/")
def sollicitud_gestio(request: HttpRequest) -> HttpResponse:
    """Request management of an existing artist."""
    if request.method == "POST":
        form = SollicitudGestioForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                ua = form.save(commit=False)
                ua.usuari = request.user
                ua.save()
            try:
                _notify_admins("gestió", ua.artista.nom, request.user.email, ua.sollicitud_text)
            except Exception as exc:
                logger.warning("Admin notification skipped (gestió): %s", exc)
            return redirect("comptes:dashboard")
    else:
        form = SollicitudGestioForm()

    # Previous requests
    historial = list(
        UserArtista.objects.filter(usuari=request.user)
        .select_related("artista")
        .order_by("-created_at")
    )

    return render(request, "comptes/sollicitud_gestio.html", {
        "form": form,
        "historial": historial,
    })


@login_required(login_url="/compte/login/")
def sollicitud_proposta(request: HttpRequest) -> HttpResponse:
    """Propose a new artist not yet in the system."""
    if request.method == "POST":
        nom = request.POST.get("nom", "").strip()
        justificacio = request.POST.get("justificacio", "").strip()

        errors = []
        if not nom:
            errors.append("El nom de l'artista és obligatori.")
        if len(justificacio) < 20:
            errors.append("La justificació ha de tenir almenys 20 caràcters.")

        if not errors:
            # Collect social links
            social_fields = [
                "spotify_url", "viasona_url", "web_url", "bandcamp_url",
                "youtube_url", "viquipedia_url", "soundcloud_url",
                "tiktok_url", "facebook_url",
            ]
            social_data = {}
            for field in social_fields:
                val = request.POST.get(field, "").strip()
                if val:
                    social_data[field] = val

            # Collect Deezer IDs
            deezer_raw = request.POST.getlist("deezer_ids")
            deezer_ids = ",".join(d.strip() for d in deezer_raw if d.strip())

            # Collect locations
            loc_municipi_ids = request.POST.getlist("loc_municipi_id")
            loc_manuals = request.POST.getlist("loc_manual")
            locs = []
            for i, mid in enumerate(loc_municipi_ids):
                mid = mid.strip()
                manual = loc_manuals[i].strip() if i < len(loc_manuals) else ""
                if mid:
                    locs.append({"municipi_id": int(mid)})
                elif manual:
                    locs.append({"manual": manual})

            # S8: run field validators explicitly. Model.objects.create()
            # does NOT call full_clean(); without this, URL scheme restrictions
            # on social_data would be ignored.
            proposta = PropostaArtista(
                usuari=request.user,
                nom=nom,
                justificacio=justificacio,
                deezer_ids=deezer_ids,
                localitzacions_json=json.dumps(locs) if locs else "",
                **social_data,
            )
            try:
                proposta.full_clean()
            except ValidationError as exc:
                for field, msgs in exc.message_dict.items():
                    for msg in msgs:
                        errors.append(f"{field}: {msg}")
                return render(request, "comptes/sollicitud_proposta.html", {
                    "errors": errors, "historial": [],
                    "form_data": request.POST,
                })
            with transaction.atomic():
                proposta.save()

            try:
                _notify_admins("proposta", nom, request.user.email, justificacio)
            except Exception as exc:
                logger.warning("Admin notification skipped (proposta): %s", exc)
            return redirect("comptes:dashboard")

        # Re-render with errors
        return render(request, "comptes/sollicitud_proposta.html", {
            "errors": errors,
            "historial": list(
                PropostaArtista.objects.filter(usuari=request.user)
                .order_by("-created_at")
            ),
        })

    # GET
    historial = list(
        PropostaArtista.objects.filter(usuari=request.user)
        .select_related("artista_creat")
        .order_by("-created_at")
    )

    return render(request, "comptes/sollicitud_proposta.html", {
        "errors": [],
        "historial": historial,
    })


def _notify_admins(tipus: str, artista_nom: str, email: str, text: str) -> None:
    """Send email to ADMINS when a new request is created."""
    subject = f"Nova sol\u00b7licitud ({tipus}): {artista_nom}"
    body = (
        f"Tipus: {tipus}\n"
        f"Usuari: {email}\n"
        f"Artista: {artista_nom}\n"
        f"Justificació: {text}\n\n"
        f"Gestiona a: https://www.topquaranta.cat/staff/verificacio/"
    )
    try:
        mail_admins(subject, body)
    except Exception as exc:
        # SMTP not configured in this environment — log and continue.
        logger.warning(
            "Admin email skipped for %s '%s': %s", tipus, artista_nom, exc,
        )


@login_required(login_url="/compte/login/")
def portal_artista(request: HttpRequest) -> HttpResponse:
    """Verified artist dashboard with ranking data."""
    # Find the first verified artist link
    ua = (
        UserArtista.objects.filter(usuari=request.user, verificat=True)
        .select_related("artista")
        .first()
    )
    if not ua:
        return redirect("comptes:sollicitud_gestio")

    artista = ua.artista
    territoris = artista.get_territoris()

    # Last 10 weeks in RankingSetmanal
    historial = (
        RankingSetmanal.objects.filter(canco__artista=artista)
        .select_related("canco", "canco__album")
        .order_by("-setmana", "territori", "posicio")[:50]
    )
    setmanes: dict = {}
    for entry in historial:
        setmanes.setdefault(entry.setmana, []).append(entry)
    historial_setmanes = sorted(setmanes.items(), reverse=True)[:10]

    # Weekly position evolution for CSS chart (last 10 weeks, best position per week)
    evolucio = []
    for setmana, entries in historial_setmanes:
        best = min(e.posicio for e in entries)
        # Invert: position 1 → 100%, position 40 → 2.5%
        height_pct = round((41 - best) / 40 * 100)
        evolucio.append({"setmana": setmana, "posicio": best, "height": height_pct})
    evolucio.reverse()

    # Current provisional ranking
    provisional = list(
        RankingProvisional.objects.filter(canco__artista=artista)
        .select_related("canco", "canco__album")
        .order_by("posicio")
    )

    # Songs pending verification
    pendents = artista.cancons.filter(verificada=False).order_by("-data_llancament")[:20]

    return render(request, "comptes/portal_artista.html", {
        "artista": artista,
        "territoris": territoris,
        "historial_setmanes": historial_setmanes,
        "evolucio": evolucio,
        "provisional": provisional,
        "pendents": pendents,
    })
