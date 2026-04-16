from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Territori(models.Model):
    """
    Territory for Catalan-language music rankings.
    Managed via data migration, not admin.
    """

    codi = models.CharField(max_length=4, primary_key=True)
    nom = models.CharField(max_length=50)

    class Meta:
        ordering = ["codi"]
        verbose_name = "Territori"
        verbose_name_plural = "Territoris"

    def __str__(self) -> str:
        return self.nom


class Municipi(models.Model):
    """
    Municipality within the Catalan-speaking territories.

    Populated from the legacy 'municipis' table. Each municipality belongs
    to a comarca and a territory. Used as FK target for ArtistaLocalitat.
    """

    nom = models.CharField(max_length=255)
    comarca = models.CharField(max_length=255)
    territori = models.ForeignKey(
        Territori,
        on_delete=models.PROTECT,
        related_name="municipis",
    )

    class Meta:
        ordering = ["nom"]
        verbose_name = "Municipi"
        verbose_name_plural = "Municipis"
        unique_together = [("nom", "comarca")]

    def __str__(self) -> str:
        return f"{self.nom} ({self.comarca})"


class Artista(models.Model):
    """
    A music artist tracked by TopQuaranta.

    Territories are derived from ArtistaLocalitat → Municipi → Territori.
    The M2M 'territoris' is kept in sync automatically via signals.
    Artists can belong to multiple territories (e.g. Marala → CAT, VAL, BAL).
    A track appears in territory T if ANY of its artists belongs to T.
    """

    PERCENTATGE_FEMENI_CHOICES = [
        ("100", "100%"),
        ("50+", "50% o més"),
        ("<50", "Menys del 50%"),
        ("0", "0%"),
    ]

    spotify_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    # R10: `deezer_id` legacy direct field removed 2026-04-16. Use the
    # ArtistaDeezer M2M exclusively (via `deezer_id_principal` property or
    # `deezer_ids` related manager).
    lastfm_nom = models.CharField(
        max_length=255,
        help_text="Exact name for Last.fm API calls (case-sensitive).",
    )
    lastfm_mbid = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="MusicBrainz ID — improves Last.fm lookup accuracy.",
    )
    nom = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    territoris = models.ManyToManyField(
        Territori,
        related_name="artistes",
        blank=True,
        help_text="Auto-synced from ArtistaLocalitat. Do not edit directly.",
    )
    deezer_no_trobat = models.BooleanField(
        default=False,
        help_text="True if Deezer search failed ISRC validation — skip in future runs.",
    )
    # Discovery provenance
    auto_descobert = models.BooleanField(default=False)
    font_descoberta = models.CharField(
        max_length=50,
        blank=True,
        help_text="Source: 'viasona', 'collaborador', 'manual'.",
    )
    aprovat = models.BooleanField(
        default=True,
        db_index=True,
        help_text="False = pending human review in staff panel.",
    )

    # Deezer metadata (populated by obtenir_metadata)
    deezer_nb_fan = models.IntegerField(null=True, blank=True)
    deezer_nb_album = models.IntegerField(null=True, blank=True)
    deezer_nom = models.CharField(max_length=255, blank=True)
    deezer_nom_similitud = models.FloatField(null=True, blank=True)

    # Legacy location fields — kept for backwards compat during migration.
    # New code should use ArtistaLocalitat instead.
    localitat = models.CharField(max_length=255, blank=True)
    comarca = models.CharField(max_length=255, blank=True)
    provincia = models.CharField(max_length=255, blank=True)

    # Genre and gender representation
    genere = models.CharField(
        max_length=255, blank=True,
        help_text="Musical genre (free text).",
    )
    percentatge_femeni = models.CharField(
        max_length=10, blank=True, choices=PERCENTATGE_FEMENI_CHOICES,
        help_text="Female representation percentage.",
    )

    # Social links
    spotify_url = models.URLField(blank=True)
    viasona_url = models.URLField(blank=True)
    web_url = models.URLField(blank=True)
    bandcamp_url = models.URLField(blank=True)
    myspace_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    viquipedia_url = models.URLField(blank=True)
    soundcloud_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)

    last_checked_deezer = models.DateTimeField(
        null=True, blank=True,
        help_text="Last time Deezer was queried for new albums.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Artista"
        verbose_name_plural = "Artistes"

    def __str__(self) -> str:
        codis = ",".join(self.territoris.values_list("codi", flat=True))
        return f"{self.nom} ({codis})" if codis else self.nom

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            base = slugify(self.nom) or "artista"
            slug = base
            n = 1
            while Artista.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)

    def clean(self):
        # Validate that approved artists have at least one location.
        # Check new ArtistaLocalitat first; fall back to legacy fields.
        if self.aprovat and self.pk:
            has_new_loc = self.localitats.exists()
            has_legacy_loc = bool(self.localitat and self.comarca)
            if not has_new_loc and not has_legacy_loc:
                raise ValidationError(
                    "No es pot aprovar un artista sense almenys una localitat."
                )

    @property
    def deezer_id_principal(self) -> int | None:
        """Primary Deezer ID from ArtistaDeezer.

        R10: the direct `Artista.deezer_id` column was dropped; ArtistaDeezer
        is now the single source of truth. Returns the row flagged
        `principal=True`, or the first one if none is, or None if the
        artist has no Deezer link yet.
        """
        ad = self.deezer_ids.filter(principal=True).first()
        if ad:
            return ad.deezer_id
        ad = self.deezer_ids.first()
        return ad.deezer_id if ad else None

    @property
    def all_deezer_ids(self) -> list[int]:
        """All Deezer IDs for this artist."""
        return list(self.deezer_ids.values_list("deezer_id", flat=True))

    def get_territoris(self) -> list[str]:
        """Return list of territory codes for this artist."""
        return list(self.territoris.values_list("codi", flat=True))

    def sync_territoris_from_localitats(self) -> None:
        """Recompute M2M territoris from ArtistaLocalitat → Municipi → Territori.

        Called automatically by ArtistaLocalitat signals. If artist has no
        localitats at all, the M2M is left unchanged (preserves legacy data
        during migration). If all localitats have municipi=NULL, territory
        defaults to ALT.
        """
        if not self.pk:
            return
        localitats_qs = self.localitats.all()
        if not localitats_qs.exists():
            return  # No ArtistaLocalitat entries — keep legacy M2M
        # Collect territories from municipis
        territori_ids = set(
            localitats_qs.filter(municipi__isnull=False)
            .values_list("municipi__territori_id", flat=True)
        )
        # If all entries have municipi=NULL → non-PPCC artist → ALT
        if not territori_ids:
            territori_ids = {"ALT"}
        self.territoris.set(list(territori_ids))

    SOCIAL_LINK_FIELDS = [
        ("spotify_url", "Spotify"),
        ("viasona_url", "Viasona"),
        ("web_url", "Web"),
        ("bandcamp_url", "Bandcamp"),
        ("myspace_url", "Myspace"),
        ("youtube_url", "YouTube"),
        ("viquipedia_url", "Viquipèdia"),
        ("soundcloud_url", "SoundCloud"),
        ("tiktok_url", "TikTok"),
        ("facebook_url", "Facebook"),
    ]


class ArtistaDeezer(models.Model):
    """Links an Artista to one or more Deezer artist IDs."""

    artista = models.ForeignKey(
        Artista, on_delete=models.CASCADE, related_name="deezer_ids",
    )
    deezer_id = models.BigIntegerField(unique=True)
    principal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Artista Deezer ID"
        verbose_name_plural = "Artista Deezer IDs"

    def __str__(self) -> str:
        return f"{self.artista.nom} → {self.deezer_id}"


class ArtistaLocalitat(models.Model):
    """Links an artist to one or more municipalities (locations).

    Each entry represents one location the artist is associated with.
    Territories are derived automatically from municipi → territori.
    For non-PPCC artists, municipi is NULL and localitat_manual is used.
    """

    artista = models.ForeignKey(
        Artista,
        on_delete=models.CASCADE,
        related_name="localitats",
    )
    municipi = models.ForeignKey(
        Municipi,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="artistes_localitat",
        help_text="NULL for non-PPCC artists (Altres).",
    )
    localitat_manual = models.CharField(
        max_length=255,
        blank=True,
        help_text="Free text for non-PPCC locations or display override.",
    )
    descripcio = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional qualifier, e.g. 'nascut a' or 'resident a'.",
    )

    class Meta:
        verbose_name = "Localitat d'artista"
        verbose_name_plural = "Localitats d'artista"

    def __str__(self) -> str:
        if self.municipi:
            return f"{self.artista.nom} → {self.municipi.nom}"
        return f"{self.artista.nom} → {self.localitat_manual} (Altres)"

    @property
    def nom_display(self) -> str:
        """Human-readable location name."""
        if self.municipi:
            return self.municipi.nom
        return self.localitat_manual or "Altres"

    @property
    def comarca_display(self) -> str:
        """Human-readable comarca."""
        if self.municipi:
            return self.municipi.comarca
        return ""

    @property
    def territori_display(self) -> str:
        """Territory code derived from municipi."""
        if self.municipi:
            return self.municipi.territori_id
        return "ALT"


class Album(models.Model):
    TIPUS_CHOICES = [
        ("album", "Àlbum"),
        ("single", "Single"),
        ("ep", "EP"),
    ]

    spotify_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    deezer_id = models.BigIntegerField(unique=True, null=True, blank=True)
    artista = models.ForeignKey(Artista, on_delete=models.CASCADE, related_name="albums")
    nom = models.CharField(max_length=500)
    slug = models.SlugField(max_length=550, unique=True, blank=True)
    data_llancament = models.DateField(null=True, blank=True)
    tipus = models.CharField(max_length=10, choices=TIPUS_CHOICES, default="album")
    imatge_url = models.URLField(blank=True)
    cancons_obtingudes = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True when tracks have been fetched from Deezer.",
    )
    descartat = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True if all tracks were rejected. Skipped by obtenir_novetats.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_llancament"]

    def __str__(self) -> str:
        return f"{self.nom} — {self.artista.nom}"

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            base = slugify(self.nom) or "album"
            slug = base
            n = 1
            while Album.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)


class Canco(models.Model):
    """
    A single track. Only tracks released within the last 12 months are ingested.

    In the new model, a track exists ONCE (not duplicated per territory like legacy).
    Territory is derived from the artists:
      - artista: main artist (FK, for display and default lookups)
      - artistes_col: collaborating artists (M2M)
    A track appears in territory T if ANY artist (main or collaborator) belongs to T.
    """

    spotify_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    deezer_id = models.BigIntegerField(unique=True, null=True, blank=True)
    isrc = models.CharField(
        max_length=15,
        blank=True,
        help_text="International Standard Recording Code.",
    )
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="cancons")
    artista = models.ForeignKey(
        Artista,
        on_delete=models.CASCADE,
        related_name="cancons",
        help_text="Main artist (for display). Territory also from collaborators.",
    )
    artistes_col = models.ManyToManyField(
        Artista,
        related_name="participacions",
        blank=True,
        help_text="Collaborating artists. Track appears in their territories too.",
    )
    nom = models.CharField(max_length=500)
    lastfm_nom = models.CharField(
        max_length=500,
        blank=True,
        help_text="Track name as returned by Last.fm (may differ from Spotify).",
    )
    lastfm_mbid = models.CharField(max_length=50, blank=True)
    lastfm_verificat = models.BooleanField(default=False)
    # R5: "Last.fm's autocorrect of our query IS the correct track".
    # When True, obtenir_senyal stops flagging SenyalDiari rows for this
    # track as corrected even when the returned names differ from what
    # we sent. Flipped by staff from /staff/senyal/ after reviewing a
    # drift flag and deciding Last.fm was right.
    lastfm_confirmed = models.BooleanField(default=False)
    durada_ms = models.IntegerField(null=True, blank=True)
    preview_url = models.URLField(max_length=500, blank=True)
    data_llancament = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Tracks older than 12 months are excluded from ingestion.",
    )
    activa = models.BooleanField(default=True, db_index=True)
    verificada = models.BooleanField(
        default=False,
        db_index=True,
        help_text="False = pending admin review. Only verified tracks enter the ranking.",
    )
    ml_classe = models.CharField(max_length=1, blank=True, db_index=True)
    ml_confianca = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Cançó"
        verbose_name_plural = "Cançons"

    def __str__(self) -> str:
        return f"{self.nom} — {self.artista.nom}"

    @property
    def lastfm_lookup_nom(self) -> str:
        """Return the best name for Last.fm API calls."""
        return self.lastfm_nom if self.lastfm_nom else self.nom

    def get_territoris(self) -> set[str]:
        """
        Return all territories this track should appear in.
        Union of main artist's territories + all collaborators' territories.
        """
        codis = set(self.artista.territoris.values_list("codi", flat=True))
        codis.update(
            Territori.objects.filter(
                artistes__participacions=self
            ).values_list("codi", flat=True)
        )
        return codis


class HistorialRevisio(models.Model):
    DECISIONS = [
        ("aprovada", "Aprovada"),
        ("rebutjada", "Rebutjada"),
    ]
    MOTIUS = [
        ("ok", "En català i correcte"),
        ("no_catala", "La cançó no és en català"),
        ("artista_incorrecte", "El perfil Deezer no és el nostre artista"),
        ("album_incorrecte", "L'àlbum sencer no pertany al nostre artista"),
        ("no_musica", "No és música (podcast, audiollibre...)"),
    ]

    canco_deezer_id = models.BigIntegerField(null=True, blank=True)
    canco_spotify_id = models.CharField(max_length=50, blank=True)
    canco_isrc = models.CharField(max_length=20, blank=True)

    canco_nom = models.CharField(max_length=500)
    artista_nom = models.CharField(max_length=255)
    artista_territori = models.CharField(max_length=10, blank=True)
    album_nom = models.CharField(max_length=500, blank=True)
    data_llancament = models.DateField(null=True, blank=True)
    isrc_prefix = models.CharField(max_length=5, blank=True)

    artista_deezer_id = models.BigIntegerField(null=True, blank=True)
    artista_deezer_nb_fan = models.IntegerField(null=True, blank=True)
    artista_deezer_nb_album = models.IntegerField(null=True, blank=True)
    artista_nom_deezer = models.CharField(max_length=255, blank=True)
    artista_nom_similitud = models.FloatField(null=True, blank=True)

    ml_classe_decisio = models.CharField(
        max_length=1, blank=True,
        help_text="ML class at the time of decision.",
    )
    ml_confianca_decisio = models.FloatField(
        null=True, blank=True,
        help_text="ML confidence at the time of decision.",
    )

    decisio = models.CharField(max_length=20, choices=DECISIONS)
    motiu = models.CharField(max_length=50, choices=MOTIUS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Historial de revisió"
        verbose_name_plural = "Historial de revisions"
        indexes = [
            models.Index(fields=["decisio", "motiu"]),
            models.Index(fields=["canco_isrc"]),
            models.Index(fields=["artista_deezer_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.canco_nom} — {self.decisio} ({self.motiu})"


class StaffAuditLog(models.Model):
    """R9: immutable record of every destructive or consequential staff action.

    Append-only log. The UI at /staff/auditlog/ is read-only; by convention,
    nothing in the codebase deletes or mutates rows after creation. Actor,
    action, and target snapshot are captured so the log remains meaningful
    even if the target record is later deleted.

    `metadata` is a JSON blob for action-specific context — e.g. motiu of
    a rejection, the field diff of a config change, the source/target of a
    merge. Keep keys stable (documented where each action site creates
    them) so the audit view can format them consistently.
    """

    # Action taxonomy. Extend conservatively — every new value should be
    # usable as a filter on the audit page.
    ACTION_CHOICES = [
        # Cançons
        ("canco_aprovar", "Cançó: aprovar"),
        ("canco_rebutjar", "Cançó: rebutjar"),
        ("canco_rebutjar_album", "Cançó: rebutjar àlbum sencer"),
        ("canco_edit", "Cançó: edició"),
        # Artistes
        ("artista_aprovar", "Artista: aprovar"),
        ("artista_rebutjar", "Artista: rebutjar"),
        ("artista_marcar_sense_deezer", "Artista: marcar sense Deezer"),
        ("artista_fusionar", "Artista: fusionar"),
        ("artista_edit", "Artista: edició"),
        # Artistes pendents (auto-discovered)
        ("pendent_aprovar", "Pendent: aprovar"),
        ("pendent_descartar", "Pendent: descartar"),
        # Àlbums
        ("album_edit", "Àlbum: edició"),
        ("album_descartar", "Àlbum: descartar"),
        # Propostes d'artistes nous
        ("proposta_aprovar", "Proposta: aprovar"),
        ("proposta_rebutjar", "Proposta: rebutjar"),
        # Sol·licituds de gestió
        ("sollicitud_aprovar", "Sol·licitud: aprovar"),
        ("sollicitud_rebutjar", "Sol·licitud: rebutjar"),
        # Configuració global
        ("config_update", "Configuració global: actualitzada"),
        # Usuaris
        ("usuari_desactivar", "Usuari: desactivar"),
        ("usuari_reactivar", "Usuari: reactivar"),
        ("usuari_reset_2fa", "Usuari: reset 2FA"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_audit_entries",
        help_text="Staff user who performed the action. NULL if actor was "
                  "deleted — the action itself is still in the record.",
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)

    # Target snapshot — so the row remains meaningful after the target goes.
    target_type = models.CharField(
        max_length=30, blank=True,
        help_text='e.g. "Canco", "Artista", "Album", "Proposta", "Config".',
    )
    target_id = models.BigIntegerField(null=True, blank=True)
    target_label = models.CharField(
        max_length=500, blank=True,
        help_text="Human-readable identifier of the target at action time.",
    )

    # Action-specific context (reason, diff, counts, …). No schema.
    metadata = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Entrada d'auditoria staff"
        verbose_name_plural = "Auditoria staff"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
        ]

    def __str__(self) -> str:
        who = self.actor.email if self.actor_id else "(deleted user)"
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {who} · {self.action} · {self.target_label}"
