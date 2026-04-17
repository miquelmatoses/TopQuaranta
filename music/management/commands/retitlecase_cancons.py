"""Re-apply Catalan titlecase to all Canco names.

Use after the titlecase rules change (new particles, orphan-accent
normalization, single-letter fix, etc.). The command is idempotent:
running it twice in a row produces zero changes on the second run.

Options:
    --dry-run      show diffs without saving
    --limit N      process only the first N changed tracks (for spot-checks)
"""

import logging

from django.core.management.base import BaseCommand

from music.models import Canco
from music.titlecase_catala import titlecase_catala

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-apply Catalan titlecase to all Canco.nom values."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        limit = options["limit"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no writes.\n"))

        changed = 0
        unchanged = 0
        shown = 0
        batch: list[Canco] = []

        for canco in Canco.objects.all().only("id", "nom").iterator(chunk_size=1000):
            new_nom = titlecase_catala(canco.nom)
            if new_nom == canco.nom:
                unchanged += 1
                continue
            changed += 1
            if shown < 20 or dry_run:
                self.stdout.write(f"  [{canco.id}] {canco.nom!r} → {new_nom!r}")
                shown += 1
            if not dry_run:
                canco.nom = new_nom
                batch.append(canco)
            if len(batch) >= 500:
                Canco.objects.bulk_update(batch, ["nom"])
                batch = []
            if limit is not None and changed >= limit:
                break

        if batch:
            Canco.objects.bulk_update(batch, ["nom"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Changed: {changed}. Unchanged: {unchanged}. "
                f"Mode: {'DRY RUN' if dry_run else 'WRITE'}."
            )
        )
