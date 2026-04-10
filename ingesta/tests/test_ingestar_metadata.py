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


def _make_artista(nom="Zoo", spotify_id="sp_zoo", aprovat=True, territori="CAT"):
    a = Artista.objects.create(
        nom=nom,
        lastfm_nom=nom,
        spotify_id=spotify_id,
        aprovat=aprovat,
    )
    a.territoris.set([Territori.objects.get(codi=territori)])
    return a


def _mock_spotify_client(albums=None, tracks=None, full_track=None):
    """Return a mock SpotifyClient with configurable responses."""
    client = MagicMock()
    client.get_artist_albums.return_value = albums or []
    client.get_album_tracks.return_value = tracks or []
    client.get_track.return_value = full_track
    return client


@pytest.mark.django_db
class TestIngestarMetadata:
    @patch("ingesta.management.commands.ingestar_metadata.SpotifyClient")
    def test_creates_album_and_track(self, MockClient):
        artista = _make_artista()
        recent = date.today() - timedelta(days=30)

        client = _mock_spotify_client(
            albums=[{
                "id": "alb1",
                "name": "Disc Nou",
                "release_date": recent,
                "album_type": "album",
                "image_url": "https://img.com/cover.jpg",
            }],
            tracks=[{
                "id": "trk1",
                "name": "Cançó 1",
                "duration_ms": 200000,
                "track_number": 1,
                "artists": [{"id": "sp_zoo", "name": "Zoo"}],
            }],
            full_track={
                "id": "trk1",
                "name": "Cançó 1",
                "duration_ms": 200000,
                "isrc": "ES0001234567",
                "artists": [{"id": "sp_zoo", "name": "Zoo"}],
            },
        )
        MockClient.return_value = client

        call_command("ingestar_metadata", artista_id=artista.pk)

        assert Album.objects.count() == 1
        album = Album.objects.first()
        assert album.nom == "Disc Nou"
        assert album.spotify_id == "alb1"
        assert album.artista == artista

        assert Canco.objects.count() == 1
        canco = Canco.objects.first()
        assert canco.nom == "Cançó 1"
        assert canco.isrc == "ES0001234567"
        assert canco.spotify_id == "trk1"
        assert canco.artista == artista

    @patch("ingesta.management.commands.ingestar_metadata.SpotifyClient")
    def test_skips_unapproved_artist(self, MockClient):
        artista = _make_artista(aprovat=False)
        MockClient.return_value = _mock_spotify_client()

        with pytest.raises(CommandError, match="No approved Artista"):
            call_command("ingestar_metadata", artista_id=artista.pk)

    @patch("ingesta.management.commands.ingestar_metadata.SpotifyClient")
    def test_skips_artist_without_spotify_id(self, MockClient):
        a = Artista.objects.create(
            nom="Manual Artist",
            lastfm_nom="Manual Artist",
            spotify_id=None,
            aprovat=True,
        )
        MockClient.return_value = _mock_spotify_client()

        with pytest.raises(CommandError, match="No approved Artista"):
            call_command("ingestar_metadata", artista_id=a.pk)

    @patch("ingesta.management.commands.ingestar_metadata.SpotifyClient")
    def test_dry_run_no_writes(self, MockClient):
        _make_artista()
        MockClient.return_value = _mock_spotify_client()

        call_command("ingestar_metadata", dry_run=True)

        assert Album.objects.count() == 0
        assert Canco.objects.count() == 0
        MockClient.assert_not_called()

    @patch("ingesta.management.commands.ingestar_metadata.SpotifyClient")
    def test_idempotent_without_force(self, MockClient):
        artista = _make_artista()
        recent = date.today() - timedelta(days=30)

        client = _mock_spotify_client(
            albums=[{
                "id": "alb1",
                "name": "Disc",
                "release_date": recent,
                "album_type": "single",
                "image_url": "",
            }],
            tracks=[{
                "id": "trk1",
                "name": "Track",
                "duration_ms": 180000,
                "track_number": 1,
                "artists": [{"id": "sp_zoo", "name": "Zoo"}],
            }],
            full_track={
                "id": "trk1",
                "name": "Track",
                "duration_ms": 180000,
                "isrc": "ES999",
                "artists": [{"id": "sp_zoo", "name": "Zoo"}],
            },
        )
        MockClient.return_value = client

        call_command("ingestar_metadata", artista_id=artista.pk)
        call_command("ingestar_metadata", artista_id=artista.pk)

        assert Album.objects.count() == 1
        assert Canco.objects.count() == 1

    @patch("ingesta.management.commands.ingestar_metadata.SpotifyClient")
    def test_links_collaborators(self, MockClient):
        artista = _make_artista(nom="Zoo", spotify_id="sp_zoo")
        collab = _make_artista(
            nom="Txarango", spotify_id="sp_txarango", territori="VAL"
        )
        recent = date.today() - timedelta(days=30)

        client = _mock_spotify_client(
            albums=[{
                "id": "alb1",
                "name": "Collab EP",
                "release_date": recent,
                "album_type": "single",
                "image_url": "",
            }],
            tracks=[{
                "id": "trk1",
                "name": "Duet",
                "duration_ms": 200000,
                "track_number": 1,
                "artists": [
                    {"id": "sp_zoo", "name": "Zoo"},
                    {"id": "sp_txarango", "name": "Txarango"},
                ],
            }],
            full_track={
                "id": "trk1",
                "name": "Duet",
                "duration_ms": 200000,
                "isrc": "ES555",
                "artists": [
                    {"id": "sp_zoo", "name": "Zoo"},
                    {"id": "sp_txarango", "name": "Txarango"},
                ],
            },
        )
        MockClient.return_value = client

        call_command("ingestar_metadata", artista_id=artista.pk)

        canco = Canco.objects.first()
        assert canco.artista == artista
        collab_ids = list(canco.artistes_col.values_list("spotify_id", flat=True))
        assert "sp_txarango" in collab_ids

    @patch("ingesta.management.commands.ingestar_metadata.SpotifyClient")
    def test_force_updates_existing(self, MockClient):
        artista = _make_artista()
        recent = date.today() - timedelta(days=30)

        # Pre-create with old data
        album = Album.objects.create(
            spotify_id="alb1", nom="Old Name", artista=artista, tipus="album"
        )
        Canco.objects.create(
            spotify_id="trk1",
            nom="Old Track",
            album=album,
            artista=artista,
            isrc="OLD",
        )

        client = _mock_spotify_client(
            albums=[{
                "id": "alb1",
                "name": "New Name",
                "release_date": recent,
                "album_type": "album",
                "image_url": "",
            }],
            tracks=[{
                "id": "trk1",
                "name": "New Track",
                "duration_ms": 210000,
                "track_number": 1,
                "artists": [{"id": "sp_zoo", "name": "Zoo"}],
            }],
            full_track={
                "id": "trk1",
                "name": "New Track",
                "duration_ms": 210000,
                "isrc": "NEW123",
                "artists": [{"id": "sp_zoo", "name": "Zoo"}],
            },
        )
        MockClient.return_value = client

        call_command("ingestar_metadata", artista_id=artista.pk, force=True)

        album.refresh_from_db()
        assert album.nom == "New Name"

        canco = Canco.objects.get(spotify_id="trk1")
        assert canco.nom == "New Track"
        assert canco.isrc == "NEW123"
