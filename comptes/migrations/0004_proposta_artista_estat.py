"""Add PropostaArtista model, estat field on UserArtista, make artista non-nullable."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("comptes", "0003_useartista_multi_nullable"),
        ("music", "0025_populate_municipis_and_localitats"),
    ]

    operations = [
        # Add estat field to UserArtista
        migrations.AddField(
            model_name="userartista",
            name="estat",
            field=models.CharField(
                choices=[("pendent", "Pendent"), ("aprovat", "Aprovat"), ("rebutjat", "Rebutjat")],
                default="pendent",
                max_length=10,
            ),
        ),
        # Make artista non-nullable (0 rows, safe)
        migrations.AlterField(
            model_name="userartista",
            name="artista",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="music.artista",
            ),
        ),
        # Create PropostaArtista
        migrations.CreateModel(
            name="PropostaArtista",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=255)),
                ("justificacio", models.TextField()),
                ("spotify_url", models.URLField(blank=True)),
                ("viasona_url", models.URLField(blank=True)),
                ("web_url", models.URLField(blank=True)),
                ("bandcamp_url", models.URLField(blank=True)),
                ("youtube_url", models.URLField(blank=True)),
                ("viquipedia_url", models.URLField(blank=True)),
                ("soundcloud_url", models.URLField(blank=True)),
                ("tiktok_url", models.URLField(blank=True)),
                ("facebook_url", models.URLField(blank=True)),
                ("deezer_ids", models.CharField(blank=True, max_length=255)),
                ("localitzacions_json", models.TextField(blank=True)),
                ("estat", models.CharField(
                    choices=[("pendent", "Pendent"), ("aprovat", "Aprovat"), ("rebutjat", "Rebutjat")],
                    default="pendent",
                    max_length=10,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("usuari", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="propostes_artista",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("artista_creat", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="propostes_origen",
                    to="music.artista",
                )),
            ],
            options={
                "verbose_name": "Proposta d'artista",
                "verbose_name_plural": "Propostes d'artista",
                "ordering": ["-created_at"],
            },
        ),
    ]
