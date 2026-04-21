"""Align auth_user_groups + auth_user_user_permissions columns with the
custom Usuari model name.

History: the project reuses Django's original auth_user table via
`db_table = "auth_user"` on Usuari. The original schema names the
through-table FK `user_id`, but Django's ORM — which derives the
column from the source model's name — expects `usuari_id`. This
mismatch is silent for reads (Django rarely hits those tables) but
breaks `User.delete()` because the cascade collector emits
`DELETE FROM auth_user_groups WHERE usuari_id = %s`.

This migration renames the columns (and their unique constraints) to
match Django's expectations. No data is touched.
"""

from django.db import migrations

SQL_UP = r"""
ALTER TABLE auth_user_groups RENAME COLUMN user_id TO usuari_id;
ALTER TABLE auth_user_user_permissions RENAME COLUMN user_id TO usuari_id;

-- The unique constraints were created with names derived from the old
-- column; try to rename them if they exist under the Django-expected
-- names; ignore if they already have a different name.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'auth_user_groups_user_id_group_id_94350c0c_uniq'
    ) THEN
        ALTER TABLE auth_user_groups
        RENAME CONSTRAINT auth_user_groups_user_id_group_id_94350c0c_uniq
        TO auth_user_groups_usuari_id_group_id_uniq;
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'auth_user_user_permissions_user_id_permission_id_14a6b632_uniq'
    ) THEN
        ALTER TABLE auth_user_user_permissions
        RENAME CONSTRAINT auth_user_user_permissions_user_id_permission_id_14a6b632_uniq
        TO auth_user_user_permissions_usuari_id_permission_id_uniq;
    END IF;
END $$;
"""

SQL_DOWN = r"""
ALTER TABLE auth_user_groups RENAME COLUMN usuari_id TO user_id;
ALTER TABLE auth_user_user_permissions RENAME COLUMN usuari_id TO user_id;
"""


class Migration(migrations.Migration):

    dependencies = [
        (
            "comptes",
            "0009_perfilusuari_notificar_comentaris_email_and_more",
        ),
    ]

    operations = [
        migrations.RunSQL(SQL_UP, SQL_DOWN),
    ]
