from django.db import migrations


TERRITORIS = [
    ("CAT", "Catalunya"),
    ("VAL", "País Valencià"),
    ("BAL", "Illes Balears"),
]


def create_territoris(apps, schema_editor):
    Territori = apps.get_model("music", "Territori")
    for codi, nom in TERRITORIS:
        Territori.objects.get_or_create(codi=codi, defaults={"nom": nom})


def remove_territoris(apps, schema_editor):
    Territori = apps.get_model("music", "Territori")
    Territori.objects.filter(codi__in=["CAT", "VAL", "BAL"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("music", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_territoris, remove_territoris),
    ]
