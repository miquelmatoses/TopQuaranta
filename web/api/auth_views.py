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


def _profile(user) -> dict:
    """Shape matching what the React `AuthContext` expects."""
    if not user or not user.is_authenticated:
        return {"is_authenticated": False}
    return {
        "id": user.pk,
        "email": user.email,
        "username": user.username,
        "is_staff": bool(user.is_staff),
        "is_superuser": bool(user.is_superuser),
        "is_authenticated": True,
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
    return Response(_profile(request.user))


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

    # Custom Usuari model uses `email` as USERNAME_FIELD; authenticate
    # expects the USERNAME_FIELD as the `username` kwarg.
    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response({"error": "Credencials invàlides"}, status=401)

    login(request, user)
    return Response(_profile(user))


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request: Request) -> Response:
    """Clear the session cookie."""
    logout(request)
    return Response({"ok": True})
