"""Staff views package — internal tools for TopQuaranta admins.

All views in this package require is_staff=True.
"""

import functools

from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponseForbidden


def staff_required(view_func):
    """Decorator that gates a view behind: authenticated + is_staff + 2FA verified.

    S11: the session is only OTP-verified after the user completes a 2FA
    challenge (via django-otp's otp_login). If the staff user has no device
    configured yet, send them to enrollment; if they have a device but this
    session hasn't passed the challenge, send them to the verify page with
    the current URL as `next`. Non-staff (including anonymous) still get 403.
    """

    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not user.is_staff:
            from django.shortcuts import render

            return render(request, "web/403.html", status=403)

        if not user.is_verified():
            # Lazy import to avoid a circular dep at app-load time.
            from django.shortcuts import redirect
            from django_otp.plugins.otp_totp.models import TOTPDevice

            has_device = TOTPDevice.objects.filter(
                user=user,
                confirmed=True,
            ).exists()
            target = (
                "comptes:dos_fa_verificar"
                if has_device
                else "comptes:dos_fa_configurar"
            )
            return redirect(
                f"/compte/2fa/{'verificar' if has_device else 'configurar'}/"
                f"?next={request.get_full_path()}"
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def paginate(request: HttpRequest, queryset, per_page: int = 50):
    """Paginate a queryset and return the current page object."""
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def apply_ordering(
    request: HttpRequest, queryset, allowed_fields: dict[str, str], default: str = ""
):
    """Apply column ordering from GET params.

    allowed_fields maps URL param names to ORM field paths,
    e.g. {"nom": "nom", "data": "data_llancament"}.

    Returns (ordered_queryset, current_order, current_dir).
    """
    order = request.GET.get("order", "")
    direction = request.GET.get("dir", "asc")

    if order not in allowed_fields:
        if default:
            return queryset.order_by(default), "", ""
        return queryset, "", ""

    field = allowed_fields[order]
    if direction == "desc":
        field = f"-{field}"

    return queryset.order_by(field), order, direction
