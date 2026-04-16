import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from ranking.models import SenyalDiari
from ranking.senyal import normalize_score_entrada

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
            self.stdout.write(
                f"Processing {len(dates)} dates: {dates[0]} → {dates[-1]}"
            )
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
            updated = normalize_score_entrada(d)
            total_updated += updated
            self.stdout.write(f"  {d}: {updated} rows updated")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nTotal: {total_updated} rows updated across {len(dates)} dates"
            )
        )
