# web_cms/home/migrations/00XY_cms_artista_add_draft_revision_fields.py

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0036_adopt_cms_artista"),
    ]

    operations = [
        # Afegim els camps requerits per DraftStateMixin i RevisionMixin
        migrations.AddField(
            model_name="cmsartista",
            name="live",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="cmsartista",
            name="has_unpublished_changes",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="cmsartista",
            name="first_published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cmsartista",
            name="last_published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cmsartista",
            name="latest_revision",
            field=models.ForeignKey(
                to="wagtailcore.revision",
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
            ),
        ),
        migrations.AddField(
            model_name="cmsartista",
            name="live_revision",
            field=models.ForeignKey(
                to="wagtailcore.revision",
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
            ),
        ),
    ]

