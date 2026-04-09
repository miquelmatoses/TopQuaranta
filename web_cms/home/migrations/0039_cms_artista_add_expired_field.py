from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("home", "0038_cms_artista_add_scheduling_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="cmsartista",
            name="expired",
            field=models.BooleanField(default=False),
        ),
    ]
