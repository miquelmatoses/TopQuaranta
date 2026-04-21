import difflib
import logging

from django.core.management.base import BaseCommand

from ingesta.clients import deezer
from music.models import Artista

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill deezer_nb_fan, deezer_nb_album, deezer_nom, deezer_nom_similitud for artists with a linked Deezer ID."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        # R10: Artista.deezer_id legacy field is gone; filter via the
        # ArtistaDeezer reverse manager instead.
        qs = Artista.objects.filter(
            deezer_ids__isnull=False,
            deezer_nb_fan__isnull=True,
        ).distinct()
        total = qs.count()
        self.stdout.write(f"Artists to backfill: {total}")

        if limit:
            qs = qs[:limit]
            self.stdout.write(f"  Limited to: {limit}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no DB writes."))
            for a in qs[:10]:
                self.stdout.write(
                    f"  Would fetch: {a.nom} (deezer_id={a.deezer_id_principal})"
                )
            if total > 10:
                self.stdout.write(f"  ... and {total - 10} more")
            return

        ok = 0
        errors = 0
        iterable = qs if limit else qs.iterator()

        for i, artista in enumerate(iterable, 1):
            dz_id = artista.deezer_id_principal
            info = deezer.get_artist_info(dz_id)
            if deezer.quota_exhausted():
                self.stderr.write(
                    self.style.ERROR("Quota Deezer exhaurida — reintenta demà.")
                )
                break
            if not info:
                logger.warning("No Deezer info for %s (id=%s)", artista.nom, dz_id)
                errors += 1
            else:
                deezer_name = info["name"]
                artista.deezer_nb_fan = info["nb_fan"]
                artista.deezer_nb_album = info["nb_album"]
                artista.deezer_nom = deezer_name
                artista.deezer_nom_similitud = difflib.SequenceMatcher(
                    None, artista.nom.lower(), deezer_name.lower()
                ).ratio()
                artista.save(
                    update_fields=[
                        "deezer_nb_fan",
                        "deezer_nb_album",
                        "deezer_nom",
                        "deezer_nom_similitud",
                    ]
                )
                ok += 1

            if i % 100 == 0:
                self.stdout.write(
                    f"  Processed {i}/{total}... (ok={ok}, errors={errors})"
                )

        self.stdout.write(
            self.style.SUCCESS(f"Backfill complete: {ok} updated, {errors} errors.")
        )
