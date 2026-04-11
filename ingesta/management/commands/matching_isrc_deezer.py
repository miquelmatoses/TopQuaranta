import logging
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from ingesta.clients.deezer import _get, _normalize, API_BASE
from music.models import Artista

logger = logging.getLogger(__name__)

RATE_LIMIT_SLEEP = 0.2


class Command(BaseCommand):
    help = (
        "Match artists without deezer_id via ISRC lookup: "
        "find an ISRC from legacy spotify_tracks, query Deezer by ISRC, "
        "and save the deezer_id on the artist."
    )

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
            help="Max number of artists to process.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        # Find artists without deezer_id, not marked as not found
        artists = Artista.objects.filter(
            deezer_id__isnull=True,
            deezer_no_trobat=False,
            spotify_id__isnull=False,
        ).order_by("nom")

        if limit:
            artists = artists[:limit]

        artists = list(artists)
        self.stdout.write(f"Artists to process: {len(artists)}")

        matched = 0
        not_found = 0
        no_isrc = 0
        errors = 0

        for i, artista in enumerate(artists, 1):
            if i % 50 == 0:
                self.stdout.write(f"  Progress: {i}/{len(artists)} ...")

            # Step 1: find an ISRC from legacy spotify_tracks
            isrc = self._find_isrc(artista.spotify_id)
            if not isrc:
                no_isrc += 1
                continue

            # Step 2: query Deezer by ISRC
            time.sleep(RATE_LIMIT_SLEEP)
            data = _get(f"{API_BASE}/track/isrc:{isrc}")
            if not data or "error" in (data if isinstance(data, dict) else {}):
                logger.info(
                    "Deezer ISRC lookup failed for %s (ISRC=%s)", artista.nom, isrc
                )
                if not dry_run:
                    artista.deezer_no_trobat = True
                    artista.save(update_fields=["deezer_no_trobat"])
                not_found += 1
                continue

            # Step 3: extract artist id from Deezer response
            # The main artist on the track may not be our artist (e.g. feat.),
            # so check all contributors too.
            deezer_artist_id = None
            deezer_artist_name = None
            nom_norm = _normalize(artista.nom)

            # Check main artist
            main_artist = data.get("artist", {})
            if main_artist and _normalize(main_artist.get("name", "")) == nom_norm:
                deezer_artist_id = main_artist["id"]
                deezer_artist_name = main_artist["name"]

            # Check contributors if main didn't match
            if not deezer_artist_id:
                for contrib in data.get("contributors", []):
                    if _normalize(contrib.get("name", "")) == nom_norm:
                        deezer_artist_id = contrib["id"]
                        deezer_artist_name = contrib["name"]
                        break

            if not deezer_artist_id:
                logger.info(
                    "Deezer ISRC match but artist name mismatch for %s: "
                    "main=%s, contributors=%s (ISRC=%s)",
                    artista.nom,
                    main_artist.get("name", "?"),
                    [c.get("name") for c in data.get("contributors", [])],
                    isrc,
                )
                if not dry_run:
                    artista.deezer_no_trobat = True
                    artista.save(update_fields=["deezer_no_trobat"])
                not_found += 1
                continue

            deezer_artist = {"id": deezer_artist_id, "name": deezer_artist_name}

            # Check for deezer_id collision
            existing = Artista.objects.filter(deezer_id=deezer_artist_id).first()
            if existing and existing.pk != artista.pk:
                logger.warning(
                    "Deezer ID %d already assigned to %s — skipping %s",
                    deezer_artist_id, existing.nom, artista.nom,
                )
                if not dry_run:
                    artista.deezer_no_trobat = True
                    artista.save(update_fields=["deezer_no_trobat"])
                not_found += 1
                continue

            prefix = "[DRY-RUN] " if dry_run else ""
            self.stdout.write(
                f"  {prefix}MATCH: {artista.nom} → Deezer artist "
                f"{deezer_artist_name} (id={deezer_artist_id}, ISRC={isrc})"
            )

            if not dry_run:
                with transaction.atomic():
                    artista.deezer_id = deezer_artist_id
                    artista.save(update_fields=["deezer_id"])

            matched += 1

        self.stdout.write(
            f"\nDone. Processed: {len(artists)} | "
            f"Matched: {matched} | Not found: {not_found} | "
            f"No ISRC in legacy: {no_isrc} | Errors: {errors}"
        )

    def _find_isrc(self, spotify_id: str) -> str | None:
        """Find an ISRC for an artist via legacy spotify_tracks table."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT st.external_ids->>'isrc'
                FROM spotify_tracks st, jsonb_array_elements(st.artists) AS artist
                WHERE artist->>'id' = %s
                  AND st.external_ids->>'isrc' IS NOT NULL
                LIMIT 1
                """,
                [spotify_id],
            )
            row = cursor.fetchone()
            return row[0] if row else None
