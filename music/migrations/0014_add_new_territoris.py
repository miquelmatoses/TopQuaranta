from django.db import migrations

NEW_TERRITORIS = [
    ("CNO", "Catalunya del Nord"),
    ("AND", "Andorra"),
    ("FRA", "Franja de Ponent"),
    ("ALG", "L'Alguer"),
    ("CAR", "El Carxe"),
    ("ALT", "Altres territoris"),
    ("PPCC", "Països Catalans"),
]


def create_territoris(apps, schema_editor):
    Territori = apps.get_model("music", "Territori")
    for codi, nom in NEW_TERRITORIS:
        Territori.objects.get_or_create(codi=codi, defaults={"nom": nom})


def remove_territoris(apps, schema_editor):
    Territori = apps.get_model("music", "Territori")
    Territori.objects.filter(codi__in=[c for c, _ in NEW_TERRITORIS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("music", "0013_alter_territori_codi"),
    ]

    operations = [
        migrations.RunPython(create_territoris, remove_territoris),
    ]
