from django.db import models


class Territori(models.Model):
    """
    Territory for Catalan-language music rankings.
    Fixed set: CAT, VAL, BAL. Managed via data migration, not admin.
    """

    codi = models.CharField(max_length=3, primary_key=True)
    nom = models.CharField(max_length=50)

    class Meta:
        ordering = ["codi"]
        verbose_name = "Territori"
        verbose_name_plural = "Territoris"

    def __str__(self) -> str:
        return self.nom


class Artista(models.Model):
    """
    A music artist tracked by TopQuaranta.

    Territory is a manually curated field — Last.fm has no geographic signal.
    Artists can belong to multiple territories (e.g. Marala → CAT, VAL, BAL).
    A track appears in territory T if ANY of its artists belongs to T.
    """

    spotify_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    deezer_id = models.BigIntegerField(unique=True, null=True, blank=True)
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
    territoris = models.ManyToManyField(
        Territori,
        related_name="artistes",
        blank=True,
        help_text="Territories this artist belongs to. Tracks appear in all.",
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
        help_text="False = pending human review in Wagtail admin.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Artista"
        verbose_name_plural = "Artistes"

    def __str__(self) -> str:
        codis = ",".join(self.territoris.values_list("codi", flat=True))
        return f"{self.nom} ({codis})" if codis else self.nom

    def get_territoris(self) -> list[str]:
        """Return list of territory codes for this artist."""
        return list(self.territoris.values_list("codi", flat=True))


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
    data_llancament = models.DateField(null=True, blank=True)
    tipus = models.CharField(max_length=10, choices=TIPUS_CHOICES, default="album")
    imatge_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_llancament"]

    def __str__(self) -> str:
        return f"{self.nom} — {self.artista.nom}"


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
    durada_ms = models.IntegerField(null=True, blank=True)
    data_llancament = models.DateField(
        null=True,
        blank=True,
        help_text="Tracks older than 12 months are excluded from ingestion.",
    )
    activa = models.BooleanField(default=True)
    verificada = models.BooleanField(
        default=False,
        help_text="False = pending admin review. Only verified tracks enter the ranking.",
    )
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
