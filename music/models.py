from django.db import models


class Artista(models.Model):
    """
    A music artist tracked by TopQuaranta.

    Territory is a manually curated field — Last.fm has no geographic signal.
    Artists with territori='ALL' appear in all three territory rankings.
    """

    TERRITORI_CHOICES = [
        ("CAT", "Catalunya"),
        ("VAL", "País Valencià"),
        ("BAL", "Illes Balears"),
        ("ALL", "Tots els territoris"),
    ]

    spotify_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
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
    territori = models.CharField(max_length=3, choices=TERRITORI_CHOICES, default="CAT")
    actiu = models.BooleanField(default=True)

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
        return f"{self.nom} ({self.territori})"

    def get_territoris(self) -> list[str]:
        """Expand 'ALL' into individual territory codes."""
        if self.territori == "ALL":
            return ["CAT", "VAL", "BAL"]
        return [self.territori]


class Album(models.Model):
    TIPUS_CHOICES = [
        ("album", "Àlbum"),
        ("single", "Single"),
        ("ep", "EP"),
    ]

    spotify_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
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
    Territory comes from the artist.
    """

    spotify_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
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
        help_text="Denormalized from album for query performance.",
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
