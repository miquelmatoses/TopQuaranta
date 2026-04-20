"""Auth endpoints for the React SPA.

Uses Django's session middleware (the same chain that powers the current
templates) so nothing new on the backend is required to support login
— we just need a JSON surface over the existing behaviour. `django-axes`
stays active on `login()`; 2FA via `django-otp` remains enforced at the
decorator level on sensitive endpoints (not here — this is public-ish).

Endpoints
---------
GET  /api/v1/auth/me/      — current user, or {is_authenticated: False}
POST /api/v1/auth/login/   — {email, password} → session cookie + user
POST /api/v1/auth/logout/  — clears the session
"""

from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response


def _profile(request_or_user) -> dict:
    """Shape matching what the React `AuthContext` expects.

    Accepts either a DRF request (preferred — we can read the session
    OTP flag off its user) or a bare user. For staff users we also
    expose `is_verified` (did the session pass the 2FA challenge) and
    `has_totp` (is a confirmed TOTP device registered). React's
    `AdminRoute` relies on those to bounce staff who authenticated
    via the API into the Django 2FA flow.
    """
    user = getattr(request_or_user, "user", request_or_user)
    if not user or not user.is_authenticated:
        return {"is_authenticated": False}

    is_verified = False
    has_totp = False
    if user.is_staff:
        is_verified_fn = getattr(user, "is_verified", None)
        if callable(is_verified_fn):
            is_verified = bool(is_verified_fn())
        # Lazy import so non-staff requests skip the query cost.
        from django_otp.plugins.otp_totp.models import TOTPDevice

        has_totp = TOTPDevice.objects.filter(user=user, confirmed=True).exists()

    return {
        "id": user.pk,
        "email": user.email,
        "username": user.username,
        "is_staff": bool(user.is_staff),
        "is_superuser": bool(user.is_superuser),
        "is_authenticated": True,
        "is_verified": is_verified,
        "has_totp": has_totp,
    }


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def me(request: Request) -> Response:
    """Return the current user profile (or an anonymous shape).

    Setting `ensure_csrf_cookie` here means any SPA doing a GET to /me/
    on page load picks up the `csrftoken` cookie it needs for later
    POST requests. The React `lib/api.js` client reads that cookie and
    forwards it as `X-CSRFToken` automatically.
    """
    return Response(_profile(request))


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request: Request) -> Response:
    """Authenticate via email + password and open a session.

    `django-axes` rate-limits failed attempts automatically via its
    authentication backend; no extra logic here.
    """
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""
    if not email or not password:
        return Response({"error": "Missing credentials"}, status=400)

    # Usuari inherits AbstractUser (USERNAME_FIELD="username"), but we
    # expose a single email field in the UI. Look the user up by email
    # first, then authenticate by their actual username so ModelBackend
    # + django-axes both work untouched.
    from comptes.models import Usuari

    lookup = Usuari.objects.filter(email__iexact=email).first()
    if lookup is None:
        return Response({"error": "Credencials invàlides"}, status=401)

    user = authenticate(request, username=lookup.username, password=password)
    if user is None:
        return Response({"error": "Credencials invàlides"}, status=401)

    login(request, user)
    return Response(_profile(request))


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request: Request) -> Response:
    """Clear the session cookie."""
    logout(request)
    return Response({"ok": True})
