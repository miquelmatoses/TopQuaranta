from django.db import models

from music.models import Canco


class ConfiguracioGlobal(models.Model):
    """
    Ranking algorithm coefficients. Single-row table.
    Migrated from legacy `configuracio_global`.
    """

    dia_setmana_ranking = models.IntegerField(default=6)
    penalitzacio_descens = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.025
    )
    exponent_penalitzacio_antiguitat = models.DecimalField(
        max_digits=5, decimal_places=2, default=2.5
    )
    max_factor_a = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    max_factor_b = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    max_factor_c = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    max_factor_final = models.DecimalField(max_digits=5, decimal_places=2, default=1.5)
    penalitzacio_album_per_canco = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.25
    )
    penalitzacio_artista_per_canco = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.2
    )
    coeficient_penalitzacio_top = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.075
    )
    penalitzacio_setmana_0 = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.1
    )
    penalitzacio_setmana_1 = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.05
    )
    penalitzacio_setmana_2 = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.0
    )
    suavitat = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)
    min_cancons_ranking_propi = models.IntegerField(default=20)

    class Meta:
        verbose_name = "Configuració global"
        verbose_name_plural = "Configuració global"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class IngestaDiari(models.Model):
    """
    Daily Last.fm snapshot per track.
    Stores raw cumulative values. One row per (canco, data).
    """

    canco = models.ForeignKey(Canco, on_delete=models.CASCADE, related_name="ingestes")
    data = models.DateField()

    lastfm_playcount = models.BigIntegerField(null=True)
    lastfm_listeners = models.IntegerField(null=True)

    score_entrada = models.FloatField(
        null=True,
        help_text="Normalized score (0-100) for the ranking algorithm.",
    )

    error = models.BooleanField(default=False)
    error_msg = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("canco", "data")]
        ordering = ["-data"]
        indexes = [
            models.Index(fields=["canco", "data"]),
            models.Index(fields=["data", "error"]),
        ]

    def __str__(self) -> str:
        return f"{self.canco} — {self.data}"


class RankingSetmanal(models.Model):
    """Weekly ranking result. setmana = Monday of the ranking week (ISO)."""

    canco = models.ForeignKey(Canco, on_delete=models.CASCADE, related_name="rankings")
    territori = models.CharField(max_length=4)
    setmana = models.DateField()
    posicio = models.PositiveSmallIntegerField()
    score_setmanal = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("canco", "territori", "setmana")]
        ordering = ["territori", "posicio"]
        indexes = [models.Index(fields=["setmana", "territori"])]

    def __str__(self) -> str:
        return f"#{self.posicio} {self.canco.nom} ({self.territori}) — {self.setmana}"
