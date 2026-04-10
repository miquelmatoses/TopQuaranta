from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("legacy", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="legacycanco",
            name="id",
        ),
        migrations.AlterField(
            model_name="legacycanco",
            name="id_canco",
            field=models.CharField(max_length=50, primary_key=True, serialize=False),
        ),
    ]
