from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("home", "0037_cms_artista_add_draft_revision_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="cmsartista",
            name="go_live_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="cmsartista",
            name="expire_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
