import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from scipy.stats import percentileofscore

from ranking.models import SenyalDiari

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Compute score_entrada (percent_rank of playcount) for SenyalDiari rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data",
            type=str,
            default=None,
            help="Process a specific date (YYYY-MM-DD). Default: yesterday.",
        )
        parser.add_argument(
            "--tots",
            action="store_true",
            help="Process all dates that have rows with score_entrada IS NULL.",
        )

    def handle(self, *args, **options):
        if options["tots"]:
            dates = list(
                SenyalDiari.objects.filter(
                    score_entrada__isnull=True,
                    error=False,
                    lastfm_playcount__isnull=False,
                )
                .values_list("data", flat=True)
                .distinct()
                .order_by("data")
            )
            if not dates:
                self.stdout.write("No dates with NULL score_entrada found.")
                return
            self.stdout.write(f"Processing {len(dates)} dates: {dates[0]} → {dates[-1]}")
        elif options["data"]:
            try:
                target = date.fromisoformat(options["data"])
            except ValueError:
                raise CommandError(f"Invalid date: {options['data']}. Use YYYY-MM-DD.")
            dates = [target]
        else:
            dates = [date.today() - timedelta(days=1)]

        total_updated = 0
        for d in dates:
            updated = self._normalize_day(d)
            total_updated += updated
            self.stdout.write(f"  {d}: {updated} rows updated")

        self.stdout.write(
            self.style.SUCCESS(f"\nTotal: {total_updated} rows updated across {len(dates)} dates")
        )

    def _normalize_day(self, target_date: date) -> int:
        """Compute percent_rank(playcount) for all SenyalDiari of a given day."""
        rows = list(
            SenyalDiari.objects.filter(
                data=target_date,
                error=False,
                lastfm_playcount__isnull=False,
            ).values_list("pk", "lastfm_playcount")
        )
        if not rows:
            return 0

        sorted_plays = sorted(pc for _, pc in rows if pc > 0)

        updates = []
        for pk, playcount in rows:
            if playcount > 0 and sorted_plays:
                score = percentileofscore(sorted_plays, playcount, kind="rank")
            else:
                score = 0.0
            updates.append((pk, score))

        updated = 0
        for i in range(0, len(updates), 500):
            batch = updates[i : i + 500]
            with transaction.atomic():
                for pk, score in batch:
                    SenyalDiari.objects.filter(pk=pk).update(score_entrada=score)
                    updated += 1

        return updated
