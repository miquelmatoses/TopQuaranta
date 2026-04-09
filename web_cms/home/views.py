from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from .models import Municipi

@login_required
def geo_choices(request):
    # Limitem a usuaris amb accés a l’admin
    user = request.user
    if not (user.is_staff or user.has_perm("wagtailadmin.access_admin")):
        return HttpResponseForbidden("Forbidden")

    territori = (request.GET.get("territori") or "").strip()
    comarca = (request.GET.get("comarca") or "").strip()

    comarques = []
    localitats = []

    if territori and territori != "Altres":
        comarques = list(
            Municipi.objects.filter(Territori=territori)
            .exclude(Comarca__isnull=True).exclude(Comarca="")
            .values_list("Comarca", flat=True)
            .distinct().order_by("Comarca")
        )

    if territori and comarca:
        localitats = list(
            Municipi.objects.filter(Territori=territori, Comarca=comarca)
            .exclude(Municipi__isnull=True).exclude(Municipi="")
            .values_list("Municipi", flat=True)
            .distinct().order_by("Municipi")
        )

    return JsonResponse({"comarques": comarques, "localitats": localitats})
