import datetime

from django.http import HttpRequest


def current_year(request: HttpRequest) -> dict[str, int]:
    """Add the current year to template context for copyright footers."""
    return {"current_year": datetime.date.today().year}
