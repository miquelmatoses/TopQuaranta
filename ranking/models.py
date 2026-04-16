from decimal import Decimal

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

    # Defaults are Decimal(str) — never float — so full_clean() doesn't trip
    # on imprecise float → Decimal round-tripping (e.g. 0.025 becoming
    # 0.02500000000000000138...).
    dia_setmana_ranking = models.IntegerField(default=6, validators=_DAY_RANGE)
    penalitzacio_descens = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=Decimal("0.025"),
        validators=_PENALTY_RANGE,
    )
    exponent_penalitzacio_antiguitat = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("2.5"),
        validators=_EXPONENT_RANGE,
    )
    max_factor_a = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.0"),
        validators=_FACTOR_RANGE,
    )
    max_factor_b = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.0"),
        validators=_FACTOR_RANGE,
    )
    max_factor_c = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.0"),
        validators=_FACTOR_RANGE,
    )
    max_factor_final = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.5"),
        validators=_FACTOR_RANGE,
    )
    penalitzacio_album_per_canco = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=Decimal("0.25"),
        validators=_PENALTY_RANGE,
    )
    penalitzacio_artista_per_canco = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=Decimal("0.2"),
        validators=_PENALTY_RANGE,
    )
    coeficient_penalitzacio_top = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=Decimal("0.075"),
        validators=_PENALTY_RANGE,
    )
    penalitzacio_setmana_0 = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=Decimal("0.1"),
        validators=_PENALTY_RANGE,
    )
    penalitzacio_setmana_1 = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=Decimal("0.05"),
        validators=_PENALTY_RANGE,
    )
    penalitzacio_setmana_2 = models.DecimalField(
        max_digits=5,
        decimal_places=3,
        default=Decimal("0.0"),
        validators=_PENALTY_RANGE,
    )
    suavitat = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("5.0"),
        validators=_SMOOTH_RANGE,
    )
    min_cancons_ranking_propi = models.IntegerField(
        default=20,
        validators=_COUNT_RANGE,
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

    # R2: SET_NULL so historical signal survives artist / track deletions.
    # A null canco row becomes an anonymous data point; it's raw Last.fm
    # telemetry, there's no snapshot name to preserve here.
    canco = models.ForeignKey(
        Canco,
        on_delete=models.SET_NULL,
        null=True,
        related_name="senyals",
    )
    data = models.DateField()

    lastfm_playcount = models.BigIntegerField(null=True)
    lastfm_listeners = models.IntegerField(null=True)

    # R5: Last.fm with autocorrect=1 can silently return a different track —
    # we ask for "Mira / Artist X", Last.fm answers with "Mira / Artist Y"
    # data because it "thinks" we meant them. Store what the API actually
    # returned so we can flag silent drift. `corregit` is set at ingest
    # time when the returned names diverge significantly from what we
    # asked for (see obtenir_senyal._detect_drift).
    lastfm_returned_track = models.CharField(max_length=500, blank=True)
    lastfm_returned_artista = models.CharField(max_length=255, blank=True)
    corregit = models.BooleanField(default=False, db_index=True)

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
            models.Index(fields=["data", "corregit"]),
        ]

    def __str__(self) -> str:
        return f"{self.canco} — {self.data}"


class RankingSetmanal(models.Model):
    """Weekly ranking result. setmana = Monday of the ranking week (ISO).

    This is the cultural archive. Once a row is written it must remain
    reproducible and displayable forever, so we:

    - R2: keep the row even if the Canco/Artista that produced it is
      deleted (on_delete=SET_NULL + name/artist snapshots).
    - R1: freeze the algorithm identity (algorithm_version) and the
      coefficient set used (config_snapshot) so future code changes can
      never silently alter what this week's ranking was.
    """

    # R2: SET_NULL so deleting an artist or track does not wipe their
    # historical chart positions. unique_together is per (canco, ...),
    # which tolerates null canco because Postgres treats NULLs as distinct.
    canco = models.ForeignKey(
        Canco,
        on_delete=models.SET_NULL,
        null=True,
        related_name="rankings",
    )
    territori = models.CharField(max_length=4)
    setmana = models.DateField()
    posicio = models.PositiveSmallIntegerField()
    score_setmanal = models.FloatField()

    # R2: snapshots so the row remains self-describing if canco is NULL.
    canco_nom_snapshot = models.CharField(max_length=500, blank=True)
    artista_nom_snapshot = models.CharField(max_length=255, blank=True)

    # R1: algorithm provenance. algorithm_version is a semantic tag we
    # bump when the ranking formula changes in a user-visible way.
    # config_snapshot is the set of coefficients (ConfiguracioGlobal)
    # that produced this row. Both let us recompute a historical ranking
    # deterministically — or at least prove what computed it.
    algorithm_version = models.CharField(max_length=20, default="v1.0")
    config_snapshot = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("canco", "territori", "setmana")]
        ordering = ["territori", "posicio"]
        indexes = [models.Index(fields=["setmana", "territori"])]

    def __str__(self) -> str:
        nom = self.canco.nom if self.canco_id else (self.canco_nom_snapshot or "?")
        return f"#{self.posicio} {nom} ({self.territori}) — {self.setmana}"


class RankingProvisional(models.Model):
    """
    Rolling daily ranking. Recalculated every day at 07:00.
    Truncated and rebuilt on each run — not a historical record.
    """

    # R2: SET_NULL for consistency with the rest of the ranking stack,
    # though provisional rows are rebuilt daily so the guarantee is
    # weaker here. No snapshot — a null canco is effectively a tombstone
    # that the next rebuild will replace.
    canco = models.ForeignKey(
        Canco,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ranking_provisional",
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
