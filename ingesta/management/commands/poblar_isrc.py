import logging

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from music.models import Canco

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Populate ISRC on Canco from legacy spotify_tracks table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without writing to DB.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of tracks to process.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN — no DB writes.\n")
            )

        # Find all cancons with spotify_id but no ISRC, that have a match
        # in the legacy spotify_tracks table.
        query = """
            SELECT c.id, c.spotify_id, st.external_ids->>'isrc' AS isrc
            FROM music_canco c
            JOIN spotify_tracks st ON st.id = c.spotify_id
            WHERE (c.isrc IS NULL OR c.isrc = '')
              AND st.external_ids->>'isrc' IS NOT NULL
        """
        if limit:
            query += f" LIMIT {int(limit)}"

        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        total = len(rows)
        self.stdout.write(f"Cancons with ISRC match found: {total}")

        if dry_run:
            for canco_id, spotify_id, isrc in rows[:20]:
                self.stdout.write(f"  Would set: canco_id={canco_id} spotify_id={spotify_id} → isrc={isrc}")
            if total > 20:
                self.stdout.write(f"  ... and {total - 20} more")
            return

        updated = 0
        with transaction.atomic():
            for i, (canco_id, spotify_id, isrc) in enumerate(rows, 1):
                Canco.objects.filter(pk=canco_id).update(isrc=isrc)
                updated += 1

                if i % 200 == 0:
                    self.stdout.write(f"  Updated {i}/{total}...")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nISRC population complete:\n"
                f"  Updated: {updated}\n"
                f"  Total eligible: {total}"
            )
        )
