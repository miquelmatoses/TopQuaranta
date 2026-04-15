"""Staff dashboard — landing page with links to all staff tools."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from . import staff_required


@staff_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Staff landing page with links to all internal tools."""
    return render(request, "web/staff/dashboard.html")
