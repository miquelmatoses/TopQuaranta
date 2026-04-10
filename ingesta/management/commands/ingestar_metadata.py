import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ingesta.clients.spotify import SpotifyClient
from music.models import Album, Artista, Canco

logger = logging.getLogger(__name__)

ALBUM_TYPE_MAP = {
    "album": "album",
    "single": "single",
    "compilation": "album",
}


class Command(BaseCommand):
    help = "Fetch Spotify metadata (albums + tracks) for approved artists."

    def add_arguments(self, parser):
        parser.add_argument(
            "--artista-id",
            type=int,
            default=None,
            help="Only process this Artista PK.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-fetch even if albums/tracks already exist.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be fetched without calling Spotify or writing to DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        artista_id = options["artista_id"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN — no API calls, no DB writes.\n")
            )

        # Build queryset
        qs = Artista.objects.filter(aprovat=True).exclude(spotify_id__isnull=True).exclude(spotify_id="")

        if artista_id:
            qs = qs.filter(pk=artista_id)
            if not qs.exists():
                raise CommandError(f"No approved Artista with pk={artista_id} and a spotify_id found.")

        total = qs.count()
        self.stdout.write(f"Artists to process: {total}")

        cutoff = date.today() - timedelta(days=365)
        self.stdout.write(f"Release cutoff: {cutoff} (only albums released after this date)")

        if dry_run:
            for a in qs[:20]:
                self.stdout.write(f"  Would fetch: {a.nom} (spotify_id={a.spotify_id})")
            if total > 20:
                self.stdout.write(f"  ... and {total - 20} more")
            return

        client = SpotifyClient()

        artists_ok = 0
        artists_err = 0
        albums_created = 0
        albums_updated = 0
        tracks_created = 0
        tracks_updated = 0

        for i, artista in enumerate(qs.iterator(), 1):
            try:
                a_new, a_upd, t_new, t_upd = self._process_artist(
                    client, artista, cutoff, force
                )
                albums_created += a_new
                albums_updated += a_upd
                tracks_created += t_new
                tracks_updated += t_upd
                artists_ok += 1
            except Exception as exc:
                logger.error("Error processing %s: %s", artista.nom, exc)
                artists_err += 1

            if i % 50 == 0:
                self.stdout.write(
                    f"  Processed {i}/{total}... "
                    f"(albums: +{albums_created}/~{albums_updated}, "
                    f"tracks: +{tracks_created}/~{tracks_updated})"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nMetadata ingestion complete:\n"
                f"  Artists OK: {artists_ok}\n"
                f"  Artists errors: {artists_err}\n"
                f"  Albums created: {albums_created}\n"
                f"  Albums updated: {albums_updated}\n"
                f"  Tracks created: {tracks_created}\n"
                f"  Tracks updated: {tracks_updated}"
            )
        )

    def _process_artist(
        self,
        client: SpotifyClient,
        artista: Artista,
        cutoff: date,
        force: bool,
    ) -> tuple[int, int, int, int]:
        """
        Fetch and store albums + tracks for one artist.
        Returns (albums_created, albums_updated, tracks_created, tracks_updated).
        """
        albums_data = client.get_artist_albums(artista.spotify_id, min_date=cutoff)
        if albums_data is None:
            logger.warning("No album data returned for %s", artista.nom)
            return 0, 0, 0, 0

        a_created = 0
        a_updated = 0
        t_created = 0
        t_updated = 0

        for album_data in albums_data:
            album, was_created = self._upsert_album(artista, album_data, force)
            if was_created:
                a_created += 1
            elif force:
                a_updated += 1

            tracks_data = client.get_album_tracks(album_data["id"])
            if not tracks_data:
                continue

            for track_data in tracks_data:
                # Fetch full track to get ISRC
                full_track = client.get_track(track_data["id"])
                if full_track:
                    track_data["isrc"] = full_track.get("isrc", "")

                was_new = self._upsert_track(
                    artista, album, track_data, force
                )
                if was_new:
                    t_created += 1
                elif force:
                    t_updated += 1

        return a_created, a_updated, t_created, t_updated

    def _upsert_album(
        self, artista: Artista, data: dict, force: bool
    ) -> tuple[Album, bool]:
        """Create or update an Album. Returns (album, was_created)."""
        tipus = ALBUM_TYPE_MAP.get(data.get("album_type", "album"), "album")

        defaults = {
            "nom": data["name"],
            "artista": artista,
            "data_llancament": data.get("release_date"),
            "tipus": tipus,
            "imatge_url": data.get("image_url", ""),
        }

        with transaction.atomic():
            if force:
                album, created = Album.objects.update_or_create(
                    spotify_id=data["id"],
                    defaults=defaults,
                )
            else:
                album, created = Album.objects.get_or_create(
                    spotify_id=data["id"],
                    defaults=defaults,
                )

        return album, created

    def _upsert_track(
        self, artista: Artista, album: Album, data: dict, force: bool
    ) -> bool:
        """Create or update a Canco. Returns True if newly created."""
        defaults = {
            "nom": data["name"],
            "album": album,
            "artista": artista,
            "durada_ms": data.get("duration_ms"),
            "isrc": data.get("isrc", ""),
            "data_llancament": album.data_llancament,
        }

        with transaction.atomic():
            if force:
                canco, created = Canco.objects.update_or_create(
                    spotify_id=data["id"],
                    defaults=defaults,
                )
            else:
                canco, created = Canco.objects.get_or_create(
                    spotify_id=data["id"],
                    defaults=defaults,
                )

        # Handle collaborators — link any known artists from the track's artist list
        if created or force:
            track_artist_ids = [a["id"] for a in data.get("artists", [])]
            # Exclude the main artist
            collab_ids = [aid for aid in track_artist_ids if aid != artista.spotify_id]
            if collab_ids:
                collabs = Artista.objects.filter(spotify_id__in=collab_ids)
                canco.artistes_col.set(collabs)

        return created
