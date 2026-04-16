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


def apply_ordering(request: HttpRequest, queryset, allowed_fields: dict[str, str], default: str = ""):
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
