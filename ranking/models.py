from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from music.models import Canco

# R8: bounds on ranking coefficients. A typo (0.25 -> 25) or an accidental
# negative value could wipe out the ranking for a week. We enforce sensible
# ranges at the model level so full_clean() and admin-style edits reject
# nonsense before it persists.
#
# Conservative ranges:
#   - Factors / multipliers: [0, 5]  (defaults are all <= 1.5)
#   - Penalty coefficients:  [0, 1]  (no negative penalties; never > 100%)
#   - Exponents:             [0, 10]
#   - Smoothing:             [0, 100]
#   - Threshold counts:      [0, 10000]
#   - Day-of-week:           [0, 6]

_FACTOR_RANGE = [MinValueValidator(0), MaxValueValidator(5)]
_PENALTY_RANGE = [MinValueValidator(0), MaxValueValidator(1)]
_EXPONENT_RANGE = [MinValueValidator(0), MaxValueValidator(10)]
_SMOOTH_RANGE = [MinValueValidator(0), MaxValueValidator(100)]
_COUNT_RANGE = [MinValueValidator(0), MaxValueValidator(10000)]
_DAY_RANGE = [MinValueValidator(0), MaxValueValidator(6)]


class ConfiguracioGlobal(models.Model):
    """
    Ranking algorithm coefficients. Single-row table.
    Migrated from legacy `configuracio_global`.
    """

    dia_setmana_ranking = models.IntegerField(default=6, validators=_DAY_RANGE)
    penalitzacio_descens = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.025, validators=_PENALTY_RANGE,
    )
    exponent_penalitzacio_antiguitat = models.DecimalField(
        max_digits=5, decimal_places=2, default=2.5, validators=_EXPONENT_RANGE,
    )
    max_factor_a = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.0, validators=_FACTOR_RANGE,
    )
    max_factor_b = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.0, validators=_FACTOR_RANGE,
    )
    max_factor_c = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.0, validators=_FACTOR_RANGE,
    )
    max_factor_final = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.5, validators=_FACTOR_RANGE,
    )
    penalitzacio_album_per_canco = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.25, validators=_PENALTY_RANGE,
    )
    penalitzacio_artista_per_canco = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.2, validators=_PENALTY_RANGE,
    )
    coeficient_penalitzacio_top = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.075, validators=_PENALTY_RANGE,
    )
    penalitzacio_setmana_0 = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.1, validators=_PENALTY_RANGE,
    )
    penalitzacio_setmana_1 = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.05, validators=_PENALTY_RANGE,
    )
    penalitzacio_setmana_2 = models.DecimalField(
        max_digits=5, decimal_places=3, default=0.0, validators=_PENALTY_RANGE,
    )
    suavitat = models.DecimalField(
        max_digits=5, decimal_places=2, default=5.0, validators=_SMOOTH_RANGE,
    )
    min_cancons_ranking_propi = models.IntegerField(
        default=20, validators=_COUNT_RANGE,
    )

    class Meta:
        verbose_name = "Configuració global"
        verbose_name_plural = "Configuració global"

    def save(self, *args, **kwargs):
        self.pk = 1
        # R8: ensure validators run on every save, including admin-form saves.
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SenyalDiari(models.Model):
    """
    Daily Last.fm snapshot per track.
    Stores raw cumulative values. One row per (canco, data).
    """

    canco = models.ForeignKey(Canco, on_delete=models.CASCADE, related_name="senyals")
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


class RankingProvisional(models.Model):
    """
    Rolling daily ranking. Recalculated every day at 07:00.
    Truncated and rebuilt on each run — not a historical record.
    """

    canco = models.ForeignKey(
        Canco, on_delete=models.CASCADE, related_name="ranking_provisional"
    )
    territori = models.CharField(max_length=4)
    posicio = models.PositiveSmallIntegerField()
    score_setmanal = models.FloatField()
    lastfm_playcount = models.IntegerField(null=True)
    dies_en_top = models.IntegerField(null=True)
    data_calcul = models.DateField(auto_now=True)

    class Meta:
        unique_together = [("canco", "territori")]
        ordering = ["territori", "posicio"]
        indexes = [models.Index(fields=["territori", "posicio"])]

    def __str__(self) -> str:
        return f"#{self.posicio} {self.canco.nom} ({self.territori})"
