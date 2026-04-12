import logging
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from legacy.models import LegacyArtista, LegacyCanco
from music.models import Album, Artista, Canco, Territori
from ranking.models import ConfiguracioGlobal

logger = logging.getLogger(__name__)

# municipis.Territori → new territory code
MUNICIPIS_TERRITORI_MAP = {
    "Catalunya": "CAT",
    "País Valencià": "VAL",
    "Illes": "BAL",
    "Catalunya del Nord": "CNO",
    "Andorra": "AND",
    "Franja de Ponent": "FRA",
    "L'Alguer": "ALG",
    "El Carxe": "CAR",
}

# Fallback: legacy artistes.territori → new territory code
LEGACY_TERRITORI_FALLBACK = {
    "Catalunya": "CAT",
    "País Valencià": "VAL",
    "Balears": "BAL",
    "Illes": "BAL",
    "Altres": "ALT",
}


def _build_comarca_map() -> dict[str, str]:
    """Build comarca → territory code mapping from legacy municipis table."""
    comarca_map = {}
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT DISTINCT "Comarca", "Territori" FROM municipis'
        )
        for comarca, territori in cursor.fetchall():
            codi = MUNICIPIS_TERRITORI_MAP.get(territori)
            if codi and comarca:
                comarca_map[comarca.strip()] = codi
    return comarca_map


def get_territori(legacy_artista, comarca_map: dict[str, str]) -> str | None:
    """
    Determine territory code for a legacy artist.
    1. comarca → municipis → territory code
    2. Fallback: artistes.territori
    Returns territory code or None if unmappable.
    """
    # Try comarca lookup first
    comarca = (legacy_artista.comarca or "").strip()
    if comarca and comarca in comarca_map:
        return comarca_map[comarca]

    # Fallback to legacy territori field
    return LEGACY_TERRITORI_FALLBACK.get(legacy_artista.territori)


class Command(BaseCommand):
    help = "Import artists and tracks from legacy tables into new models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--artistes",
            action="store_true",
            help="Import artists only.",
        )
        parser.add_argument(
            "--cancons",
            action="store_true",
            help="Import tracks only.",
        )
        parser.add_argument(
            "--configuracio",
            action="store_true",
            help="Import configuracio_global only.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without writing to DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        import_all = not any(
            [options["artistes"], options["cancons"], options["configuracio"]]
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN — no changes will be saved.\n")
            )

        if import_all or options["configuracio"]:
            self._import_configuracio(dry_run)

        if import_all or options["artistes"]:
            self._import_artistes(dry_run)

        if import_all or options["cancons"]:
            self._import_cancons(dry_run)

    def _import_configuracio(self, dry_run: bool) -> None:
        self.stdout.write("Importing configuracio_global...")
        if not dry_run:
            ConfiguracioGlobal.load()
            self.stdout.write(
                self.style.SUCCESS("ConfiguracioGlobal: OK (defaults loaded)")
            )
        else:
            self.stdout.write("  Would create ConfiguracioGlobal with default values.")

    def _import_artistes(self, dry_run: bool) -> None:
        self.stdout.write("\nImporting artists from legacy `artistes` table...")

        territori_objs = {t.codi: t for t in Territori.objects.all()}
        if not territori_objs:
            raise CommandError(
                "No Territori objects found. Run migrations first."
            )

        comarca_map = _build_comarca_map()
        self.stdout.write(f"  Loaded {len(comarca_map)} comarca → territory mappings.")

        # Pre-load existing artists by spotify_id for update-in-place
        existing_by_spotify = {
            a.spotify_id: a
            for a in Artista.objects.all()
            if a.spotify_id
        }

        legacy_artistes = LegacyArtista.objects.all()
        total = legacy_artistes.count()
        self.stdout.write(f"  Found {total} legacy artists.")

        stats = Counter()
        territory_dist = Counter()
        # (artista_or_spotify_id, [territori_codes]) for M2M update
        territory_updates: list[tuple[str, str]] = []  # (spotify_id, codi)
        artistes_to_create = []

        for i, legacy in enumerate(legacy_artistes.iterator(), 1):
            is_active = legacy.status == "go"
            if not is_active:
                stats["skipped_inactive"] += 1
                continue

            territori_codi = get_territori(legacy, comarca_map)
            if territori_codi is None:
                stats["skipped_territory"] += 1
                continue

            territory_dist[territori_codi] += 1

            if legacy.id_spotify in existing_by_spotify:
                # Update territory in place — don't recreate
                territory_updates.append((legacy.id_spotify, territori_codi))
                stats["updated"] += 1
            else:
                artista = Artista(
                    spotify_id=legacy.id_spotify,
                    nom=legacy.nom or legacy.nom_spotify or "",
                    lastfm_nom=legacy.nom or legacy.nom_spotify or "",
                    aprovat=True,
                    auto_descobert=False,
                    font_descoberta="legacy",
                )
                artistes_to_create.append((artista, territori_codi))
                stats["created"] += 1

            if i % 500 == 0:
                self.stdout.write(f"  Processed {i}/{total}...")

        self.stdout.write("\n  Territory distribution:")
        for codi in sorted(territory_dist.keys()):
            self.stdout.write(f"    {codi}: {territory_dist[codi]}")

        if dry_run:
            self.stdout.write(
                f"\n  DRY RUN summary — Artists:\n"
                f"    Would update territories: {stats['updated']}\n"
                f"    Would create new: {stats['created']}\n"
                f"    Skipped (unmapped territory): {stats['skipped_territory']}\n"
                f"    Skipped (inactive status): {stats['skipped_inactive']}\n"
            )
            return

        with transaction.atomic():
            # Update territories for existing artists
            for spotify_id, codi in territory_updates:
                artista = existing_by_spotify[spotify_id]
                t = territori_objs.get(codi)
                if t:
                    artista.territoris.set([t])

            # Create new artists
            for artista, codi in artistes_to_create:
                artista.save()
                t = territori_objs.get(codi)
                if t:
                    artista.territoris.set([t])

        self.stdout.write(
            self.style.SUCCESS(
                f"\n  Artists import complete:\n"
                f"    Updated territories: {stats['updated']}\n"
                f"    Created new: {stats['created']}\n"
                f"    Skipped (territory): {stats['skipped_territory']}\n"
                f"    Skipped (inactive): {stats['skipped_inactive']}\n"
                f"    Total legacy rows: {total}"
            )
        )

    def _import_cancons(self, dry_run: bool) -> None:
        self.stdout.write("\nImporting tracks from legacy `cançons` table...")

        artista_map = {
            a.spotify_id: a
            for a in Artista.objects.filter(font_descoberta="legacy").exclude(
                spotify_id__isnull=True
            )
        }
        if not artista_map:
            raise CommandError(
                "No artists found with font_descoberta='legacy'. "
                "Run with --artistes first."
            )

        legacy_cancons = LegacyCanco.objects.filter(exclosa=False)
        total = legacy_cancons.count()
        self.stdout.write(f"  Found {total} legacy tracks (non-excluded).")

        stats = Counter()
        seen_ids: set[str] = set()
        albums_cache: dict[str, Album] = {}
        cancons_to_create: list[Canco] = []

        for i, legacy in enumerate(legacy_cancons.iterator(), 1):
            if legacy.id_canco in seen_ids:
                stats["deduplicated"] += 1
                continue
            seen_ids.add(legacy.id_canco)

            ids = legacy.artistes_ids
            if not ids or (isinstance(ids, list) and len(ids) == 0):
                stats["skipped_no_artist"] += 1
                continue
            main_spotify_id = ids[0] if isinstance(ids, list) else ids
            artista = artista_map.get(main_spotify_id)
            if artista is None:
                stats["skipped_no_artist"] += 1
                continue

            album = self._get_or_create_album(legacy, artista, albums_cache, dry_run)

            cancons_to_create.append(
                Canco(
                    spotify_id=legacy.id_canco,
                    nom=legacy.titol or "",
                    lastfm_nom=legacy.titol or "",
                    album=album,
                    artista=artista,
                    data_llancament=legacy.album_data,
                    activa=True,
                )
            )
            stats["imported"] += 1

            if i % 500 == 0:
                self.stdout.write(f"  Processed {i}/{total}...")

        if dry_run:
            self.stdout.write(
                f"\n  DRY RUN summary — Tracks:\n"
                f"    Would import: {stats['imported']}\n"
                f"    Deduplicated (same id_canco): {stats['deduplicated']}\n"
                f"    Skipped (no matching artist): {stats['skipped_no_artist']}\n"
                f"    Albums to create: {len(albums_cache)}\n"
            )
            return

        with transaction.atomic():
            deleted_c, _ = Canco.objects.filter(
                artista__font_descoberta="legacy"
            ).delete()
            deleted_a, _ = Album.objects.filter(
                artista__font_descoberta="legacy"
            ).delete()
            if deleted_c or deleted_a:
                self.stdout.write(
                    f"  Cleared {deleted_c} tracks and {deleted_a} albums "
                    f"from previous import."
                )

            albums_to_create = list(albums_cache.values())
            Album.objects.bulk_create(albums_to_create, ignore_conflicts=True)

            album_by_spotify = {
                a.spotify_id: a
                for a in Album.objects.filter(
                    artista__font_descoberta="legacy"
                ).exclude(spotify_id__isnull=True)
            }
            album_by_key = {
                (a.nom, a.artista_id): a
                for a in Album.objects.filter(artista__font_descoberta="legacy")
            }

            for canco in cancons_to_create:
                if canco.album.spotify_id and canco.album.spotify_id in album_by_spotify:
                    canco.album = album_by_spotify[canco.album.spotify_id]
                else:
                    key = (canco.album.nom, canco.album.artista_id)
                    if key in album_by_key:
                        canco.album = album_by_key[key]
                canco.album_id = canco.album.pk

            Canco.objects.bulk_create(cancons_to_create, ignore_conflicts=True)
            stats["created"] = len(cancons_to_create)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n  Tracks import complete:\n"
                f"    Created: {stats['created']}\n"
                f"    Deduplicated: {stats['deduplicated']}\n"
                f"    Skipped (no artist): {stats['skipped_no_artist']}\n"
                f"    Albums created: {len(albums_cache)}\n"
                f"    Total legacy rows: {total}"
            )
        )

    def _get_or_create_album(
        self,
        legacy: LegacyCanco,
        artista: Artista,
        cache: dict[str, Album],
        dry_run: bool,
    ) -> Album:
        """Get or create an Album from legacy track data. Uses in-memory cache."""
        album_id = legacy.album_id
        cache_key = album_id if album_id else f"_unknown_{artista.pk}_{legacy.titol}"

        if cache_key in cache:
            return cache[cache_key]

        album = Album(
            spotify_id=album_id if album_id else None,
            artista=artista,
            nom=legacy.album_titol or "Desconegut",
            data_llancament=legacy.album_data,
            imatge_url=legacy.album_caratula_url or "",
        )
        cache[cache_key] = album
        return album
