# web_cms/home/migrations/00XX_adopt_cms_artista.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0035_sitedesign_show_site_name_mainmenu_menuitem_and_more"),  # deixa-ho si l’auto-ompli deixa una alt\
ra dep
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # No fem res a la BD: la taula ja existeix
            ],
            state_operations=[
                migrations.CreateModel(
                    name="CmsArtista",
                    fields=[
                        ("id_spotify", models.CharField("ID Spotify", max_length=50, primary_key=True, serialize=False))\
,
                        ("nom", models.CharField("Nom", max_length=255)),
                        ("territori", models.CharField("Territori", max_length=50, blank=True)),
                        ("comarca", models.CharField("Comarca", max_length=255, blank=True)),
                        ("localitat", models.CharField("Localitat", max_length=255, blank=True)),

                        ("generes", models.TextField("Gèneres", blank=True, null=True)),
                        ("dones", models.CharField("Dones", max_length=4, blank=True, null=True)),

                        ("agencia", models.CharField("Agència", max_length=255, blank=True, null=True)),
                        ("email", models.TextField("Email", blank=True, null=True)),
                        ("telefon", models.TextField("Telèfon", blank=True, null=True)),

                        ("web", models.TextField("Web", blank=True, null=True)),
                        ("viquipedia", models.TextField("Viquipèdia", blank=True, null=True)),
                        ("id_viasona", models.TextField("ID Viasona", blank=True, null=True)),

                        ("instagram", models.CharField("Instagram", max_length=255, blank=True, null=True)),
                        ("youtube", models.TextField("YouTube", blank=True, null=True)),
                        ("tiktok", models.TextField("TikTok", blank=True, null=True)),
                        ("bluesky", models.TextField("Bluesky", blank=True, null=True)),

                        ("soundcloud", models.TextField("SoundCloud", blank=True, null=True)),
                        ("bandcamp", models.TextField("Bandcamp", blank=True, null=True)),
                        ("deezer", models.TextField("Deezer", blank=True, null=True)),
                        ("myspace", models.TextField("MySpace", blank=True, null=True)),

                        ("bio", models.TextField("Bio", blank=True, null=True)),

                        ("nom_spotify", models.TextField("Nom Spotify", blank=True, null=True)),
                        ("followers", models.IntegerField("Followers", blank=True, null=True)),
                        ("popularitat", models.IntegerField("Popularitat", blank=True, null=True)),
                        ("imatge_url", models.TextField("Imatge (URL)", blank=True, null=True)),

                        ("created_at", models.DateTimeField("Creat", auto_now_add=True)),
                        ("updated_at", models.DateTimeField("Actualitzat", auto_now=True)),
                    ],
                    options={
                        "db_table": "cms_artists",
                        "ordering": ("nom",),
                        "verbose_name": "Artista",
                        "verbose_name_plural": "Artistes",
                    },
                ),
            ],
        ),
    ]
