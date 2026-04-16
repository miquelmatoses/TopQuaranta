import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from music.models import Canco
from ranking.models import SenyalDiari

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Deduplicate Canco records sharing the same ISRC. Keeps the best one, merges data, deletes the rest."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--limit", type=int, default=None, help="Max groups to process."
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no DB writes."))

        # Find ISRCs with duplicates
        dupes = (
            Canco.objects.exclude(isrc="")
            .values("isrc")
            .annotate(cnt=Count("id"))
            .filter(cnt__gt=1)
            .order_by("-cnt")
        )

        total_groups = dupes.count()
        self.stdout.write(f"ISRC groups with duplicates: {total_groups}")

        if limit:
            dupes = dupes[:limit]

        groups_processed = 0
        cancons_removed = 0
        senyals_moved = 0

        for entry in dupes:
            isrc = entry["isrc"]
            cnt = entry["cnt"]

            # Order: verificada=True first, then highest deezer_id (most recent)
            cancons = list(
                Canco.objects.filter(isrc=isrc).order_by("-verificada", "-deezer_id")
            )

            principal = cancons[0]
            duplicades = cancons[1:]

            if dry_run:
                self.stdout.write(
                    f"  ISRC {isrc}: {cnt} → 1 (keep id={principal.pk} "
                    f"'{principal.nom}' dz={principal.deezer_id} "
                    f"verificada={principal.verificada})"
                )
                for dup in duplicades:
                    self.stdout.write(
                        f"    DELETE id={dup.pk} '{dup.nom}' dz={dup.deezer_id} "
                        f"verificada={dup.verificada}"
                    )
                groups_processed += 1
                cancons_removed += len(duplicades)
                continue

            with transaction.atomic():
                # Collect best deezer_id from duplicates before deleting
                best_deezer_id = None
                if not principal.deezer_id:
                    for dup in duplicades:
                        if dup.deezer_id:
                            best_deezer_id = dup.deezer_id
                            break

                for dup in duplicades:
                    # Move SenyalDiari records that don't conflict
                    existing_dates = set(
                        SenyalDiari.objects.filter(canco=principal).values_list(
                            "data", flat=True
                        )
                    )
                    moved = 0
                    for senyal in SenyalDiari.objects.filter(canco=dup):
                        if senyal.data not in existing_dates:
                            senyal.canco = principal
                            senyal.save(update_fields=["canco_id"])
                            existing_dates.add(senyal.data)
                            moved += 1
                        else:
                            senyal.delete()
                    senyals_moved += moved

                    # Merge collaborators
                    for col in dup.artistes_col.all():
                        if col.pk != principal.artista_id:
                            principal.artistes_col.add(col)

                    # If dup's main artist is different, add as collaborator
                    if dup.artista_id != principal.artista_id:
                        principal.artistes_col.add(dup.artista)

                    dup.delete()

                # Update deezer_id after all duplicates are deleted
                if best_deezer_id:
                    principal.deezer_id = best_deezer_id
                    principal.save(update_fields=["deezer_id"])

                logger.info("ISRC %s: %d → 1 (kept id=%d)", isrc, cnt, principal.pk)

            groups_processed += 1
            cancons_removed += len(duplicades)

            if groups_processed % 50 == 0:
                self.stdout.write(f"  ... {groups_processed} grups processats")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nGrups: {groups_processed} | Cançons eliminades: {cancons_removed} | "
                f"Senyals moguts: {senyals_moved}"
            )
        )
