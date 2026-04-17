from django.contrib.auth.models import AbstractUser
from django.core.validators import URLValidator
from django.db import models

# S8: accept only http(s) in user-submitted URL fields. Django's default
# URLValidator also allows ftp/ftps; restrict to web schemes explicitly
# so a typo or malicious entry can't land with e.g. ftp:// data.
HTTP_ONLY_URL = URLValidator(schemes=["http", "https"])


class Usuari(AbstractUser):
    """Custom user model for TopQuaranta.

    Extends AbstractUser without extra fields for now. This allows adding
    fields later (e.g. artist verification status) without changing
    AUTH_USER_MODEL again.
    """

    class Meta(AbstractUser.Meta):
        db_table = "auth_user"
        verbose_name = "Usuari"
        verbose_name_plural = "Usuaris"


class UserArtista(models.Model):
    """Request to manage an existing artist's profile.

    A user can have multiple management requests (ForeignKey, not OneToOne).
    Each request links to an existing approved artist.
    """

    ESTAT_PENDENT = "pendent"
    ESTAT_APROVAT = "aprovat"
    ESTAT_REBUTJAT = "rebutjat"
    ESTAT_CHOICES = [
        (ESTAT_PENDENT, "Pendent"),
        (ESTAT_APROVAT, "Aprovat"),
        (ESTAT_REBUTJAT, "Rebutjat"),
    ]

    usuari = models.ForeignKey(
        Usuari,
        on_delete=models.CASCADE,
        related_name="artistes_vinculats",
    )
    artista = models.ForeignKey(
        "music.Artista",
        on_delete=models.CASCADE,
    )
    verificat = models.BooleanField(default=False)
    estat = models.CharField(
        max_length=10,
        choices=ESTAT_CHOICES,
        default=ESTAT_PENDENT,
    )
    sollicitud_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vinculació usuari-artista"
        verbose_name_plural = "Vinculacions usuari-artista"

    def __str__(self) -> str:
        status = "verificat" if self.verificat else self.estat
        return f"{self.usuari} → {self.artista.nom} ({status})"


class PropostaArtista(models.Model):
    """Proposal to add a new artist not yet in the system.

    Stores all relevant info the user provides. When staff approves,
    an Artista is created and optionally linked via UserArtista.
    """

    ESTAT_PENDENT = "pendent"
    ESTAT_APROVAT = "aprovat"
    ESTAT_REBUTJAT = "rebutjat"
    ESTAT_CHOICES = [
        (ESTAT_PENDENT, "Pendent"),
        (ESTAT_APROVAT, "Aprovat"),
        (ESTAT_REBUTJAT, "Rebutjat"),
    ]

    usuari = models.ForeignKey(
        Usuari,
        on_delete=models.CASCADE,
        related_name="propostes_artista",
    )
    # Artist info
    nom = models.CharField(max_length=255)
    justificacio = models.TextField()

    # Social links (all optional). S8: validators restricted to http/https.
    spotify_url = models.URLField(blank=True, validators=[HTTP_ONLY_URL])
    viasona_url = models.URLField(blank=True, validators=[HTTP_ONLY_URL])
    web_url = models.URLField(blank=True, validators=[HTTP_ONLY_URL])
    bandcamp_url = models.URLField(blank=True, validators=[HTTP_ONLY_URL])
    youtube_url = models.URLField(blank=True, validators=[HTTP_ONLY_URL])
    viquipedia_url = models.URLField(blank=True, validators=[HTTP_ONLY_URL])
    soundcloud_url = models.URLField(blank=True, validators=[HTTP_ONLY_URL])
    tiktok_url = models.URLField(blank=True, validators=[HTTP_ONLY_URL])
    facebook_url = models.URLField(blank=True, validators=[HTTP_ONLY_URL])

    # D3: list of Deezer IDs. Previously a comma-separated CharField; now a
    # JSONField so the ORM parses it for us. Default `list` so `.deezer_ids`
    # always iterates without a None-check.
    deezer_ids = models.JSONField(default=list, blank=True)

    # D4: list of location dicts: [{"municipi_id": 123} | {"manual": "..."}, …].
    # Previously a TextField with a JSON string we parsed by hand.
    localitzacions = models.JSONField(default=list, blank=True)

    # Status
    estat = models.CharField(
        max_length=10,
        choices=ESTAT_CHOICES,
        default=ESTAT_PENDENT,
    )
    # FK to the artist created from this proposal (set on approval)
    artista_creat = models.ForeignKey(
        "music.Artista",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="propostes_origen",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Proposta d'artista"
        verbose_name_plural = "Propostes d'artista"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.usuari} proposa: {self.nom} ({self.estat})"

    def get_deezer_id_list(self) -> list[int]:
        """Return Deezer IDs as a list of ints.

        D3: now that `deezer_ids` is a JSONField, the list is already
        structured — but this shim stays so callers don't care about the
        storage shape, and to coerce strings that sneak in via the form
        to int before they hit the downstream ORM.
        """
        out: list[int] = []
        for raw in self.deezer_ids or []:
            try:
                out.append(int(raw))
            except (TypeError, ValueError):
                continue
        return out
