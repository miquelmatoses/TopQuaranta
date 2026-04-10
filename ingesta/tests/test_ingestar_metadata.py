from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from music.models import Album, Artista, Canco, Territori


@pytest.fixture(autouse=True)
def territoris():
    Territori.objects.get_or_create(codi="CAT", defaults={"nom": "Catalunya"})
    Territori.objects.get_or_create(codi="VAL", defaults={"nom": "País Valencià"})


def _make_artista(nom="Zoo", spotify_id="sp_zoo", deezer_id=None, aprovat=True, territori="CAT"):
    a = Artista.objects.create(
        nom=nom,
        lastfm_nom=nom,
        spotify_id=spotify_id,
        deezer_id=deezer_id,
        aprovat=aprovat,
    )
    a.territoris.set([Territori.objects.get(codi=territori)])
    return a


RECENT = date.today() - timedelta(days=30)

MOCK_ALBUM = {
    "id": 100,
    "title": "Disc Nou",
    "release_date": RECENT,
    "cover_xl": "https://img.com/cover.jpg",
    "record_type": "album",
}

MOCK_TRACK = {
    "id": 500,
    "title": "Cançó 1",
    "duration": 200,
    "isrc": "ES0001234567",
    "artist_id": 98469,
    "artist_name": "Zoo",
}


@pytest.mark.django_db
class TestIngestarMetadataDeezer:
    @patch("ingesta.management.commands.ingestar_metadata.deezer")
    def test_creates_album_and_track_with_known_deezer_id(self, mock_deezer):
        artista = _make_artista(deezer_id=98469)

        mock_deezer.get_artist_albums.return_value = [MOCK_ALBUM]
        mock_deezer.get_album_tracks.return_value = [MOCK_TRACK]

        call_command("ingestar_metadata", artista_id=artista.pk)

        assert Album.objects.count() == 1
        album = Album.objects.first()
        assert album.nom == "Disc Nou"
        assert album.deezer_id == 100

        assert Canco.objects.count() == 1
        canco = Canco.objects.first()
        assert canco.nom == "Cançó 1"
        assert canco.isrc == "ES0001234567"
        assert canco.deezer_id == 500

    @patch("ingesta.management.commands.ingestar_metadata.deezer")
    def test_resolves_deezer_id_via_search_and_isrc(self, mock_deezer):
        artista = _make_artista(deezer_id=None)
        # Create a known track with ISRC for validation
        album = Album.objects.create(
            spotify_id="alb_old", nom="Old Album", artista=artista
        )
        Canco.objects.create(
            spotify_id="trk_old", nom="Old Track", album=album,
            artista=artista, isrc="ES0001234567",
        )

        mock_deezer.search_artist.return_value = {"id": 98469, "name": "ZOO"}
        # First get_artist_albums call: for ISRC validation (up to 3 albums)
        # Second call: for actual album fetching
        mock_deezer.get_artist_albums.side_effect = [
            [{"id": 900, "title": "Val Album", "release_date": RECENT,
              "cover_xl": "", "record_type": "album"}],
            [MOCK_ALBUM],
        ]
        mock_deezer.get_album_tracks.side_effect = [
            [{"id": 901, "title": "Match", "duration": 180, "isrc": "ES0001234567",
              "artist_id": 98469, "artist_name": "Zoo"}],
            [MOCK_TRACK],
        ]

        call_command("ingestar_metadata", artista_id=artista.pk)

        artista.refresh_from_db()
        assert artista.deezer_id == 98469
        assert artista.deezer_no_trobat is False

    @patch("ingesta.management.commands.ingestar_metadata.deezer")
    def test_marks_not_found_when_search_fails(self, mock_deezer):
        artista = _make_artista(deezer_id=None)

        mock_deezer.search_artist.return_value = None

        call_command("ingestar_metadata", artista_id=artista.pk)

        artista.refresh_from_db()
        assert artista.deezer_no_trobat is True
        assert artista.deezer_id is None

    @patch("ingesta.management.commands.ingestar_metadata.deezer")
    def test_marks_not_found_when_isrc_validation_fails(self, mock_deezer):
        artista = _make_artista(deezer_id=None)
        album = Album.objects.create(
            spotify_id="alb1", nom="Album", artista=artista
        )
        Canco.objects.create(
            spotify_id="trk1", nom="Track", album=album,
            artista=artista, isrc="REAL_ISRC_123",
        )

        mock_deezer.search_artist.return_value = {"id": 999, "name": "Wrong Artist"}
        mock_deezer.get_artist_albums.return_value = [
            {"id": 800, "title": "X", "release_date": RECENT,
             "cover_xl": "", "record_type": "album"}
        ]
        mock_deezer.get_album_tracks.return_value = [
            {"id": 801, "title": "Y", "duration": 100,
             "isrc": "DIFFERENT_ISRC", "artist_id": 999, "artist_name": "Wrong"}
        ]

        call_command("ingestar_metadata", artista_id=artista.pk)

        artista.refresh_from_db()
        assert artista.deezer_no_trobat is True
        assert artista.deezer_id is None

    @patch("ingesta.management.commands.ingestar_metadata.deezer")
    def test_skips_unapproved_artist(self, mock_deezer):
        artista = _make_artista(aprovat=False)

        with pytest.raises(CommandError, match="No approved Artista"):
            call_command("ingestar_metadata", artista_id=artista.pk)

    @patch("ingesta.management.commands.ingestar_metadata.deezer")
    def test_dry_run_no_writes(self, mock_deezer):
        _make_artista(deezer_id=98469)

        call_command("ingestar_metadata", dry_run=True)

        assert Album.objects.count() == 0
        assert Canco.objects.count() == 0
        mock_deezer.search_artist.assert_not_called()
        mock_deezer.get_artist_albums.assert_not_called()

    @patch("ingesta.management.commands.ingestar_metadata.deezer")
    def test_idempotent_without_force(self, mock_deezer):
        artista = _make_artista(deezer_id=98469)

        mock_deezer.get_artist_albums.return_value = [MOCK_ALBUM]
        mock_deezer.get_album_tracks.return_value = [MOCK_TRACK]

        call_command("ingestar_metadata", artista_id=artista.pk)
        call_command("ingestar_metadata", artista_id=artista.pk)

        assert Album.objects.count() == 1
        assert Canco.objects.count() == 1

    @patch("ingesta.management.commands.ingestar_metadata.deezer")
    def test_force_updates_existing(self, mock_deezer):
        artista = _make_artista(deezer_id=98469)

        # Pre-create
        album = Album.objects.create(
            deezer_id=100, nom="Old Name", artista=artista, tipus="album"
        )
        Canco.objects.create(
            deezer_id=500, nom="Old Track", album=album,
            artista=artista, isrc="OLD",
        )

        mock_deezer.get_artist_albums.return_value = [{
            **MOCK_ALBUM, "title": "New Name",
        }]
        mock_deezer.get_album_tracks.return_value = [{
            **MOCK_TRACK, "title": "New Track", "isrc": "NEW123",
        }]

        call_command("ingestar_metadata", artista_id=artista.pk, force=True)

        album.refresh_from_db()
        assert album.nom == "New Name"

        canco = Canco.objects.get(deezer_id=500)
        assert canco.nom == "New Track"
        assert canco.isrc == "NEW123"

    @patch("ingesta.management.commands.ingestar_metadata.deezer")
    def test_skips_deezer_no_trobat_artists(self, mock_deezer):
        artista = _make_artista(deezer_id=None)
        artista.deezer_no_trobat = True
        artista.save()

        call_command("ingestar_metadata")

        mock_deezer.search_artist.assert_not_called()

    @patch("ingesta.management.commands.ingestar_metadata.deezer")
    def test_accepts_name_match_without_isrc(self, mock_deezer):
        """Artist with no known ISRC tracks — accept name match."""
        artista = _make_artista(deezer_id=None)
        # No tracks with ISRC exist

        mock_deezer.search_artist.return_value = {"id": 98469, "name": "ZOO"}
        mock_deezer.get_artist_albums.return_value = [MOCK_ALBUM]
        mock_deezer.get_album_tracks.return_value = [MOCK_TRACK]

        call_command("ingestar_metadata", artista_id=artista.pk)

        artista.refresh_from_db()
        assert artista.deezer_id == 98469
        assert Canco.objects.count() == 1
