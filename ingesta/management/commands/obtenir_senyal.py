import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ingesta.clients.lastfm import get_track_info
from music.constants import DIES_CADUCITAT
from music.models import Canco
from ranking.models import SenyalDiari
from ranking.senyal import normalize_score_entrada

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ingest daily Last.fm signal (playcount + listeners) for active tracks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data",
            type=str,
            default=None,
            help="Date to ingest for (YYYY-MM-DD). Defaults to today.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit number of tracks to process (for testing).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be ingested without calling Last.fm or writing to DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Parse target date
        if options["data"]:
            try:
                target_date = date.fromisoformat(options["data"])
            except ValueError:
                raise CommandError(
                    f"Invalid date format: {options['data']}. Use YYYY-MM-DD."
                )
        else:
            target_date = date.today()

        cutoff = target_date - timedelta(days=DIES_CADUCITAT)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN — no API calls, no DB writes.\n")
            )

        self.stdout.write(f"Ingesting Last.fm signal for {target_date}...")
        self.stdout.write(f"  Release cutoff: {cutoff} (tracks older are excluded)")

        # Fetch eligible tracks
        cancons = (
            Canco.objects.filter(
                activa=True,
                verificada=True,
                artista__aprovat=True,
                data_llancament__gte=cutoff,
            )
            .select_related("artista")
            .order_by("pk")
        )

        total = cancons.count()
        self.stdout.write(f"  Eligible tracks: {total}")

        if options["limit"]:
            cancons = cancons[: options["limit"]]
            self.stdout.write(f"  Limited to: {options['limit']}")

        if dry_run:
            for c in cancons[:10]:
                self.stdout.write(
                    f"    Would ingest: '{c.artista.lastfm_nom}' / "
                    f"'{c.lastfm_lookup_nom}'"
                )
            if total > 10:
                self.stdout.write(f"    ... and {total - 10} more")
            return

        # Skip tracks already ingested for this date
        already_ingested = set(
            SenyalDiari.objects.filter(data=target_date).values_list(
                "canco_id", flat=True
            )
        )

        success = 0
        errors = 0
        skipped = 0

        for i, canco in enumerate(cancons.iterator(), 1):
            if canco.pk in already_ingested:
                skipped += 1
                continue

            artist_name = canco.artista.lastfm_nom
            track_name = canco.lastfm_lookup_nom

            result = get_track_info(artist_name, track_name)

            if result is not None:
                with transaction.atomic():
                    SenyalDiari.objects.update_or_create(
                        canco=canco,
                        data=target_date,
                        defaults={
                            "lastfm_playcount": result["playcount"],
                            "lastfm_listeners": result["listeners"],
                            "error": False,
                            "error_msg": "",
                        },
                    )
                success += 1
            else:
                with transaction.atomic():
                    SenyalDiari.objects.update_or_create(
                        canco=canco,
                        data=target_date,
                        defaults={
                            "lastfm_playcount": None,
                            "lastfm_listeners": None,
                            "error": True,
                            "error_msg": f"Last.fm lookup failed for '{artist_name}' / '{track_name}'",
                        },
                    )
                errors += 1

            if i % 100 == 0:
                self.stdout.write(f"  Processed {i}... (ok={success}, err={errors}, skip={skipped})")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n  Ingestion complete for {target_date}:\n"
                f"    Success: {success}\n"
                f"    Errors:  {errors}\n"
                f"    Skipped (already ingested): {skipped}\n"
                f"    Total processed: {success + errors + skipped}"
            )
        )

        # Normalization: compute score_entrada via percent_rank over the day's playcounts
        updated = normalize_score_entrada(target_date)
        self.stdout.write(f"  score_entrada normalized: {updated} rows updated")
