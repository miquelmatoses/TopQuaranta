"""Staff views package — internal tools for TopQuaranta admins.

All views in this package require is_staff=True.
"""

import functools

from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponseForbidden


def staff_required(view_func):
    """Decorator that requires the user to be authenticated and is_staff=True."""

    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return HttpResponseForbidden("Accés restringit a personal autoritzat.")
        return view_func(request, *args, **kwargs)

    return wrapper


def paginate(request: HttpRequest, queryset, per_page: int = 50):
    """Paginate a queryset and return the current page object."""
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))
