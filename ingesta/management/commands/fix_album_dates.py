import logging

from django.core.management.base import BaseCommand

from ingesta.clients import deezer
from ingesta.clients.deezer import _parse_date
from music.models import Album

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fix album dates using track.album.release_date from Deezer (original date, not re-release)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limit = options["limit"]
        dry_run = options["dry_run"]

        qs = (
            Album.objects.filter(deezer_id__isnull=False)
            .exclude(cancons__deezer_id__isnull=True)
            .distinct()
        )
        total = qs.count()
        self.stdout.write(f"Albums to check: {total}")

        if limit:
            qs = qs[:limit]

        fixed = 0
        errors = 0
        checked = 0

        for album in qs if limit else qs.iterator():
            # Get first track with deezer_id from this album
            track = album.cancons.filter(deezer_id__isnull=False).first()
            if not track:
                continue

            data = deezer._get(f"{deezer.API_BASE}/track/{track.deezer_id}")

            if deezer.quota_exhausted():
                self.stderr.write(self.style.ERROR("Quota Deezer exhaurida."))
                break

            if not data:
                errors += 1
                continue

            album_date_str = data.get("album", {}).get("release_date", "")
            album_date = _parse_date(album_date_str)
            checked += 1

            if (
                album_date
                and album.data_llancament
                and album_date < album.data_llancament
            ):
                if dry_run:
                    self.stdout.write(
                        f"  FIX: {album.nom} — {album.data_llancament} → {album_date}"
                    )
                else:
                    album.data_llancament = album_date
                    album.save(update_fields=["data_llancament"])
                    # Also fix tracks in this album
                    album.cancons.update(data_llancament=album_date)
                fixed += 1

            if checked % 100 == 0:
                self.stdout.write(f"  Checked {checked}/{total}... (fixed={fixed})")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: checked={checked}, fixed={fixed}, errors={errors}"
            )
        )
