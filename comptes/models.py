from django.contrib.auth.models import AbstractUser
from django.db import models


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
    """Links a registered user to an artist for the verified artist portal."""

    usuari = models.OneToOneField(Usuari, on_delete=models.CASCADE)
    artista = models.ForeignKey("music.Artista", on_delete=models.CASCADE)
    verificat = models.BooleanField(default=False)
    sollicitud_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vinculació usuari-artista"
        verbose_name_plural = "Vinculacions usuari-artista"

    def __str__(self) -> str:
        status = "verificat" if self.verificat else "pendent"
        return f"{self.usuari} → {self.artista.nom} ({status})"
