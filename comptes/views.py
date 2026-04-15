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

from .forms import RegistreForm, SollicitudArtistaForm
from .models import UserArtista
from .tokens import email_verification_token

Usuari = get_user_model()
logger = logging.getLogger(__name__)


def registre(request: HttpRequest) -> HttpResponse:
    """User registration: create inactive account and send verification email."""
    if request.user.is_authenticated:
        return redirect("comptes:dashboard")

    if request.method == "POST":
        form = RegistreForm(request.POST)
        if form.is_valid():
            user = form.save()
            _send_verification_email(request, user)
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
    """User dashboard showing account info and artist verification status."""
    user_artista = UserArtista.objects.filter(usuari=request.user).select_related("artista").first()
    return render(request, "comptes/dashboard.html", {
        "user_artista": user_artista,
    })


@login_required(login_url="/compte/login/")
def sollicitud_artista(request: HttpRequest) -> HttpResponse:
    """Request artist verification: select artist and provide justification."""
    existing = UserArtista.objects.filter(usuari=request.user).select_related("artista").first()
    if existing:
        return render(request, "comptes/sollicitud_status.html", {
            "user_artista": existing,
        })

    if request.method == "POST":
        form = SollicitudArtistaForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                ua = form.save(commit=False)
                ua.usuari = request.user
                ua.save()
            _notify_admins_new_sollicitud(ua)
            return render(request, "comptes/sollicitud_status.html", {
                "user_artista": ua,
            })
    else:
        form = SollicitudArtistaForm()

    return render(request, "comptes/sollicitud.html", {"form": form})


def _notify_admins_new_sollicitud(ua: UserArtista) -> None:
    """Send email to ADMINS when a new artist verification request is created."""
    subject = f"Nova sol·licitud artista: {ua.artista.nom}"
    body = (
        f"Usuari: {ua.usuari.email}\n"
        f"Artista: {ua.artista.nom}\n"
        f"Justificació: {ua.sollicitud_text}\n\n"
        f"Verifica a: https://www.topquaranta.cat/nou-admin/"
    )
    try:
        mail_admins(subject, body)
    except Exception:
        logger.exception("Failed to send admin notification for UserArtista %s", ua.pk)


@login_required(login_url="/compte/login/")
def portal_artista(request: HttpRequest) -> HttpResponse:
    """Verified artist dashboard with ranking data."""
    ua = UserArtista.objects.filter(usuari=request.user).select_related("artista").first()
    if not ua:
        return redirect("comptes:sollicitud_artista")
    if not ua.verificat:
        return render(request, "comptes/artista_pendent.html", status=403)

    artista = ua.artista
    territoris = artista.get_territoris()

    # Last 10 weeks in RankingSetmanal
    historial = (
        RankingSetmanal.objects.filter(canco__artista=artista)
        .select_related("canco")
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
        .select_related("canco")
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
