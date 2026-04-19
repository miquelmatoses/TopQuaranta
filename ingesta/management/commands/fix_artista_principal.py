import logging

from django.core.management.base import BaseCommand
from django.db import IntegrityError

from ingesta.clients import deezer
from music.models import Artista, Canco

logger = logging.getLogger(__name__)


def _get_or_create_artista(deezer_id: int, name: str) -> Artista | None:
    """Get or create an Artista by Deezer ID (via ArtistaDeezer M2M).

    R10: Artista.deezer_id was dropped — ArtistaDeezer is the single source.
    """
    from music.models import ArtistaDeezer

    ad = (
        ArtistaDeezer.objects.filter(deezer_id=deezer_id)
        .select_related("artista")
        .first()
    )
    if ad:
        return ad.artista
    try:
        artista = Artista.objects.create(
            nom=name,
            lastfm_nom=name,
            aprovat=False,
            auto_descobert=True,
            pendent_review=True,
            font_descoberta="deezer_contributor",
        )
        ArtistaDeezer.objects.get_or_create(
            deezer_id=deezer_id,
            defaults={"artista": artista, "principal": True},
        )
        return artista
    except IntegrityError:
        # Race condition or duplicate — refetch via the M2M
        ad = (
            ArtistaDeezer.objects.filter(deezer_id=deezer_id)
            .select_related("artista")
            .first()
        )
        return ad.artista if ad else None


class Command(BaseCommand):
    help = "Fix main artist and collaborators on all tracks with deezer_id using Deezer contributors."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limit = options["limit"]
        dry_run = options["dry_run"]

        qs = Canco.objects.filter(
            deezer_id__isnull=False,
        ).select_related("artista")
        total = qs.count()
        self.stdout.write(f"Tracks to check: {total}")

        if limit:
            qs = qs[:limit]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no DB writes."))

        main_fixed = 0
        collabs_added = 0
        errors = 0
        checked = 0

        for canco in qs if limit else qs.iterator():
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

            # Determine main contributor
            main = contributors[0]
            main_id = main.get("id")
            main_name = main.get("name", "")

            # Fix main artist if different
            if main_id and main_id != canco.artista.deezer_id_principal:
                if dry_run:
                    self.stdout.write(
                        f"  FIX MAIN: {canco.nom} — {canco.artista.nom} → {main_name} (dz={main_id})"
                    )
                else:
                    real_artista = _get_or_create_artista(main_id, main_name)
                    if real_artista:
                        canco.artista = real_artista
                        canco.save(update_fields=["artista_id"])
                main_fixed += 1

            # Process secondary contributors. Read existing collaborator
            # Deezer IDs via the ArtistaDeezer M2M (R10: legacy direct
            # column on Artista is gone).
            from music.models import ArtistaDeezer

            current_col_ids = set(
                ArtistaDeezer.objects.filter(
                    artista__in=canco.artistes_col.all()
                ).values_list("deezer_id", flat=True)
            )
            main_artista_dz = main_id or canco.artista.deezer_id_principal

            for contributor in contributors[1:]:
                c_id = contributor.get("id")
                c_name = contributor.get("name", "")
                if not c_id or c_id == main_artista_dz:
                    continue
                if c_id in current_col_ids:
                    continue

                if dry_run:
                    self.stdout.write(
                        f"  ADD COLLAB: {canco.nom} += {c_name} (dz={c_id})"
                    )
                else:
                    collab = _get_or_create_artista(c_id, c_name)
                    if collab:
                        canco.artistes_col.add(collab)
                collabs_added += 1

            if checked % 100 == 0:
                self.stdout.write(
                    f"  Processed {checked}/{total}... "
                    f"(main_fixed={main_fixed}, collabs_added={collabs_added}, errors={errors})"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone:\n"
                f"  Checked: {checked}\n"
                f"  Main artist fixed: {main_fixed}\n"
                f"  Collaborators added: {collabs_added}\n"
                f"  Errors: {errors}"
            )
        )
