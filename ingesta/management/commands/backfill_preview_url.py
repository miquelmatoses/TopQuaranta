import logging

from django.core.management.base import BaseCommand

from ingesta.clients import deezer
from music.models import Canco

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill preview_url for Canco records with deezer_id."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        limit = options["limit"]

        qs = Canco.objects.filter(
            deezer_id__isnull=False,
            preview_url="",
        )
        total = qs.count()
        self.stdout.write(f"Tracks to backfill: {total}")

        if limit:
            qs = qs[:limit]
            self.stdout.write(f"  Limited to: {limit}")

        ok = 0
        errors = 0
        iterable = qs if limit else qs.iterator()

        for i, canco in enumerate(iterable, 1):
            data = deezer._get(f"{deezer.API_BASE}/track/{canco.deezer_id}")

            if deezer.quota_exhausted():
                self.stderr.write(
                    self.style.ERROR("Quota Deezer exhaurida — reintenta demà.")
                )
                break

            if not data or not data.get("preview"):
                errors += 1
            else:
                canco.preview_url = data["preview"]
                canco.save(update_fields=["preview_url"])
                ok += 1

            if i % 100 == 0:
                self.stdout.write(f"  Processed {i}/{total}... (ok={ok}, errors={errors})")

        self.stdout.write(
            self.style.SUCCESS(f"Backfill complete: {ok} updated, {errors} errors.")
        )
