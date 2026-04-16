import json
import logging

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import mail_admins, send_mail
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from ranking.models import RankingProvisional, RankingSetmanal

from .forms import RegistreForm, SollicitudGestioForm
from .models import PropostaArtista, UserArtista
from .tokens import email_verification_token

Usuari = get_user_model()
logger = logging.getLogger(__name__)


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
        return self.request.GET.get("next", "/compte/dashboard/")


class TQLogoutView(LogoutView):
    next_page = "/"


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

            with transaction.atomic():
                proposta = PropostaArtista.objects.create(
                    usuari=request.user,
                    nom=nom,
                    justificacio=justificacio,
                    deezer_ids=deezer_ids,
                    localitzacions_json=json.dumps(locs) if locs else "",
                    **social_data,
                )

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
