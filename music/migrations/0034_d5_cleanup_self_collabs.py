"""D5: remove existing self-collabs from Canco.artistes_col.

A Canco must not list its own main Artista as a collaborator. The Deezer
contributor parsing occasionally produced these (7 rows in production).
The m2m_changed signal in music/signals.py prevents future ones.

Irreversible: we can't rebuild the removed rows without running the
contributor sync again, so the reverse is a no-op.
"""

from django.db import migrations


def cleanup_self_collabs(apps, schema_editor):
    # Portable form (works on PostgreSQL and SQLite, unlike DELETE ... USING
    # which is Postgres-only). The EXISTS subquery matches through rows
    # whose (canco_id, artista_id) pair matches a Canco's (id, artista_id).
    with schema_editor.connection.cursor() as cur:
        cur.execute(
            """
            DELETE FROM music_canco_artistes_col
            WHERE EXISTS (
                SELECT 1
                FROM music_canco
                WHERE music_canco.id = music_canco_artistes_col.canco_id
                  AND music_canco.artista_id = music_canco_artistes_col.artista_id
            );
            """
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("music", "0033_p3_historial_indexes"),
    ]

    operations = [
        migrations.RunPython(cleanup_self_collabs, noop),
    ]
