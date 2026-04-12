import logging

from django.core.management.base import BaseCommand

from ingesta.clients import deezer
from music.models import Artista, Canco

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fix main artist on tracks where Deezer's first contributor differs from stored artista."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        limit = options["limit"]

        qs = Canco.objects.filter(
            deezer_id__isnull=False,
            verificada=False,
        ).select_related("artista")
        total = qs.count()
        self.stdout.write(f"Tracks to check: {total}")

        if limit:
            qs = qs[:limit]

        fixed = 0
        errors = 0
        checked = 0

        for canco in (qs if limit else qs.iterator()):
            data = deezer._get(f"{deezer.API_BASE}/track/{canco.deezer_id}")

            if deezer.quota_exhausted():
                self.stderr.write(self.style.ERROR("Quota Deezer exhaurida."))
                break

            if not data:
                errors += 1
                continue

            checked += 1
            contributors = data.get("contributors", [])
            if not contributors:
                continue

            main = contributors[0]
            main_id = main.get("id")
            main_name = main.get("name", "")

            if not main_id or main_id == canco.artista.deezer_id:
                continue

            # Main artist is different — fix it
            try:
                real_artista = Artista.objects.get(deezer_id=main_id)
            except Artista.DoesNotExist:
                real_artista = Artista.objects.create(
                    nom=main_name,
                    lastfm_nom=main_name,
                    deezer_id=main_id,
                    aprovat=False,
                    auto_descobert=True,
                    font_descoberta="deezer_contributor",
                )
                logger.info("Created artist '%s' (deezer_id=%d)", main_name, main_id)

            # Add old artista as collaborator if not already
            canco.artistes_col.add(canco.artista)
            canco.artista = real_artista
            canco.save(update_fields=["artista_id"])
            fixed += 1

            if checked % 100 == 0:
                self.stdout.write(f"  Checked {checked}... (fixed={fixed})")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: checked={checked}, fixed={fixed}, errors={errors}"
            )
        )
