"""Set the Spotify playlist IDs the admin has already created.

Usage:

    manage.py configurar_spotify_playlists \
        --top-cat  37i9dQZF1DZ06evO4xjGEc \
        --top-val  37i9dQZF1DZ0... \
        --top-bal  37i9dQZF1DZ0... \
        --top-alt  37i9dQZF1DZ0... \
        --novetats 37i9dQZF1DZ0...

Only the flags you pass get updated; omit a flag to leave the
existing value alone. The daily sync skips any playlist with an
empty `spotify_playlist_id`.
"""

from django.core.management.base import BaseCommand, CommandError

from music.models import SpotifyPlaylist

FLAG_TO_CODI = {
    "top_cat": "top-cat",
    "top_val": "top-val",
    "top_bal": "top-bal",
    "top_alt": "top-alt",
    "novetats": "novetats",
}


class Command(BaseCommand):
    help = "Attach existing Spotify playlist IDs to the seeded SpotifyPlaylist rows."

    def add_arguments(self, parser):
        for flag in FLAG_TO_CODI:
            parser.add_argument(
                f"--{flag.replace('_', '-')}",
                dest=flag,
                default=None,
                help=f"Spotify playlist ID for {FLAG_TO_CODI[flag]}",
            )

    def handle(self, *args, **opts):
        changed = 0
        for flag, codi in FLAG_TO_CODI.items():
            value = (opts.get(flag) or "").strip()
            if not value:
                continue
            try:
                pl = SpotifyPlaylist.objects.get(codi=codi)
            except SpotifyPlaylist.DoesNotExist:
                raise CommandError(
                    f"No hi ha cap SpotifyPlaylist amb codi={codi}. "
                    "Executa primer `seed_spotify_playlists`."
                )
            pl.spotify_playlist_id = value
            pl.save(update_fields=["spotify_playlist_id"])
            self.stdout.write(f"  - {codi} → {value}")
            changed += 1

        if changed == 0:
            self.stdout.write(self.style.WARNING("Cap flag. Mostra l'estat actual:"))
            for pl in SpotifyPlaylist.objects.order_by("codi"):
                self.stdout.write(
                    f"  - {pl.codi}: {pl.spotify_playlist_id or '(no configurat)'}"
                )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"{changed} playlist(s) actualitzades.")
            )
