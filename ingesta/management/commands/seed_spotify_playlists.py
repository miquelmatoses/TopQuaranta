"""Seed the `SpotifyPlaylist` rows the daily sync expects.

Creates (or leaves untouched) one row per territori-top + a novetats
row. `spotify_playlist_id` is left blank — the admin wires it up via
`configurar_spotify_playlists`.

Idempotent: safe to run on every deploy.
"""

from django.core.management.base import BaseCommand

from music.models import SpotifyPlaylist

SEED = [
    {"codi": "top-cat", "kind": SpotifyPlaylist.KIND_TOP, "territori": "CAT"},
    {"codi": "top-val", "kind": SpotifyPlaylist.KIND_TOP, "territori": "VAL"},
    {"codi": "top-bal", "kind": SpotifyPlaylist.KIND_TOP, "territori": "BAL"},
    {"codi": "top-alt", "kind": SpotifyPlaylist.KIND_TOP, "territori": "ALT"},
    {"codi": "novetats", "kind": SpotifyPlaylist.KIND_NOVETATS, "territori": ""},
]


class Command(BaseCommand):
    help = "Idempotently seed SpotifyPlaylist rows (top-CAT/VAL/BAL/ALT + novetats)."

    def handle(self, *args, **opts):
        for spec in SEED:
            obj, created = SpotifyPlaylist.objects.get_or_create(
                codi=spec["codi"],
                defaults=spec,
            )
            verb = "creat" if created else "existent"
            self.stdout.write(
                f"  - {obj.codi}  [{verb}]  "
                f"spotify_id='{obj.spotify_playlist_id or '(no configurat)'}'"
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Llest. Ara executa `configurar_spotify_playlists --<codi> <spotify_id>` "
                "per cada playlist."
            )
        )
