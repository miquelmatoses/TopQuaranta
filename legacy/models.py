from django.db import models


class LegacyArtista(models.Model):
    """Read-only access to legacy `artistes` table for data migration."""

    id_spotify = models.CharField(max_length=50, primary_key=True)
    nom = models.CharField(max_length=255, null=True)
    nom_spotify = models.TextField(null=True)
    territori = models.CharField(max_length=50, null=True)
    status = models.CharField(max_length=20, null=True)
    catala = models.BooleanField(db_column="català", null=True)
    localitat = models.CharField(max_length=255, null=True)
    comarca = models.CharField(max_length=255, null=True)
    id_viasona = models.TextField(null=True)
    font_dades = models.CharField(max_length=255, null=True)

    class Meta:
        managed = False
        db_table = "artistes"


class LegacyCanco(models.Model):
    """Read-only access to legacy `cançons` table for data migration."""

    id_canco = models.CharField(max_length=50, primary_key=True)
    territori = models.CharField(max_length=50)
    titol = models.TextField(null=True)
    artista_basat = models.TextField(null=True)
    album_id = models.CharField(max_length=50, null=True)
    album_titol = models.TextField(null=True)
    album_data = models.DateField(null=True)
    album_caratula_url = models.TextField(null=True)
    artistes_ids = models.TextField(null=True)
    exclosa = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "cançons"
        unique_together = [("id_canco", "territori")]
