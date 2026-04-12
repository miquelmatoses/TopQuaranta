from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("music", "0016_rename_cancons_ingerades_album_cancons_obtingudes_and_more"),
        ("ranking", "0002_configuracioglobal_min_cancons_ranking_propi_and_more"),
    ]

    operations = [
        # Rename model (preserves data and table)
        migrations.RenameModel(
            old_name="IngestaDiari",
            new_name="SenyalDiari",
        ),
        # Update related_name on FK
        migrations.AlterField(
            model_name="senyaldiari",
            name="canco",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="senyals",
                to="music.canco",
            ),
        ),
    ]
