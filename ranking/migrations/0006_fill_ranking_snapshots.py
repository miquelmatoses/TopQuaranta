"""R1 + R2: backfill snapshot and config_snapshot on existing RankingSetmanal.

Schema migration 0005 added empty columns. This migration fills them:
- canco_nom_snapshot / artista_nom_snapshot: copy from current Canco / Artista.
- config_snapshot: the ConfiguracioGlobal values at migration time.
  Good-enough approximation for the 182 rows written before R1 existed;
  from now on calcular_ranking writes the real snapshot per row.
- algorithm_version: already defaulted to "v1.0" by the AddField operation.
"""

from decimal import Decimal

from django.db import migrations


CONFIG_FIELDS = [
    "dia_setmana_ranking", "penalitzacio_descens",
    "exponent_penalitzacio_antiguitat",
    "max_factor_a", "max_factor_b", "max_factor_c", "max_factor_final",
    "penalitzacio_album_per_canco", "penalitzacio_artista_per_canco",
    "coeficient_penalitzacio_top",
    "penalitzacio_setmana_0", "penalitzacio_setmana_1", "penalitzacio_setmana_2",
    "suavitat", "min_cancons_ranking_propi",
]


def _decimal_to_float(value):
    return float(value) if isinstance(value, Decimal) else value


def forwards(apps, schema_editor):
    ConfiguracioGlobal = apps.get_model("ranking", "ConfiguracioGlobal")
    RankingSetmanal = apps.get_model("ranking", "RankingSetmanal")

    cfg = ConfiguracioGlobal.objects.filter(pk=1).first()
    if cfg is None:
        snapshot = None
    else:
        snapshot = {
            field: _decimal_to_float(getattr(cfg, field))
            for field in CONFIG_FIELDS
        }

    # Fill snapshots + config. Use a single UPDATE per row with bulk_update
    # for efficiency, but 182 rows is tiny so a simple loop is fine.
    updated = 0
    for row in RankingSetmanal.objects.select_related("canco", "canco__artista"):
        changed = False
        if not row.canco_nom_snapshot and row.canco_id and row.canco is not None:
            row.canco_nom_snapshot = (row.canco.nom or "")[:500]
            changed = True
        if not row.artista_nom_snapshot and row.canco_id and row.canco is not None:
            row.artista_nom_snapshot = (row.canco.artista.nom or "")[:255]
            changed = True
        if row.config_snapshot is None and snapshot is not None:
            row.config_snapshot = snapshot
            changed = True
        if changed:
            row.save(update_fields=[
                "canco_nom_snapshot", "artista_nom_snapshot", "config_snapshot",
            ])
            updated += 1
    print(f"  RankingSetmanal: backfilled snapshots for {updated} rows")


def backwards(apps, schema_editor):
    # Leaving snapshots in place on rollback is harmless — the schema
    # migration (0005) will drop the columns anyway.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("ranking", "0005_ranking_reproducibility_and_set_null"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
