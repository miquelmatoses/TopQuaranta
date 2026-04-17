"""Re-apply Catalan titlecase to Canco and Album names.

Use after the titlecase rules change (new particles, orphan-accent
normalization, post-paren capitalization, etc.). Idempotent: running
twice in a row produces zero changes on the second run.

Options:
    --dry-run            show diffs without saving
    --limit N            stop after processing N changed rows (per target)
    --target cancons     only titlecase Canco.nom
    --target albums      only titlecase Album.nom
    --target all         both (default)
"""

import logging

from django.core.management.base import BaseCommand

from music.models import Album, Canco
from music.titlecase_catala import titlecase_catala

logger = logging.getLogger(__name__)

TARGETS = {
    "cancons": (Canco, "nom"),
    "albums": (Album, "nom"),
}


class Command(BaseCommand):
    help = "Re-apply Catalan titlecase to Canco.nom and Album.nom values."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument(
            "--target",
            choices=["cancons", "albums", "all"],
            default="all",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        limit = options["limit"]
        target = options["target"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no writes.\n"))

        targets = TARGETS if target == "all" else {target: TARGETS[target]}

        total_changed = 0
        for name, (Model, field) in targets.items():
            changed = self._process(Model, field, name, dry_run, limit)
            total_changed += changed

        self.stdout.write(
            self.style.SUCCESS(
                f"\nTotal changed across targets: {total_changed}. "
                f"Mode: {'DRY RUN' if dry_run else 'WRITE'}."
            )
        )

    def _process(
        self,
        Model,
        field: str,
        name: str,
        dry_run: bool,
        limit: int | None,
    ) -> int:
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {name} ==="))
        changed = 0
        unchanged = 0
        shown = 0
        batch = []

        qs = Model.objects.all().only("id", field).iterator(chunk_size=1000)
        for obj in qs:
            old = getattr(obj, field)
            new = titlecase_catala(old)
            if new == old:
                unchanged += 1
                continue
            changed += 1
            if shown < 20 or dry_run:
                self.stdout.write(f"  [{obj.id}] {old!r} → {new!r}")
                shown += 1
            if not dry_run:
                setattr(obj, field, new)
                batch.append(obj)
            if len(batch) >= 500:
                Model.objects.bulk_update(batch, [field])
                batch = []
            if limit is not None and changed >= limit:
                break

        if batch:
            Model.objects.bulk_update(batch, [field])

        self.stdout.write(f"{name}: changed={changed} unchanged={unchanged}")
        return changed
