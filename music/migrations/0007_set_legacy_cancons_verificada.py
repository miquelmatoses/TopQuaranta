"""
Data migration: mark legacy cançons (with spotify_id) as verificada=True.

These tracks came from importar_legacy and represent the manually curated
catalogue. New tracks from ingestar_metadata (Deezer) keep verificada=False
until an admin reviews them.
"""

from django.db import migrations


def set_legacy_verificada(apps, schema_editor):
    Canco = apps.get_model("music", "Canco")
    updated = Canco.objects.filter(
        spotify_id__isnull=False,
    ).exclude(
        spotify_id="",
    ).update(verificada=True)
    print(f"\n  Marked {updated} legacy cançons as verificada=True")


def reverse_verificada(apps, schema_editor):
    Canco = apps.get_model("music", "Canco")
    Canco.objects.all().update(verificada=False)


class Migration(migrations.Migration):

    dependencies = [
        ("music", "0006_add_canco_verificada"),
    ]

    operations = [
        migrations.RunPython(set_legacy_verificada, reverse_verificada),
    ]
