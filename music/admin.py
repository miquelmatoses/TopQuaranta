from django.contrib import admin
from django.contrib import messages
from django.db import connection, transaction
from django.db.models import Count, Q
from django.template.response import TemplateResponse
from django.utils.html import format_html

from .ml import classificar_i_guardar, recalcular_ml_si_cal
from .models import Album, Artista, Canco, HistorialRevisio, Territori
from .verificacio import crear_historial


MOTIUS_VALIDS = {"no_catala", "artista_incorrecte", "album_incorrecte", "no_musica"}

MOTIUS_REBUIG_ARTISTA = [
    ("artista_incorrecte", "El perfil Deezer no és el nostre artista"),
]

# comarca → territory code from municipis table (cached at module level)
_COMARCA_MAP: dict[str, str] | None = None
_MUNICIPIS_TERRITORI_MAP = {
    "Catalunya": "CAT",
    "País Valencià": "VAL",
    "Illes": "BAL",
    "Catalunya del Nord": "CNO",
    "Andorra": "AND",
    "Franja de Ponent": "FRA",
    "L'Alguer": "ALG",
    "El Carxe": "CAR",
}


def _get_comarca_map() -> dict[str, str]:
    global _COMARCA_MAP
    if _COMARCA_MAP is None:
        _COMARCA_MAP = {}
        with connection.cursor() as cursor:
            cursor.execute('SELECT DISTINCT "Comarca", "Territori" FROM municipis')
            for comarca, territori in cursor.fetchall():
                codi = _MUNICIPIS_TERRITORI_MAP.get(territori)
                if codi and comarca:
                    _COMARCA_MAP[comarca.strip()] = codi
    return _COMARCA_MAP


class TerritoriInline(admin.TabularInline):
    model = Artista.territoris.through
    extra = 1
    verbose_name = "Territori"
    verbose_name_plural = "Territoris"


@admin.register(Artista)
class ArtistaAdmin(admin.ModelAdmin):
    list_display = ("nom", "get_territoris_display", "deezer_id", "deezer_no_trobat", "aprovat", "localitat", "comarca")
    list_editable = ("deezer_id", "localitat", "comarca")
    list_filter = ("deezer_no_trobat", "aprovat", "auto_descobert", "territoris")
    search_fields = ("nom",)
    readonly_fields = ("deezer_link",)
    inlines = [TerritoriInline]
    exclude = ("territoris",)
    actions = ["marcar_sense_deezer_i_netejar", "aprovar_artista"]

    @admin.display(description="Territoris")
    def get_territoris_display(self, obj):
        return ", ".join(obj.territoris.values_list("codi", flat=True))

    @admin.display(description="Deezer")
    def deezer_link(self, obj):
        if not obj.deezer_id:
            return "-"
        url = f"https://www.deezer.com/artist/{obj.deezer_id}"
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, url)

    @admin.action(description="Marcar sense Deezer i netejar")
    def marcar_sense_deezer_i_netejar(self, request, queryset):
        if "confirmar" not in request.POST:
            cancons = Canco.objects.filter(
                artista__in=queryset, verificada=False
            )
            return TemplateResponse(
                request,
                "admin/music/confirmar_rebuig.html",
                {
                    "action_name": "marcar_sense_deezer_i_netejar",
                    "queryset": queryset,
                    "total_cancons": cancons.count(),
                    "total_albums": 0,
                    "motius": MOTIUS_REBUIG_ARTISTA,
                    "cancel_url": request.get_full_path(),
                },
            )

        motiu = request.POST.get("motiu", "artista_incorrecte")
        total_cancons = 0
        with transaction.atomic():
            for artista in queryset:
                cancons = Canco.objects.filter(
                    artista=artista, verificada=False
                )
                for canco in cancons.iterator():
                    crear_historial(canco, "rebutjada", motiu)
                deleted = cancons.count()
                cancons.delete()
                total_cancons += deleted
            updated = queryset.update(deezer_id=None, deezer_no_trobat=True)
        recalcular_ml_si_cal()
        self.message_user(
            request,
            f"{updated} artistes marcats sense Deezer, "
            f"{total_cancons} cançons no verificades esborrades.",
        )

    @admin.action(description="Aprovar artista")
    def aprovar_artista(self, request, queryset):
        ok = 0
        errors = []
        comarca_map = _get_comarca_map()
        for artista in queryset:
            if not artista.localitat or not artista.comarca:
                errors.append(f"{artista.nom}: falta localitat o comarca")
                continue
            artista.aprovat = True
            artista.save(update_fields=["aprovat"])
            # Auto-assign territory from comarca
            codi = comarca_map.get(artista.comarca.strip())
            if codi:
                t = Territori.objects.filter(codi=codi).first()
                if t:
                    artista.territoris.set([t])
                    self.message_user(
                        request,
                        f"{artista.nom}: aprovat, territori={codi}",
                    )
            ok += 1
        if errors:
            self.message_user(
                request,
                "Errors: " + "; ".join(errors),
                level=messages.ERROR,
            )
        if ok:
            self.message_user(request, f"{ok} artistes aprovats.")

    def save_model(self, request, obj, form, change):
        # Auto-assign territory from comarca on save
        if change and "comarca" in form.changed_data and obj.comarca:
            comarca_map = _get_comarca_map()
            codi = comarca_map.get(obj.comarca.strip())
            if codi:
                t = Territori.objects.filter(codi=codi).first()
                if t:
                    obj.territoris.set([t])

        super().save_model(request, obj, form, change)
        if change and "deezer_id" in form.changed_data and obj.deezer_id is not None:
            deleted, _ = Canco.objects.filter(
                artista=obj, verificada=False
            ).delete()
            obj.deezer_no_trobat = False
            obj.save(update_fields=["deezer_no_trobat"])
            if deleted:
                self.message_user(
                    request,
                    f"{obj.nom}: deezer_id canviat, {deleted} cançons antigues "
                    f"(no verificades) esborrades, deezer_no_trobat=False.",
                )


class VerificadaFilter(admin.SimpleListFilter):
    title = "verificada"
    parameter_name = "verificada"

    def lookups(self, request, model_admin):
        return [("0", "No verificada"), ("1", "Verificada")]

    def queryset(self, request, queryset):
        if self.value() == "0":
            return queryset.filter(verificada=False)
        if self.value() == "1":
            return queryset.filter(verificada=True)
        return queryset

    def choices(self, changelist):
        yield {
            "selected": self.value() is None,
            "query_string": changelist.get_query_string(remove=[self.parameter_name]),
            "display": "Totes",
        }
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == str(lookup),
                "query_string": changelist.get_query_string({self.parameter_name: lookup}),
                "display": title,
            }

    def value(self):
        val = super().value()
        if val is None:
            return "0"
        return val


@admin.register(Canco)
class CancoAdmin(admin.ModelAdmin):
    list_display = (
        "ml_display",
        "nom",
        "artista",
        "album_nom",
        "data_llancament",
        "deezer_track_link",
        "deezer_artista_link",
        "viasona_link",
        "isrc",
        "verificada",
        "get_territoris_display",
    )
    list_display_links = ("nom",)
    list_filter = (VerificadaFilter, "ml_classe", "data_llancament")
    search_fields = ("nom", "artista__nom")
    ordering = ("ml_classe", "-data_llancament")
    list_per_page = 50
    raw_id_fields = ("artista", "album")
    actions = ["marcar_verificada", "rebutjar_esborrar", "rebutjar_album_sencer"]

    @admin.display(description="ML", ordering="ml_classe")
    def ml_display(self, obj):
        if not obj.ml_classe:
            return "-"
        colors = {"A": "#28a745", "B": "#fd7e14", "C": "#dc3545"}
        color = colors.get(obj.ml_classe, "#666")
        pct = f"{obj.ml_confianca * 100:.0f}" if obj.ml_confianca is not None else "?"
        return format_html(
            '<span style="color:{};font-weight:bold">{} ({}%)</span>',
            color,
            obj.ml_classe,
            pct,
        )

    @admin.display(description="Àlbum")
    def album_nom(self, obj):
        return obj.album.nom

    @admin.display(description="Deezer track")
    def deezer_track_link(self, obj):
        if not obj.deezer_id:
            return "-"
        url = f"https://www.deezer.com/track/{obj.deezer_id}"
        return format_html('<a href="{}" target="_blank" rel="noopener">&#x1F517;</a>', url)

    @admin.display(description="Deezer artista")
    def deezer_artista_link(self, obj):
        if not obj.artista.deezer_id:
            return "-"
        url = f"https://www.deezer.com/artist/{obj.artista.deezer_id}"
        return format_html('<a href="{}" target="_blank" rel="noopener">&#x1F517;</a>', url)

    @admin.display(description="Viasona")
    def viasona_link(self, obj):
        from django.utils.http import urlencode
        q = f"{obj.artista.nom} {obj.nom}"
        url = "https://www.viasona.cat/cerca?" + urlencode({"que": q})
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" '
            'style="font-size:12px">\U0001f50d</a>',
            url,
        )

    @admin.display(description="Territoris")
    def get_territoris_display(self, obj):
        return ", ".join(obj.artista.territoris.values_list("codi", flat=True))

    @admin.action(description="Aprovar cançó")
    def marcar_verificada(self, request, queryset):
        with transaction.atomic():
            for canco in queryset.iterator():
                crear_historial(canco, "aprovada", "ok")
            updated = queryset.update(verificada=True)
        recalcular_ml_si_cal()
        self.message_user(request, f"{updated} cançons marcades com a verificades.")

    @admin.action(description="Rebutjar (esborrar)")
    def rebutjar_esborrar(self, request, queryset):
        motiu = request.POST.get("motiu", "")
        if motiu not in MOTIUS_VALIDS:
            self.message_user(
                request,
                "Has de seleccionar un motiu de rebuig.",
                level=messages.ERROR,
            )
            return

        msgs = []
        with transaction.atomic():
            for canco in queryset.select_related("artista", "album"):
                crear_historial(canco, "rebutjada", motiu)

            if motiu == "artista_incorrecte":
                artista_ids = set(queryset.values_list("artista_id", flat=True))
                for artista in Artista.objects.filter(pk__in=artista_ids):
                    to_delete = Canco.objects.filter(artista=artista, verificada=False)
                    count = to_delete.count()
                    to_delete.delete()
                    artista.deezer_no_trobat = True
                    artista.deezer_id = None
                    artista.save(update_fields=["deezer_no_trobat", "deezer_id"])
                    msgs.append(f"{count} cançons esborrades de l'artista {artista.nom}")
            elif motiu == "album_incorrecte":
                album_ids = set(queryset.values_list("album_id", flat=True))
                for album in Album.objects.filter(pk__in=album_ids):
                    to_delete = Canco.objects.filter(album=album, verificada=False)
                    count = to_delete.count()
                    to_delete.delete()
                    msgs.append(f"{count} cançons esborrades de l'àlbum {album.nom}")
            else:
                count = queryset.count()
                queryset.delete()
                msgs.append(f"{count} cançons esborrades")
        recalcular_ml_si_cal()
        self.message_user(request, f"Motiu: {motiu}. " + "; ".join(msgs) + ".")

    @admin.action(description="Rebutjar àlbum sencer")
    def rebutjar_album_sencer(self, request, queryset):
        motiu = request.POST.get("motiu", "")
        if motiu not in MOTIUS_VALIDS:
            self.message_user(
                request,
                "Has de seleccionar un motiu de rebuig.",
                level=messages.ERROR,
            )
            return

        album_ids = set(queryset.values_list("album_id", flat=True).distinct())
        cancons = Canco.objects.filter(album_id__in=album_ids, verificada=False)

        msgs = []
        with transaction.atomic():
            for canco in cancons.select_related("artista", "album"):
                crear_historial(canco, "rebutjada", motiu)

            if motiu == "artista_incorrecte":
                artista_ids = set(cancons.values_list("artista_id", flat=True))
                for artista in Artista.objects.filter(pk__in=artista_ids):
                    to_delete = Canco.objects.filter(artista=artista, verificada=False)
                    count = to_delete.count()
                    to_delete.delete()
                    artista.deezer_no_trobat = True
                    artista.deezer_id = None
                    artista.save(update_fields=["deezer_no_trobat", "deezer_id"])
                    msgs.append(f"{count} cançons de l'artista {artista.nom}")
            else:
                deleted, _ = Canco.objects.filter(
                    album_id__in=album_ids, verificada=False
                ).delete()
                msgs.append(f"{deleted} cançons de {len(album_ids)} àlbums")
        recalcular_ml_si_cal()
        self.message_user(request, f"Motiu: {motiu}. Esborrades: " + "; ".join(msgs) + ".")


class ArtistaPendent(Artista):
    """Proxy model for auto-discovered artists pending approval."""

    class Meta:
        proxy = True
        verbose_name = "Artista pendent"
        verbose_name_plural = "Artistes pendents"


@admin.register(ArtistaPendent)
class ArtistaPendentAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "deezer_artista_link",
        "viasona_link",
        "nb_cancons_verificades",
        "territori_select",
        "comarca_select",
        "localitat_select",
        "accions_inline",
    )
    search_fields = ("nom",)
    actions = ["aprovar_artista", "descartar_artista"]

    # Keep localitat/comarca in list_editable for Django form handling,
    # but hide them visually — the cascading selects replace them.
    class Media:
        js = ("music/js/artista_pendent.js",)
        css = {"all": ("music/css/artista_pendent.css",)}

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(aprovat=False, auto_descobert=True)
            .annotate(
                nb_verif=Count("cancons", filter=Q(cancons__verificada=True))
            )
            .order_by("-nb_verif")
        )

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                "municipis/territoris/",
                self.admin_site.admin_view(self._api_territoris),
                name="artista_pendent_territoris",
            ),
            path(
                "municipis/comarques/",
                self.admin_site.admin_view(self._api_comarques),
                name="artista_pendent_comarques",
            ),
            path(
                "municipis/municipis/",
                self.admin_site.admin_view(self._api_municipis),
                name="artista_pendent_municipis",
            ),
            path(
                "<int:pk>/aprovar/",
                self.admin_site.admin_view(self._api_aprovar),
                name="artista_pendent_aprovar",
            ),
            path(
                "<int:pk>/descartar/",
                self.admin_site.admin_view(self._api_descartar),
                name="artista_pendent_descartar",
            ),
        ]
        return custom + urls

    def _api_territoris(self, request):
        from django.http import JsonResponse
        result = []
        seen = set()
        with connection.cursor() as cursor:
            cursor.execute('SELECT DISTINCT "Territori" FROM municipis ORDER BY 1')
            for (territori,) in cursor.fetchall():
                codi = _MUNICIPIS_TERRITORI_MAP.get(territori)
                if codi and codi not in seen:
                    result.append({"codi": codi, "nom": territori})
                    seen.add(codi)
        return JsonResponse(result, safe=False)

    def _api_comarques(self, request):
        from django.http import JsonResponse
        territori_codi = request.GET.get("territori", "")
        # Reverse-map codi → municipis.Territori name
        reverse_map = {v: k for k, v in _MUNICIPIS_TERRITORI_MAP.items()}
        territori_nom = reverse_map.get(territori_codi, "")
        if not territori_nom:
            return JsonResponse([], safe=False)
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT DISTINCT "Comarca" FROM municipis WHERE "Territori" = %s ORDER BY 1',
                [territori_nom],
            )
            result = [row[0] for row in cursor.fetchall()]
        return JsonResponse(result, safe=False)

    def _api_municipis(self, request):
        from django.http import JsonResponse
        comarca = request.GET.get("comarca", "")
        if not comarca:
            return JsonResponse([], safe=False)
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT "Municipi" FROM municipis WHERE "Comarca" = %s ORDER BY 1',
                [comarca],
            )
            result = [row[0] for row in cursor.fetchall()]
        return JsonResponse(result, safe=False)

    @admin.display(description="Cançons verif.", ordering="nb_verif")
    def nb_cancons_verificades(self, obj):
        return getattr(obj, "nb_verif", 0)

    @admin.display(description="Deezer")
    def deezer_artista_link(self, obj):
        if not obj.deezer_id:
            return "-"
        url = f"https://www.deezer.com/artist/{obj.deezer_id}"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">\U0001f517</a>', url
        )

    @admin.display(description="Viasona")
    def viasona_link(self, obj):
        from django.utils.http import urlencode
        url = "https://www.viasona.cat/cerca?" + urlencode({"que": obj.nom})
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">\U0001f50d</a>', url
        )

    @admin.display(description="Territori")
    def territori_select(self, obj):
        return format_html(
            '<select class="tq-territori" data-artista-id="{}" data-field="territori">'
            '<option value="">-- Territori --</option></select>',
            obj.pk,
        )

    @admin.display(description="Comarca")
    def comarca_select(self, obj):
        return format_html(
            '<select class="tq-comarca" data-artista-id="{}" data-field="comarca">'
            '<option value="">-- Comarca --</option></select>',
            obj.pk,
        )

    @admin.display(description="Localitat")
    def localitat_select(self, obj):
        return format_html(
            '<select class="tq-localitat" data-artista-id="{}" data-field="localitat">'
            '<option value="">-- Localitat --</option></select>',
            obj.pk,
        )

    @admin.display(description="")
    def accions_inline(self, obj):
        return format_html(
            '<button type="button" class="tq-aprovar" data-id="{}" disabled '
            'style="background:#28a745;color:#fff;border:none;padding:4px 8px;'
            'border-radius:3px;cursor:pointer;opacity:0.4;margin-right:4px"'
            '>\u2713</button>'
            '<button type="button" class="tq-descartar" data-id="{}" '
            'style="background:#dc3545;color:#fff;border:none;padding:4px 8px;'
            'border-radius:3px;cursor:pointer"'
            '>\u2717</button>',
            obj.pk, obj.pk,
        )

    def _api_aprovar(self, request, pk):
        from django.http import JsonResponse
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)
        try:
            artista = Artista.objects.get(pk=pk)
        except Artista.DoesNotExist:
            return JsonResponse({"error": "Artista not found"}, status=404)

        import json
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            data = {}
        comarca = data.get("comarca", "").strip()
        localitat = data.get("localitat", "").strip()
        if not comarca or not localitat:
            return JsonResponse({"error": "Cal comarca i localitat"}, status=400)

        artista.comarca = comarca
        artista.localitat = localitat
        artista.aprovat = True
        artista.save(update_fields=["aprovat", "localitat", "comarca"])

        comarca_map = _get_comarca_map()
        codi = comarca_map.get(comarca)
        territori = ""
        if codi:
            t = Territori.objects.filter(codi=codi).first()
            if t:
                artista.territoris.set([t])
                territori = codi
        return JsonResponse({"ok": True, "territori": territori})

    def _api_descartar(self, request, pk):
        from django.http import JsonResponse
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)
        try:
            artista = Artista.objects.get(pk=pk)
        except Artista.DoesNotExist:
            return JsonResponse({"error": "Artista not found"}, status=404)

        has_verified = artista.cancons.filter(verificada=True).exists()
        if has_verified:
            artista.auto_descobert = False
            artista.save(update_fields=["auto_descobert"])
            return JsonResponse({"ok": True, "action": "kept"})
        else:
            artista.delete()
            return JsonResponse({"ok": True, "action": "deleted"})

    @admin.action(description="Aprovar artista")
    def aprovar_artista(self, request, queryset):
        ok = 0
        errs = []
        comarca_map = _get_comarca_map()
        for artista in queryset:
            # Read values from cascading selects (hidden fields injected by JS)
            comarca = request.POST.get(f"pendent_comarca_{artista.pk}", "") or artista.comarca
            localitat = request.POST.get(f"pendent_localitat_{artista.pk}", "") or artista.localitat
            if comarca:
                artista.comarca = comarca
            if localitat:
                artista.localitat = localitat
            if not artista.localitat or not artista.comarca:
                errs.append(f"{artista.nom}: falta localitat o comarca")
                continue
            artista.aprovat = True
            artista.save(update_fields=["aprovat", "localitat", "comarca"])
            codi = comarca_map.get(artista.comarca.strip())
            if codi:
                t = Territori.objects.filter(codi=codi).first()
                if t:
                    artista.territoris.set([t])
            ok += 1
        if errs:
            self.message_user(request, "; ".join(errs), level=messages.ERROR)
        if ok:
            self.message_user(request, f"{ok} artistes aprovats.")

    @admin.action(description="Descartar artista")
    def descartar_artista(self, request, queryset):
        deleted = 0
        kept = 0
        for artista in queryset:
            has_verified = artista.cancons.filter(verificada=True).exists()
            if has_verified:
                artista.auto_descobert = False
                artista.save(update_fields=["auto_descobert"])
                kept += 1
            else:
                artista.delete()
                deleted += 1
        self.message_user(
            request, f"{deleted} artistes eliminats, {kept} descartats (tenen cançons verificades)."
        )


@admin.register(HistorialRevisio)
class HistorialRevisioAdmin(admin.ModelAdmin):
    list_display = ("canco_nom", "artista_nom", "decisio", "motiu", "created_at")
    list_filter = ("decisio", "motiu")
    search_fields = ("canco_nom", "artista_nom")
    readonly_fields = [f.name for f in HistorialRevisio._meta.get_fields()]
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
