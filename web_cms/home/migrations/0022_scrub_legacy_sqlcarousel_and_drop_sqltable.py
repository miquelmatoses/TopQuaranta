from django.contrib.contenttypes.models import ContentType
from django.db import connection, migrations


def scrub_sql_carousel(apps, schema_editor):
    HomePage = apps.get_model("home", "HomePage")
    updated = 0
    for page in HomePage.objects.all():
        body = page.body.stream_data or []
        new_body = [b for b in body if b.get("type") != "sql_carousel"]
        if new_body != body:
            page.body.stream_data = new_body
            page.save(update_fields=["body"])
            updated += 1
    if updated:
        print(f"Removed sql_carousel blocks from {updated} page(s).")


def drop_sqltable_and_contenttype(apps, schema_editor):
    # 2a) Eliminar la taula si existeix
    with connection.cursor() as cur:
        cur.execute("SELECT to_regclass('public.home_sqltable');")
        exists = cur.fetchone()[0]
        if exists:
            cur.execute("DROP TABLE IF EXISTS public.home_sqltable CASCADE;")
            print("Dropped table public.home_sqltable")

    # 2b) Eliminar ContentType orfe si hi és
    try:
        ct = ContentType.objects.get(app_label="home", model="sqltable")
        ct.delete()
        print("Deleted ContentType home.sqltable")
    except ContentType.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0021_sitebranding_on_brand"),
    ]
    operations = [
        migrations.RunPython(scrub_sql_carousel, migrations.RunPython.noop),
        migrations.RunPython(drop_sqltable_and_contenttype, migrations.RunPython.noop),
    ]
