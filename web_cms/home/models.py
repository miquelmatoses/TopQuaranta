# --- Standard library ---
from urllib.parse import urlencode

# --- Django ---
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.cache import cache
from django.core.paginator import EmptyPage, Paginator
from django.core.validators import (MaxValueValidator, MinValueValidator,
                                    RegexValidator)
from django import forms
from django.db import models, transaction, connection
from django.db.models import F
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
# --- Wagtail ---
from wagtail import blocks
from wagtail.admin.panels import (FieldPanel, HelpPanel, InlinePanel,
                                  MultiFieldPanel)
from wagtail.contrib.routable_page.models import RoutablePageMixin, route
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import StreamField
from wagtail.models import Orderable, Page
from wagtail.contrib.routable_page.models import RoutablePageMixin, route
from wagtail.models import DraftStateMixin, RevisionMixin, WorkflowMixin
from wagtail.snippets.models import register_snippet
from wagtail.admin.forms import WagtailAdminModelForm  # ← AFIG
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, HelpPanel  # ← AFIG

import json

# --- Project-local ---
from .blocks import CarouselBlock


# --- Pages ---
class HomePage(Page):
    """
    Pàgina d'inici construïda des de l'admin amb blocs (StreamField).
    A l'admin: Pàgines → Home → Body (afegeix blocs "Hero", "Graella d'Àlbums", etc.).
    """

    # --- Hero (nadiu, simple) ---
    hero_title = models.CharField(max_length=120, blank=True)
    hero_subtitle = models.CharField(max_length=255, blank=True)
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    hero_cta_text = models.CharField(max_length=80, blank=True)
    hero_cta_url = models.URLField(blank=True)

    body = StreamField(
        [
            ("text", blocks.RichTextBlock()),
            ("carousel", CarouselBlock()),
        ],
        use_json_field=True,
        blank=True,
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_title"),
                FieldPanel("hero_subtitle"),
                FieldPanel("hero_image"),
                FieldPanel("hero_cta_text"),
                FieldPanel("hero_cta_url"),
            ],
            heading="Hero (portada)",
        ),
        FieldPanel("body"),
    ]

class CmsArtistaAdminForm(WagtailAdminModelForm):
    """
    Converteix Territori/Comarca/Localitat en selects amb valors vàlids
    provinents de la taula 'municipis'. Accepta Territori='Altres'.
    """
    class Media:
        js = ["home/js/cmsartista_admin.js"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Llistes úniques ordenades
        territoris = (
            Municipi.objects.exclude(Territori__isnull=True)
            .exclude(Territori="")
            .values_list("Territori", flat=True)
            .distinct()
            .order_by("Territori")
        )
        # 'Altres' al final
        territori_choices = [(t, t) for t in territoris] + [("Altres", "Altres")]

        self.fields["territori"] = forms.ChoiceField(
            choices=[("", "— Selecciona —")] + territori_choices,
            required=False,
            label=_("Territori"),
        )

        # En funció del territori seleccionat (o instància existent) filtrem comarques/localitats
        current_territori = (
            self.data.get(self.add_prefix("territori"))
            or getattr(self.instance, "territori", "") or ""
        )

        comarques_qs = Municipi.objects.all()
        if current_territori and current_territori != "Altres":
            comarques_qs = comarques_qs.filter(Territori=current_territori)

        comarques = (
            comarques_qs.exclude(Comarca__isnull=True)
            .exclude(Comarca="")
            .values_list("Comarca", flat=True)
            .distinct()
            .order_by("Comarca")
        )
        self.fields["comarca"] = forms.ChoiceField(
            choices=[("", "—")] + [(c, c) for c in comarques],
            required=False,
            label=_("Comarca"),
        )
        current_comarca = (
            self.data.get(self.add_prefix("comarca"))
            or getattr(self.instance, "comarca", "") or ""
        )

        localitats_qs = Municipi.objects.all()
        if current_territori and current_territori != "Altres":
            localitats_qs = localitats_qs.filter(Territori=current_territori)
        if current_comarca:
            localitats_qs = localitats_qs.filter(Comarca=current_comarca)

        localitats = (
            localitats_qs.exclude(Municipi__isnull=True)
            .exclude(Municipi="")
            .values_list("Municipi", flat=True)
            .distinct()
            .order_by("Municipi")
        )
        self.fields["localitat"] = forms.ChoiceField(
            choices=[("", "—")] + [(m, m) for m in localitats],
            required=False,
            label=_("Localitat"),
        )

    def clean(self):
        cleaned = super().clean()
        territori = cleaned.get("territori") or ""
        comarca = cleaned.get("comarca") or ""
        localitat = cleaned.get("localitat") or ""

        if territori == "Altres":
            # Acceptem "Altres" sense comarca/localitat
            cleaned["comarca"] = ""
            cleaned["localitat"] = ""
            return cleaned

        # Valida que estiguen al catàleg
        if territori:
            ok_terr = Municipi.objects.filter(Territori=territori).exists()
            if not ok_terr:
                self.add_error("territori", _("Valor no vàlid"))

        if comarca:
            ok_com = Municipi.objects.filter(Territori=territori, Comarca=comarca).exists()
            if not ok_com:
                self.add_error("comarca", _("Valor no vàlid per al territori seleccionat"))

        if localitat:
            ok_loc = Municipi.objects.filter(
                Territori=territori, Comarca=comarca, Municipi=localitat
            ).exists()
            if not ok_loc:
                self.add_error("localitat", _("Valor no vàlid per a la comarca seleccionada"))

        return cleaned

# --- Databases ---
class CmsArtista(WorkflowMixin, DraftStateMixin, RevisionMixin, models.Model):
    """
    Mapa ORM a la taula existent `cms_artists` (UNMANAGED).
    No genera migracions ni taules; només llig dades per a l'admin/consulta.
    """

    # 1) Identificació
    id_spotify = models.CharField(
        "ID Spotify",
        max_length=50,
        primary_key=True,
        help_text=_("Introdueix només l’ID. https://open.spotify.com/artist/AQUEST_ÉS_L'ID "),
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z0-9]{22}$",
                message=_("Només l’ID de Spotify (22 caràcters alfanumèrics, sense URL)."),
                code="invalid_spotify_id",
            )
        ],
    )
    nom = models.CharField("Nom", max_length=255, blank=False, null=False)

    # 2) Localització
    territori = models.CharField("Territori", max_length=50, blank=True, null=False)
    comarca = models.CharField("Comarca", max_length=255, blank=True, null=False)
    localitat = models.CharField("Localitat", max_length=255, blank=True, null=False)

    # 3) Etiquetes
    generes = models.TextField(
        "Gèneres", 
        blank=True, 
        null=True, 
    )
    DONES_CHOICES = (("0%", "0%"), ("<50%", "<50%"), (">50%", ">50%"), ("100%", "100%"))
    dones = models.CharField(
        "Dones", 
        max_length=4, 
        choices=DONES_CHOICES, 
        blank=True, 
        null=True,
        help_text=_("Percentatge de dones."),
    )

    # 4) Contacte
    agencia = models.CharField("Agència", max_length=255, blank=True, null=True)
    email = models.TextField("Email", blank=True, null=True)
    telefon = models.TextField("Telèfon", blank=True, null=True)

    # 5) Enllaços
    web = models.TextField("Web", blank=True, null=True)
    viquipedia = models.TextField("Viquipèdia", blank=True, null=True)
    id_viasona = models.TextField("ID Viasona", blank=True, null=True)

    # 6) Xarxes
    instagram = models.CharField("Instagram", max_length=255, blank=True, null=True)
    youtube = models.TextField("YouTube", blank=True, null=True)
    tiktok = models.TextField("TikTok", blank=True, null=True)
    bluesky = models.TextField("Bluesky", blank=True, null=True)

    # 7) Música
    soundcloud = models.TextField("SoundCloud", blank=True, null=True)
    bandcamp = models.TextField("Bandcamp", blank=True, null=True)
    deezer = models.TextField("Deezer", blank=True, null=True)
    myspace = models.TextField("MySpace", blank=True, null=True)

    # 8) Contingut
    bio = models.TextField("Bio", blank=True, null=True, help_text=_("Opcional"))

    # 9) Dades Spotify (només lectura al CMS)
    nom_spotify = models.TextField("Nom Spotify", blank=True, null=True, editable=False)
    followers = models.IntegerField("Followers", blank=True, null=True, editable=False)
    popularitat = models.IntegerField("Popularitat", blank=True, null=True, editable=False)
    imatge_url = models.TextField("Imatge (URL)", blank=True, null=True, editable=False)

    # 10) Traça
    created_at = models.DateTimeField("Creat", auto_now_add=True)
    updated_at = models.DateTimeField("Actualitzat", auto_now=True)

    class Meta:
        db_table = "cms_artists"
        ordering = ("nom",)
        verbose_name = "Artista"
        verbose_name_plural = "Artistes"

    def __str__(self):
        return self.nom or self.id_spotify

    # Formulari base d'admin
    base_form_class = CmsArtistaAdminForm  # ← AFIG

    # Panells d'edició (no incloem camps de scheduling ni derivats d’Spotify)
    panels = [
        HelpPanel(content=_("<p>Completa almenys les dades bàsiques (Identificació i Localització).")),
        MultiFieldPanel(
            [
                FieldPanel("nom"),
                FieldPanel("id_spotify"),
                HelpPanel(content='<a id="sp_link" target="_blank" rel="noopener noreferrer" style="display:none">Obrir \
a Spotify</a><script>(function(){function u(){var el=document.querySelector(\'input[name="id_spotify"]\');var a=document\
.getElementById("sp_link");if(!el||!a)return;var v=(el.value||"").trim();if(v){a.href="https://open.spotify.com/artist/"\
+v;a.style.display="inline"}else{a.removeAttribute("href");a.style.display="none"}}document.addEventListener("DOMContent\
Loaded",u);document.addEventListener("input",function(e){if(e&&e.target&&e.target.name==="id_spotify")u()});u();})();</s\
cript>'),
                FieldPanel("bio"),
            ],
            heading=_("Identificació"),
        ),
        MultiFieldPanel(
            [
                FieldPanel("territori"),
                FieldPanel("comarca"),
                FieldPanel("localitat"),
            ],
            heading=_("Localització"),
        ),
        MultiFieldPanel(
            [
                FieldPanel("generes"),
                FieldPanel("dones"),
            ],
            heading=_("Etiquetes"),
        ),
        MultiFieldPanel(
            [
                FieldPanel("agencia"),
                FieldPanel("email"),
                FieldPanel("telefon"),
            ],
            heading=_("Contacte"),
            classname="collapsible collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("web"),
                FieldPanel("viquipedia"),
                FieldPanel("id_viasona"),
            ],
            heading=_("Enllaços"),
            classname="collapsible collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("instagram"),
                FieldPanel("youtube"),
                FieldPanel("tiktok"),
                FieldPanel("bluesky"),
            ],
            heading=_("Xarxes socials"),
            classname="collapsible collapsed",
        ),
        MultiFieldPanel(
            [
                FieldPanel("soundcloud"),
                FieldPanel("bandcamp"),
                FieldPanel("deezer"),
                FieldPanel("myspace"),
            ],
            heading=_("Música"),
            classname="collapsible collapsed",
        ),
    ]



class CmsAlbum(models.Model):
    """
    Mapa ORM (UNMANAGED) a la taula materialitzada `cms_albums`.
    """

    id = models.CharField("ID Spotify", max_length=50, primary_key=True)
    name = models.TextField("Nom")
    album_type = models.TextField("Tipus")
    release_date = models.TextField("Data")
    image_url = models.TextField("Caràtula", blank=True, null=True)
    artist_ids = ArrayField(
        models.TextField(), verbose_name="IDs Artistes", blank=True, null=True
    )
    artist_names = ArrayField(
        models.TextField(), verbose_name="Artistes", blank=True, null=True
    )
    artist_names_str = models.TextField("Artistes str", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "cms_albums"
        ordering = ("release_date", "name")
        verbose_name = "Àlbum"
        verbose_name_plural = "Àlbums"

    def __str__(self):
        return self.name or self.id


class CmsSong(models.Model):
    """
    Mapa ORM (UNMANAGED) a la taula materialitzada `cms_songs`.
    """

    id = models.CharField("ID Spotify", max_length=50, primary_key=True)
    name = models.TextField("Nom")
    popularity = models.IntegerField("Popularitat", blank=True, null=True)
    isrc = models.TextField("ISRC", blank=True, null=True)
    artist_ids = ArrayField(
        models.TextField(), verbose_name="IDs Artistes", blank=True, null=True
    )
    artist_names = ArrayField(
        models.TextField(), verbose_name="Artistes", blank=True, null=True
    )
    artist_names_str = models.TextField("Artistes str", blank=True, null=True)
    album_id = models.CharField("ID Àlbum", max_length=50)

    class Meta:
        managed = False
        db_table = "cms_songs"
        ordering = ("-popularity", "name")
        verbose_name = "Cançó"
        verbose_name_plural = "Cançons"

    def __str__(self):
        return self.name or self.id

class Municipi(models.Model):
    """
    Mirror de la taula existent 'municipis' (només lectura al CMS).
    S'usa per a extraure llistes vàlides de Territori/Comarca/Localitat.
    """
    Municipi = models.CharField(max_length=50, null=True, db_column="Municipi")
    Comarca = models.CharField(max_length=50, null=True, db_column="Comarca")
    Territori = models.CharField(max_length=50, null=True, db_column="Territori")
    Codi = models.CharField(max_length=50, null=True, db_column="Codi")

    class Meta:
        managed = False
        db_table = "municipis"

    def __str__(self):
        return self.Municipi or ""

class RankingSetmanal(models.Model):
    """
    Mirror UNMANAGED de la taula existent `ranking_setmanal`.
    S'usa per a consultar rànquings fixats setmanalment.
    """
    data = models.DateField()
    territori = models.CharField(max_length=20)
    posicio = models.IntegerField(primary_key=True)
    id_canco = models.CharField(max_length=50)
    titol = models.TextField(blank=True, null=True)
    artistes = ArrayField(models.TextField(), blank=True, null=True)
    album_titol = models.TextField(blank=True, null=True)
    score_setmanal = models.IntegerField(blank=True, null=True)
    artistes_ids = ArrayField(models.TextField(), blank=True, null=True)
    album_id = models.CharField(max_length=50, blank=True, null=True)
    album_data = models.DateField(blank=True, null=True)
    album_caratula_url = models.TextField(blank=True, null=True)
    canvi_posicio = models.IntegerField(blank=True, null=True)
    score_global = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "ranking_setmanal"
        indexes = [
            models.Index(fields=["data", "territori", "posicio"]),
            models.Index(fields=["data", "territori"]),
            models.Index(fields=["data"]),
        ]
        verbose_name = "Rànquing setmanal (fixat)"
        verbose_name_plural = "Rànquing setmanal (fixat)"

    def __str__(self):
        return f"{self.data} · {self.territori} · #{self.posicio} · {self.titol or self.id_canco}"

class MusicIndexPage(RoutablePageMixin, Page):
    """
    Pàgina índex amb subrutes per navegar per ÀLBUMS / ARTISTES / CANÇONS
    usant taules materialitzades (cms_*) via ORM, amb filtres, ordre i caché curt.
    """

    parent_page_types = ["home.HomePage", "wagtailcore.Page"]
    subpage_types = ["home.ArtistsPage", "home.AlbumsPage", "home.SongsPage"]

    # ---------- Helpers ----------
    def _cache_get_or_set(self, key: str, producer, timeout=120):
        data = cache.get(key)
        if data is not None:
            return data
        data = producer()
        cache.set(key, data, timeout=timeout)
        return data

    def _qsdict(self, request):
        # Retorna dict net de querystring (per construir xips)
        return {k: v for k, v in request.GET.items() if v not in (None, "")}

    def _url_with(self, base: str, params: dict, **overrides):
        q = dict(params)
        q.update({k: v for k, v in overrides.items() if v is not None})
        # Llevar claus amb valor buit per "desactivar" xips
        q = {k: v for k, v in q.items() if v not in ("", None)}
        return f"{base}?{urlencode(q)}" if q else base

    def _cover_url(self, v):
        """Retorna sempre una URL neta o None a partir de:
        - URL plana (str)
        - JSON (dict) amb clau 'url'
        - JSON (str) serialitzat amb clau 'url'
        """
        if not v:
            return None
        # dict JSON
        if isinstance(v, dict):
            return v.get("url") or None
        # text: pot ser URL o JSON serialitzat
        s = str(v).strip()
        if s.startswith("{"):
            try:
                obj = json.loads(s)
                return obj.get("url") or None
            except Exception:
                return None
        # URL plana
        return s

    # ---------- Rutes ----------

    @route(r"^$", name="index")
    def index(self, request):
        # Redirigim /music/ → /music/artists/
        return redirect(self.url + "artists/")

    @route(r"^albums/$", name="albums_index")
    def albums_index(self, request):
        from .models import CmsAlbum  # import local per evitar circular

        params = self._qsdict(request)
        order = params.get("order", "release_desc")
        artist = params.get("artist")
        album_type = params.get("type")
        page = max(int(params.get("page", 1)), 1)
        per = min(max(int(params.get("per", 30)), 1), 120)
        q = params.get("q")

        cache_key = (
            f"albums_index|order={order}|artist={artist}|q={q}|type={album_type}"
        )

        def _produce_qs():
            qs = CmsAlbum.objects.all()
            if artist:
                qs = qs.filter(artist_ids__contains=[artist])
            if q:
                qs = qs.filter(
                    models.Q(name__icontains=q)
                    | models.Q(artist_names_str__icontains=q)
                )
            if album_type:
                qs = qs.filter(album_type__iexact=album_type)

            if order == "release_asc":
                qs = qs.order_by("release_date", "name")
            elif order == "name_asc":
                qs = qs.order_by("name")
            else:  # release_desc per defecte
                qs = qs.order_by("-release_date", "name")
            return qs

        ids = self._cache_get_or_set(
            cache_key + "|ids",
            lambda: list(_produce_qs().values_list("id", flat=True)),
            timeout=120,
        )

        paginator = Paginator(ids, per)
        if paginator.count == 0:
            # cap resultat → no intentes obrir cap pàgina
            page = 1
            page_ids = []
        else:
            try:
                page_ids = paginator.page(page).object_list
            except EmptyPage:
                page = paginator.num_pages
                page_ids = paginator.page(page).object_list

        # Recuperem només la pàgina actual
        qs_page = CmsAlbum.objects.filter(id__in=page_ids)
        # Mantindre l’ordre de page_ids
        album_map = {a.id: a for a in qs_page}
        ordered = [album_map[i] for i in page_ids if i in album_map]

        items = [
            {
                "id": a.id,
                "image": a.image_url,
                "title": a.name,
                "subtitle": a.artist_names_str or "",
                "href": f"{self.url}albums/{slugify(a.name)}-{a.id}/",
                "badge": a.album_type,
            }
            for a in ordered
        ]

        # Xips d'ordenació
        base = f"{self.url}albums/"
        chips_order = []
        for key, label in [
            ("release_desc", "Data → més nou"),
            ("release_asc", "Data → més antic"),
            ("name_asc", "Nom (A→Z)"),
        ]:
            chips_order.append(
                {
                    "label": label,
                    "href": self._url_with(base, params, order=key, page=1),
                    "active": (order == key),
                }
            )

        chips_filters = []
        if artist:
            chips_filters.append(
                {
                    "label": f"Artista: {artist}",
                    "href": self._url_with(base, params, artist="", page=1),
                    "active": True,
                }
            )

        # Controls de pàgina
        num_pages = (
            paginator.num_pages or 1
        )  # quan no hi ha resultats, mostrem 1 per evitar " / 0"
        pager = {
            "page": page,
            "per": per,
            "num_pages": num_pages,
            "count": paginator.count,
            "has_prev": page > 1 and paginator.count > 0,
            "has_next": page < num_pages and paginator.count > 0,
            "prev_href": (
                self._url_with(base, params, page=page - 1)
                if page > 1 and paginator.count > 0
                else None
            ),
            "next_href": (
                self._url_with(base, params, page=page + 1)
                if page < num_pages and paginator.count > 0
                else None
            ),
        }

        # JSON endpoint via ?format=json
        if params.get("format") == "json":
            return JsonResponse({"items": items, "pager": pager, "params": params})

        type_options = [
            {"value": "", "label": "Tots els tipus"},
            {"value": "album", "label": "Àlbum"},
            {"value": "single", "label": "Single"},
        ]

        ctx = {
            "page": self,
            "section_title": "Àlbums",
            "items": items,
            "chips_order": chips_order,
            "chips_filters": chips_filters,
            "pager": pager,
            "params": params,
            "type_options": type_options,
            "album_type": album_type,
        }
        return render(request, "home/music_albums.html", ctx)

    @route(r"^api/albums/$", name="albums_api")
    def albums_api(self, request):
        # Proxy intern cap a llistat amb format=json
        request.GET = request.GET.copy()
        request.GET["format"] = "json"
        return self.albums_index(request)

    @route(r"^artists/$", name="artists_index")
    def artists_index(self, request):
        from .models import CmsArtista

        params = self._qsdict(request)
        order = params.get("order", "followers_desc")
        page = max(int(params.get("page", 1)), 1)
        per = min(max(int(params.get("per", 60)), 1), 200)
        q = params.get("q")

        territori = params.get("territori") or ""
        comarca = params.get("comarca") or ""
        localitat = params.get("localitat") or ""
        has_albums = params.get("has_albums") in ("1", "true", "on")

        def _produce_qs():
            qs = CmsArtista.objects.filter(live=True)
            if q:
                qs = qs.filter(nom__icontains=q)

            # filtres en cascada
            if territori:
                qs = qs.filter(territori=territori)
            if comarca:
                qs = qs.filter(comarca=comarca)
            if localitat:
                qs = qs.filter(localitat=localitat)
            if has_albums:
                # Import local per evitar circularitats
                from .models import CmsAlbum

                # EXISTS: true si hi ha almenys un Àlbum on l'array artist_ids conté este id_spotify
                subq = CmsAlbum.objects.filter(
                    artist_ids__contains=models.Func(
                        models.OuterRef("id_spotify"),
                        template="ARRAY[%(expressions)s]::text[]",
                    )
                )
                qs = qs.annotate(_has=models.Exists(subq)).filter(_has=True)

            if order == "followers_asc":
                qs = qs.order_by(F("followers").asc(nulls_last=True), "nom")
            elif order == "pop_asc":
                qs = qs.order_by(F("popularitat").asc(nulls_last=True), "nom")
            elif order == "pop_desc":
                qs = qs.order_by(F("popularitat").desc(nulls_last=True), "nom")
            elif order == "name_asc":
                qs = qs.order_by("nom")
            else:
                qs = qs.order_by(F("followers").desc(nulls_last=True), "nom")
            return qs

        # Opcions per als selects (distincts ordenats)
        territoris = list(
            CmsArtista.objects.filter(live=True).exclude(territori="")
            .values_list("territori", flat=True)
            .distinct()
            .order_by("territori")
        )

        if territori:
            comarques = list(
                CmsArtista.objects.filter(live=True, territori=territori)
                .exclude(comarca="")
                .values_list("comarca", flat=True)
                .distinct()
                .order_by("comarca")
            )
        else:
            comarques = []

        if territori and comarca:
            localitats = list(
                CmsArtista.objects.filter(live=True, territori=territori, comarca=comarca)
                .exclude(localitat="")
                .values_list("localitat", flat=True)
                .distinct()
                .order_by("localitat")
            )
        else:
            localitats = []

        paginator = Paginator(_produce_qs(), per)
        if paginator.count == 0:
            # Cap resultat: evitem intentar cridar paginator.page(0)
            page = 1
            page_qs = []
        else:
            try:
                page_qs = paginator.page(page)
            except EmptyPage:
                page = paginator.num_pages
                page_qs = paginator.page(page)

        # Si no hi ha resultats, source serà una llista buida; si no, .object_list
        source = page_qs.object_list if paginator.count > 0 else []

        items = [
            {
                "id": ar.id_spotify,
                "image": ar.imatge_url,
                "title": ar.nom,
                "subtitle": f"{ar.localitat} ({ar.comarca})" if ar.localitat else "Desconegut",
                "href": f"{self.url}artists/{slugify(ar.nom)}-{ar.id_spotify}/",
            }
            for ar in source
        ]

        base = f"{self.url}artists/"
        chips_order = []
        for key, label in [
            ("followers_desc", "Followers ↓"),
            ("followers_asc", "Followers ↑"),
            ("pop_desc", "Popularitat ↓"),
            ("pop_asc", "Popularitat ↑"),
            ("name_asc", "Nom (A→Z)"),
        ]:
            chips_order.append(
                {
                    "label": label,
                    "href": self._url_with(base, params, order=key, page=1),
                    "active": (order == key),
                }
            )

        base = f"{self.url}artists/"

        chips_filters = []
        if territori:
            chips_filters.append(
                {
                    "label": f"Territori: {territori}",
                    "href": self._url_with(
                        base, params, territori="", comarca="", localitat="", page=1
                    ),
                    "active": True,
                }
            )
        if comarca:
            chips_filters.append(
                {
                    "label": f"Comarca: {comarca}",
                    "href": self._url_with(
                        base, params, comarca="", localitat="", page=1
                    ),
                    "active": True,
                }
            )
        if localitat:
            chips_filters.append(
                {
                    "label": f"Localitat: {localitat}",
                    "href": self._url_with(base, params, localitat="", page=1),
                    "active": True,
                }
            )
        if has_albums:
            chips_filters.append(
                {
                    "label": "Amb àlbums recents",
                    "href": self._url_with(base, params, has_albums="", page=1),
                    "active": True,
                }
            )

        num_pages = paginator.num_pages or 1
        pager = {
            "page": page,
            "per": per,
            "num_pages": num_pages,
            "count": paginator.count,
            "has_prev": page > 1 and paginator.count > 0,
            "has_next": page < num_pages and paginator.count > 0,
            "prev_href": (
                self._url_with(base, params, page=page - 1)
                if page > 1 and paginator.count > 0
                else None
            ),
            "next_href": (
                self._url_with(base, params, page=page + 1)
                if page < num_pages and paginator.count > 0
                else None
            ),
        }

        if params.get("format") == "json":
            return JsonResponse({"items": items, "pager": pager, "params": params})

        ctx = {
            "page": self,
            "section_title": "Artistes",
            "items": items,
            "chips_order": chips_order,
            "pager": pager,
            "params": params,
            "territoris": territoris,
            "comarques": comarques,
            "localitats": localitats,
            "territori": territori,
            "comarca": comarca,
            "localitat": localitat,
            "has_albums": has_albums,
            "chips_filters": chips_filters,
        }
        return render(request, "home/music_artists.html", ctx)

    @route(r"^api/artists/$", name="artists_api")
    def artists_api(self, request):
        request.GET = request.GET.copy()
        request.GET["format"] = "json"
        return self.artists_index(request)

    @route(r"^songs/$", name="songs_index")
    def songs_index(self, request):
        from .models import CmsAlbum, CmsSong

        params = self._qsdict(request)
        order = params.get("order", "pop_desc")
        artist = params.get("artist")
        album = params.get("album")
        page = max(int(params.get("page", 1)), 1)
        per = min(max(int(params.get("per", 60)), 1), 200)
        q = params.get("q")

        def _produce_qs():
            qs = CmsSong.objects.all()
            if artist:
                qs = qs.filter(artist_ids__contains=[artist])
            if album:
                qs = qs.filter(album_id=album)
            if q:
                qs = qs.filter(
                    models.Q(name__icontains=q)
                    | models.Q(artist_names_str__icontains=q)
                )

            if order == "pop_asc":
                qs = qs.order_by("popularity", "name")
            elif order == "name_asc":
                qs = qs.order_by("name")
            else:
                qs = qs.order_by("-popularity", "name")  # default
            return qs

        paginator = Paginator(_produce_qs(), per)
        if paginator.count == 0:
            page = 1
            page_qs = []
        else:
            try:
                page_qs = paginator.page(page)
            except EmptyPage:
                page = paginator.num_pages
                page_qs = paginator.page(page)

        source = page_qs.object_list if paginator.count > 0 else []

        # Map d’imatges d’àlbum per a la pàgina actual (si hi ha resultats)
        album_ids = list({s.album_id for s in source if getattr(s, "album_id", None)})
        album_map = {
            a.id: a.image_url for a in CmsAlbum.objects.filter(id__in=album_ids)
        }

        items = []
        for s in source:
            subtitle = s.artist_names_str or ""
            if subtitle and s.popularity is not None:
                subtitle = f"{subtitle} · pop {s.popularity}"
            elif s.popularity is not None:
                subtitle = f"pop {s.popularity}"
            items.append(
                {
                    "id": s.id,
                    "image": album_map.get(s.album_id),
                    "title": s.name,
                    "subtitle": subtitle,
                    "href": f"{self.url}songs/{slugify(s.name)}-{s.id}/",
                }
            )

        base = f"{self.url}songs/"
        chips_order = []
        for key, label in [
            ("pop_desc", "Popularitat ↓"),
            ("pop_asc", "Popularitat ↑"),
            ("name_asc", "Nom (A→Z)"),
        ]:
            chips_order.append(
                {
                    "label": label,
                    "href": self._url_with(base, params, order=key, page=1),
                    "active": (order == key),
                }
            )

        chips_filters = []
        if artist:
            chips_filters.append(
                {
                    "label": f"Artista: {artist}",
                    "href": self._url_with(base, params, artist="", page=1),
                    "active": True,
                }
            )
        if album:
            chips_filters.append(
                {
                    "label": f"Àlbum: {album}",
                    "href": self._url_with(base, params, album="", page=1),
                    "active": True,
                }
            )

        num_pages = paginator.num_pages or 1
        pager = {
            "page": page,
            "per": per,
            "num_pages": num_pages,
            "count": paginator.count,
            "has_prev": page > 1 and paginator.count > 0,
            "has_next": page < num_pages and paginator.count > 0,
            "prev_href": (
                self._url_with(base, params, page=page - 1)
                if page > 1 and paginator.count > 0
                else None
            ),
            "next_href": (
                self._url_with(base, params, page=page + 1)
                if page < num_pages and paginator.count > 0
                else None
            ),
        }

        if params.get("format") == "json":
            return JsonResponse({"items": items, "pager": pager, "params": params})

        ctx = {
            "page": self,
            "section_title": "Cançons",
            "items": items,
            "chips_order": chips_order,
            "chips_filters": chips_filters,
            "pager": pager,
            "params": params,
        }
        return render(request, "home/music_songs.html", ctx)

    @route(r"^api/songs/$", name="songs_api")
    def songs_api(self, request):
        request.GET = request.GET.copy()
        request.GET["format"] = "json"
        return self.songs_index(request)
    
    @route(r"^rankings/$", name="rankings_index")
    def rankings_index(self, request):
        """
        Vista de rànquing setmanal fixat, extret EXCLUSIVAMENT de `ranking_setmanal`.
        Paràmetres:
          - territori: pv | cat | ib | altres | ppcc (default=ppcc)
          - date: YYYY-MM-DD (default=última data existent a la taula)
          - format=json per a API (llista de 40 ítems + metadades)
        """
        from .models import RankingSetmanal  # import local

        params = self._qsdict(request)
        territori = (params.get("territori") or "ppcc").lower()
        territori = territori if territori in ("pv", "cat", "ib", "altres", "ppcc") else "ppcc"

        # 1) Determinar la data (si no ve informada, última existent)
        sel_date = params.get("date")
        if sel_date:
            # validació mínima; si no és vàlida caurà a fallback després
            try:
                from datetime import date as _dt_date
                y, m, d = [int(x) for x in sel_date.split("-")]
                sel_date_obj = _dt_date(y, m, d)
            except Exception:
                sel_date = None

        if not sel_date:
            # última data disponible amb posicions (qualsevol territori)
            last = (
                RankingSetmanal.objects
                .order_by("-data")
                .values_list("data", flat=True)
                .first()
            )
            if not last:
                # Sense dades
                if params.get("format") == "json":
                    return JsonResponse({"items": [], "meta": {"error": "no_data"}}, status=200)
                return render(request, "home/rankings_weekly.html", {
                    "page": self,
                    "items": [],
                    "meta": {"error": "no_data"},
                })
            sel_date = str(last)
        
        # 2) Llista de dates disponibles (setmanes fixades) per omplir el <select>
        dates_available = list(
            RankingSetmanal.objects.order_by("-data").values_list("data", flat=True).distinct()
        )
        dates_available = [str(d) for d in dates_available]

        # 2) Construir el rànquing segons territori
        items = []
        if territori == "ppcc":
            # GENERAL: calculem el TOP40 només per id_canco i score,
            # i després enriqueix amb CmsSong/CmsAlbum (artistes, títol, caràtula)
            sql = """
                WITH agg AS (
                    SELECT id_canco, MAX(score_global) AS max_score
                    FROM ranking_setmanal
                    WHERE data = %s
                    GROUP BY id_canco
                ),
                top40 AS (
                    SELECT
                        id_canco,
                        max_score,
                        ROW_NUMBER() OVER (ORDER BY max_score DESC) AS posicio
                    FROM agg
                    ORDER BY max_score DESC
                    LIMIT 40
                )
                SELECT id_canco, max_score, posicio
                FROM top40
                ORDER BY posicio;
            """
            with connection.cursor() as cur:
                cur.execute(sql, [sel_date])
                rows = cur.fetchall()
                # Columns: id_canco, max_score, posicio

            # Manté l'ordre del rànquing
            top_ids = [r[0] for r in rows]

            # Enriquix amb CMS (artistes, títol, àlbum, caràtula)
            from .models import CmsSong, CmsAlbum  # import local

            songs_qs = CmsSong.objects.filter(id__in=top_ids)
            song_map = {s.id: s for s in songs_qs}

            album_ids = {
                getattr(song_map[i], "album_id", None)
                for i in top_ids
                if i in song_map and getattr(song_map[i], "album_id", None)
            }
            albums_qs = CmsAlbum.objects.filter(id__in=album_ids)
            album_map = {a.id: a for a in albums_qs}

            items = []
            for id_canco, max_score, posicio in rows:
                s = song_map.get(id_canco)
                # Camps base des de CMS
                titol = s.name if s else ""
                artistes = list(getattr(s, "artist_names", []) or [])
                album_id = getattr(s, "album_id", None)
                album = album_map.get(album_id)
                album_titol = getattr(album, "name", "") if album else ""
                album_data = getattr(album, "release_date", None) if album else None
                album_caratula_url = self._cover_url(getattr(album, "image_url", None)) if album else None

                items.append({
                    "id_canco": id_canco,
                    "titol": titol,
                    "artistes": artistes,
                    "album_titol": album_titol,
                    "album_id": album_id,
                    "album_data": album_data,
                    "album_caratula_url": album_caratula_url,
                    "score": float(max_score) if max_score is not None else None,
                    "posicio": posicio,
                    "territori": "ppcc",
                    "data": sel_date,
                })
        else:
            # TERRITORIAL: simplement llig des de ranking_setmanal i respecta posicions fixades
            qs = (
                RankingSetmanal.objects
                .filter(data=sel_date, territori=territori)
                .order_by("posicio")
            )[:40]
            for r in qs:
                items.append({
                    "id_canco": r.id_canco,
                    "titol": r.titol,
                    "artistes": r.artistes,
                    "album_titol": r.album_titol,
                    "album_id": r.album_id,
                    "album_data": r.album_data,
                    "album_caratula_url": self._cover_url(r.album_caratula_url),
                    "score": float(r.score_global) if r.score_global is not None else (float(r.score_setmanal) if r.score_setmanal is not None else None),
                    "posicio": r.posicio,
                    "territori": territori,
                    "data": sel_date,
                    "canvi_posicio": r.canvi_posicio,
                })

        meta = {
            "date": sel_date,
            "territori": territori,
            "count": len(items),
            "territoris_valids": ["ppcc", "pv", "cat", "ib", "altres"],
            "dates": dates_available,
        }

        if params.get("format") == "json":
            return JsonResponse({"items": items, "meta": meta})

        # HTML (necessitaràs plantilla `home/rankings_weekly.html`)
        ctx = {
            "page": self,
            "items": items,
            "meta": meta,
            "params": params,
        }
        return render(request, "home/rankings_weekly.html", ctx)

    @route(r"^api/rankings/$", name="rankings_api")
    def rankings_api(self, request):
        # Proxy per a JSON: /music/api/rankings/?territori=...&date=...
        request.GET = request.GET.copy()
        request.GET["format"] = "json"
        return self.rankings_index(request)

    # ---------- Detalls ----------

    @route(r"^albums/(?:(?P<slug>[-\w]+)-)?(?P<album_id>[^/]+)/$", name="album_detail")
    def album_detail(self, request, album_id, slug=None):
        from .models import CmsAlbum, CmsArtista, CmsSong

        cache_key = f"album_detail|{album_id}"

        def _produce():
            try:
                album = CmsAlbum.objects.get(pk=album_id)
            except CmsAlbum.DoesNotExist:
                return None
            songs = list(
                CmsSong.objects.filter(album_id=album.id).order_by("-popularity")
            )

            # Construïm llista d’artistes amb enllaç si existeixen
            ids = list(album.artist_ids or [])
            names = list(album.artist_names or [])
            idx = range(min(len(ids), len(names)))
            existing = set(
                CmsArtista.objects.filter(id_spotify__in=ids).values_list(
                    "id_spotify", flat=True
                )
            )
            artists = [
                {
                    "id": ids[i],
                    "name": names[i],
                    "href": (
                        f"{self.url}artists/{slugify(names[i])}-{ids[i]}/"
                        if ids[i] in existing
                        else None
                    ),
                }
                for i in idx
            ]

            return {"album": album, "songs": songs, "artists": artists}

        data = self._cache_get_or_set(cache_key, _produce, timeout=120)
        if not data:
            raise Http404("Àlbum no trobat")
        ctx = {"page": self, **data}
        return render(request, "home/music_detail_album.html", ctx)

    @route(
        r"^artists/(?:(?P<slug>[-\w]+)-)?(?P<artist_id>[^/]+)/$", name="artist_detail"
    )
    def artist_detail(self, request, artist_id, slug=None):
        from .models import CmsAlbum, CmsArtista

        cache_key = f"artist_detail|{artist_id}"

        def _produce():
            try:
                artist = CmsArtista.objects.get(pk=artist_id)
            except CmsArtista.DoesNotExist:
                return None
            albums = list(
                CmsAlbum.objects.filter(artist_ids__contains=[artist_id]).order_by(
                    "-release_date"
                )[:200]
            )
            return {"artist": artist, "albums": albums}

        data = self._cache_get_or_set(cache_key, _produce, timeout=120)
        if not data:
            raise Http404("Artista no trobat")
        ctx = {"page": self, **data}
        return render(request, "home/music_detail_artist.html", ctx)

    @route(r"^songs/(?:(?P<slug>[-\w]+)-)?(?P<song_id>[^/]+)/$", name="song_detail")
    def song_detail(self, request, song_id, slug=None):
        from .models import CmsAlbum, CmsArtista, CmsSong

        cache_key = f"song_detail|{song_id}"

        def _produce():
            try:
                song = CmsSong.objects.get(pk=song_id)
            except CmsSong.DoesNotExist:
                return None
            album = None
            if song.album_id:
                try:
                    album = CmsAlbum.objects.get(pk=song.album_id)
                except CmsAlbum.DoesNotExist:
                    album = None

            # Artistes enllaçables si existeixen
            ids = list(song.artist_ids or [])
            names = list(song.artist_names or [])
            idx = range(min(len(ids), len(names)))
            existing = set(
                CmsArtista.objects.filter(id_spotify__in=ids).values_list(
                    "id_spotify", flat=True
                )
            )
            artists = [
                {
                    "id": ids[i],
                    "name": names[i],
                    "href": (
                        f"{self.url}artists/{slugify(names[i])}-{ids[i]}/"
                        if ids[i] in existing
                        else None
                    ),
                }
                for i in idx
            ]

            return {"song": song, "album": album, "artists": artists}

        data = self._cache_get_or_set(cache_key, _produce, timeout=120)
        if not data:
            raise Http404("Cançó no trobada")
        ctx = {"page": self, **data}
        return render(request, "home/music_detail_song.html", ctx)


# --- Wrappers per a menú (pàgines reals) ---
class ArtistsPage(Page):
    """
    Wrapper 'Page' perquè 'Artistes' puga aparéixer al menú.
    Quan es visita, redirigeix a la subruta /music/artists/ existent.
    """

    parent_page_types = ["home.MusicIndexPage"]
    subpage_types = []
    max_count = 1  # opcional: només una

    def serve(self, request):
        # Redirigim a la subruta real
        parent = self.get_parent().specific
        return redirect(parent.url + "artists/")


class AlbumsPage(Page):
    """
    Wrapper 'Page' per a 'Àlbums' -> redirigeix a /music/albums/
    """

    parent_page_types = ["home.MusicIndexPage"]
    subpage_types = []
    max_count = 1

    def serve(self, request):
        parent = self.get_parent().specific
        return redirect(parent.url + "albums/")


class SongsPage(Page):
    """
    Wrapper 'Page' per a 'Cançons' -> redirigeix a /music/songs/
    """

    parent_page_types = ["home.MusicIndexPage"]
    subpage_types = []
    max_count = 1

    def serve(self, request):
        parent = self.get_parent().specific
        return redirect(parent.url + "songs/")

class RankingsPage(Page):
    """
    Wrapper 'Page' per a 'Rànquings' -> redirigeix a /music/rankings/
    """
    parent_page_types = ["home.MusicIndexPage"]
    subpage_types = []
    max_count = 1

    def serve(self, request):
        parent = self.get_parent().specific
        return redirect(parent.url + "rankings/")

# --- MAPES D'ARTISTES ---
class MapPage(RoutablePageMixin, Page):
    """
    Pàgina amb mapa interactiu Leaflet.
    Permet consultar artistes per territori, comarca o municipi.
    """

    template = "home/map_page.html"

    @route(r"^api/artistes/$", name="api_artistes")
    def api_artistes(self, request):
        from django.db.models import F
        from .models import CmsArtista

        level = request.GET.get("level")       # territori | comarca | municipi | None
        key = request.GET.get("key")           # valor del polígon clicat | None
        order = request.GET.get("order", "pop")  # alpha | pop

        # Mapegem level -> camp de la taula artistes
        field_map = {
            "territori": "territori",
            "comarca": "comarca",
            "municipi": "localitat",
        }

        if level and level not in field_map:
            return JsonResponse({"error": "level invalid"}, status=400)

        # [NOU — usa CmsArtista + live=True]
        base_qs = CmsArtista.objects.filter(live=True)

        # Query base
        if level and key:
            qs = base_qs.filter(**{f"{field_map[level]}__iexact": key})
        else:
            qs = base_qs

        # Ordenació
        if order == "pop":
            qs = qs.order_by(models.F("popularitat").desc(nulls_last=True), "nom")
        else:
            qs = qs.order_by("nom")

        data = [
            {
                "nom": a.nom,
                "territori": a.territori,
                "comarca": a.comarca,
                "municipi": a.localitat,
                "followers": a.followers,
                "popularitat": a.popularitat,
                "href": f"/music/artists/{slugify(a.nom)}-{a.id_spotify}/",
            }
            for a in qs
        ]
        return JsonResponse({"count": len(data), "items": data}, json_dumps_params={"ensure_ascii": False})

@register_snippet
class MainMenu(ClusterableModel):
    """
    Menú principal per 'Site'. Es pot editar des de Admin → Snippets.
    """

    site = models.OneToOneField(
        "wagtailcore.Site", on_delete=models.CASCADE, related_name="main_menu"
    )

    panels = [
        FieldPanel("site"),
        InlinePanel("items", label="Ítems de menú"),
    ]

    def __str__(self):
        return f"Menú principal — {self.site.hostname}"


class MenuItem(Orderable, ClusterableModel):
    menu = ParentalKey("home.MainMenu", related_name="items", on_delete=models.CASCADE)
    label = models.CharField(max_length=80)
    page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Opcional. Si es posa, té prioritat sobre 'page'.",
    )
    new_tab = models.BooleanField(default=False, help_text="Obrir en pestanya nova")

    panels = [
        FieldPanel("label"),
        FieldPanel("page"),
        FieldPanel("url"),
        FieldPanel("new_tab"),
        InlinePanel("children", label="Subenllaços (opcional)"),
    ]

    @property
    def resolved_url(self):
        return self.url or (self.page.url if self.page else "#")


class ChildMenuItem(Orderable):
    parent = ParentalKey(
        "home.MenuItem", related_name="children", on_delete=models.CASCADE
    )
    label = models.CharField(max_length=80)
    page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    url = models.CharField(max_length=255, blank=True)
    new_tab = models.BooleanField(default=False)

    panels = [
        FieldPanel("label"),
        FieldPanel("page"),
        FieldPanel("url"),
        FieldPanel("new_tab"),
    ]

    @property
    def resolved_url(self):
        return self.url or (self.page.url if self.page else "#")


@register_setting
class SiteDesign(BaseSiteSetting):
    # Camps que ara estàs usant a base.html dins de <style id="tq-brand">
    brand = models.CharField(
        max_length=7, blank=True, help_text="HEX principal, ex: #0047FF"
    )
    text = models.CharField(
        max_length=7, blank=True, help_text="Color text general, ex: #111111"
    )
    background = models.CharField(
        max_length=7, blank=True, help_text="Color fons pàgina, ex: #FFFFFF"
    )

    # Compatibilitat enrere: camps antics com a propietats
    @property
    def on_brand(self) -> str:
        # Ara el text damunt del brand utilitza el background
        return self.background or "#FFFFFF"

    @property
    def link(self) -> str:
        # L'accent/enllaç ara es resol a brand
        return self.brand or "#0047FF"

    header_height = models.PositiveIntegerField(
        default=96,
        validators=[MinValueValidator(56), MaxValueValidator(160)],
        help_text="Alçària header en px (56–160)",
    )

    body_font = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stack de font CSS, ex: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
    )

    site_name = models.CharField(
        max_length=120, blank=True, help_text="Nom curt del lloc"
    )

    show_site_name = models.BooleanField(
        default=True, help_text="Mostra el nom del lloc al costat del logo."
    )

    logo = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Logo principal",
    )

    # --- NOVETATS: icones i logo ---
    favicon = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Icona del lloc (es recomana PNG quadrat ≥ 180×180).",
    )

    logo_width = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(24), MaxValueValidator(600)],
        help_text="Amplària màxima del logo (px, 24–600). Deixa en blanc per defecte segur.",
    )
    logo_height = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(24), MaxValueValidator(200)],
        help_text="Alçària màxima del logo (px, 24–200). Deixa en blanc per defecte segur.",
    )

    # --- NOVETATS: maquetació global ---
    container_max_width = models.PositiveIntegerField(
        default=1180,
        validators=[MinValueValidator(960), MaxValueValidator(1600)],
        help_text="Amplària màxima del contenidor (px, 960–1600) per a header, cos i footer.",
    )
    container_gutter = models.PositiveIntegerField(
        default=16,
        validators=[MinValueValidator(8), MaxValueValidator(40)],
        help_text="Marge horitzontal intern (px, 8–40) del contenidor.",
    )

    # --- NOVETATS: tipografia (govern senzill) ---
    FONT_FAMILY_CHOICES = [
        ("system", "System UI (segur)"),
        ("inter", "Inter"),
        ("roboto", "Roboto"),
        ("merriweather", "Merriweather (serif)"),
    ]
    font_family = models.CharField(
        max_length=20,
        choices=FONT_FAMILY_CHOICES,
        default="system",
        help_text="Família tipogràfica principal.",
    )
    base_font_size_px = models.PositiveIntegerField(
        default=16,
        validators=[MinValueValidator(14), MaxValueValidator(20)],
        help_text="Cos de text base (px, 14–20).",
    )
    scale_ratio = models.FloatField(
        default=1.25,
        validators=[MinValueValidator(1.1), MaxValueValidator(1.5)],
        help_text="Relació d’escala H1–H6 a partir del cos base (1.1–1.5).",
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("site_name"),
                FieldPanel("show_site_name"),
                FieldPanel("logo"),
                FieldPanel("logo_width"),
                FieldPanel("logo_height"),
                FieldPanel("favicon"),
                HelpPanel(
                    content=(
                        "<p><strong>Consells:</strong> El logo es mostra <em>sense retallar</em> (contain). "
                        "Recomanat PNG/SVG horitzontal amb fons transparent, mida orientativa <code>320×120</code> (o pr\
oporció similar). "
                        "Si es veu massa gran o menut, ajusta amplària/alçària del logo als camps o deixa’ls en blanc pe\
r al valor per defecte.</p>"
                    )
                ),
            ],
            heading="Identitat (logo i icones)",
        ),
        MultiFieldPanel(
            [
                FieldPanel("font_family"),
                FieldPanel("base_font_size_px"),
                FieldPanel("scale_ratio"),
                FieldPanel("body_font"),
                HelpPanel(
                    content=(
                        "<p>La família escollida defineix l’aspecte general. "
                        "Usa <em>System UI</em> per màxima compatibilitat i rapidesa.</p>"
                    )
                ),
            ],
            heading="Tipografia",
        ),
        MultiFieldPanel(
            [
                FieldPanel("container_max_width"),
                FieldPanel("container_gutter"),
                FieldPanel("header_height"),
                HelpPanel(
                    content=(
                        "<p>El contenidor s’aplica a header, cos i footer. "
                        "En mòbil és fluid; els valors afecten sobretot escriptori/taula.</p>"
                    )
                ),
            ],
            heading="Maquetació global",
        ),
        MultiFieldPanel(
            [
                FieldPanel("brand"),
                FieldPanel("text"),
                FieldPanel("background"),
                HelpPanel(
                    content=(
                        "<p>Paleta mínima simplificada: "
                        "<em>brand</em> (color fort i accent), "
                        "<em>text</em> (text general i menú), "
                        "<em>background</em> (fons global i text damunt de brand).</p>"
                        "<p>Compatibilitat: <code>on_brand</code> ⇒ usa <code>background</code>; "
                        "<code>link</code> ⇒ usa <code>brand</code>.</p>"
                    )
                ),
            ],
            heading="Paleta de colors",
        ),
    ]

    class Meta:
        verbose_name = "Disseny del web"
