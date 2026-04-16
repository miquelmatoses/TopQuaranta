import datetime

from django.http import HttpRequest


def current_year(request: HttpRequest) -> dict[str, int]:
    """Add the current year to template context for copyright footers."""
    return {"current_year": datetime.date.today().year}


def user_header_info(request: HttpRequest) -> dict:
    """Provide header button label and URL based on user role.

    - Anonymous: "Uneix-t'hi" → combined register/login page
    - Staff/admin: "Admin" → dashboard
    - Verified artist: "Artista" → dashboard
    - Regular user: "Compte" → dashboard
    """
    if not request.user.is_authenticated:
        return {"header_label": "Uneix-t'hi", "header_url_name": "comptes:accedir"}

    if request.user.is_staff:
        return {"header_label": "Admin", "header_url_name": "comptes:dashboard"}

    # Check if user is a verified artist (cache on request to avoid repeated queries)
    if not hasattr(request, "_tq_user_artista_checked"):
        from comptes.models import UserArtista

        request._tq_is_verified_artist = UserArtista.objects.filter(
            usuari=request.user, verificat=True
        ).exists()
        request._tq_user_artista_checked = True

    if request._tq_is_verified_artist:
        return {"header_label": "Artista", "header_url_name": "comptes:dashboard"}

    return {"header_label": "Compte", "header_url_name": "comptes:dashboard"}
