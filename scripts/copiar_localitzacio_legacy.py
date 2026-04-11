"""
One-off script: copy localitat, comarca, provincia from legacy artistes
table to music_artista via spotify_id matching.

Usage:
    DJANGO_SETTINGS_MODULE=topquaranta.settings.production \
        .venv/bin/python scripts/copiar_localitzacio_legacy.py
"""

import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "topquaranta.settings.production")
django.setup()

from django.db import connection, transaction


def main():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*)
            FROM music_artista ma
            JOIN artistes a ON a.id_spotify = ma.spotify_id
            WHERE ma.spotify_id IS NOT NULL
              AND (COALESCE(a.localitat, '') != '' OR COALESCE(a.comarca, '') != '' OR COALESCE(a.provincia, '') != '')
        """)
        count = cursor.fetchone()[0]

    print(f"Artistes amb dades de localització a legacy: {count}")

    if count == 0:
        print("Cap artista per actualitzar. Sortint.")
        return

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE music_artista ma
                SET localitat = COALESCE(a.localitat, ''),
                    comarca = COALESCE(a.comarca, ''),
                    provincia = COALESCE(a.provincia, '')
                FROM artistes a
                WHERE a.id_spotify = ma.spotify_id
                  AND ma.spotify_id IS NOT NULL
                  AND (COALESCE(a.localitat, '') != '' OR COALESCE(a.comarca, '') != '' OR COALESCE(a.provincia, '') != '')
            """)
            updated = cursor.rowcount

    print(f"Fet! {updated} artistes actualitzats amb localitat/comarca/provincia.")

    # Summary stats
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM music_artista WHERE localitat != ''")
        print(f"  - Amb localitat: {cursor.fetchone()[0]}")
        cursor.execute("SELECT COUNT(*) FROM music_artista WHERE comarca != ''")
        print(f"  - Amb comarca: {cursor.fetchone()[0]}")
        cursor.execute("SELECT COUNT(*) FROM music_artista WHERE provincia != ''")
        print(f"  - Amb provincia: {cursor.fetchone()[0]}")


if __name__ == "__main__":
    main()
