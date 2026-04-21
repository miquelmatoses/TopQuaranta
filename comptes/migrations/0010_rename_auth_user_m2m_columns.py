"""Align auth_user_groups + auth_user_user_permissions columns with the
custom Usuari model name.

History: the project reuses Django's original auth_user table via
`db_table = "auth_user"` on Usuari. The legacy schema names the through-
table FK `user_id`, but Django's ORM — which derives the column from
the source model's name — expects `usuari_id`. This mismatch is silent
for reads but breaks `User.delete()` (the cascade collector emits
`DELETE FROM auth_user_groups WHERE usuari_id = %s`).

Idempotent: inspects the live schema and only renames columns still
carrying the legacy name. Fresh DBs (tests, new clones) create the
tables with `usuari_id` directly, so this is a no-op there.
"""

from django.db import migrations


def _tables():
    return ("auth_user_groups", "auth_user_user_permissions")


def rename_columns(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as c:
        for table in _tables():
            cols = [
                col.name for col in conn.introspection.get_table_description(c, table)
            ]
            if "user_id" in cols and "usuari_id" not in cols:
                c.execute(f"ALTER TABLE {table} RENAME COLUMN user_id TO usuari_id")


def rename_columns_back(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as c:
        for table in _tables():
            cols = [
                col.name for col in conn.introspection.get_table_description(c, table)
            ]
            if "usuari_id" in cols and "user_id" not in cols:
                c.execute(f"ALTER TABLE {table} RENAME COLUMN usuari_id TO user_id")


class Migration(migrations.Migration):

    dependencies = [
        ("comptes", "0009_perfilusuari_notificar_comentaris_email_and_more"),
    ]

    operations = [
        migrations.RunPython(rename_columns, rename_columns_back),
    ]
