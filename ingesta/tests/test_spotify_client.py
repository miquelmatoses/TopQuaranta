from datetime import date
from unittest.mock import patch, MagicMock

import pytest
import requests

from ingesta.clients.spotify import SpotifyClient, _parse_release_date


class TestParseReleaseDate:
    def test_full_date(self):
        assert _parse_release_date("2025-06-15") == date(2025, 6, 15)

    def test_year_month(self):
        assert _parse_release_date("2025-06") == date(2025, 6, 1)

    def test_year_only(self):
        assert _parse_release_date("2025") == date(2025, 1, 1)

    def test_empty(self):
        assert _parse_release_date("") is None

    def test_invalid(self):
        assert _parse_release_date("not-a-date") is None


@pytest.mark.django_db
class TestSpotifyClientAuth:
    @patch("ingesta.clients.spotify.requests.post")
    @patch("ingesta.clients.spotify.requests.get")
    def test_authenticates_on_first_request(self, mock_get, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"access_token": "tok123"}),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"items": [], "next": None}),
        )
        mock_get.return_value.raise_for_status = MagicMock()

        client = SpotifyClient()
        client.get_artist_albums("artist123")

        mock_post.assert_called_once()
        assert "grant_type" in mock_post.call_args[1]["data"]

    @patch("ingesta.clients.spotify.requests.post")
    @patch("ingesta.clients.spotify.requests.get")
    def test_refreshes_token_on_401(self, mock_get, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"access_token": "new_tok"}),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        # First call: 401, second call: success
        resp_401 = MagicMock(status_code=401)
        resp_ok = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"items": [], "next": None}),
        )
        resp_ok.raise_for_status = MagicMock()
        mock_get.side_effect = [resp_401, resp_ok]

        client = SpotifyClient()
        client.get_artist_albums("artist123")

        # Token refreshed: initial auth + refresh
        assert mock_post.call_count == 2


@pytest.mark.django_db
class TestGetArtistAlbums:
    @patch("ingesta.clients.spotify.requests.post")
    @patch("ingesta.clients.spotify.requests.get")
    def test_returns_albums_filtered_by_date(self, mock_get, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"access_token": "tok"}),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "items": [
                    {
                        "id": "alb1",
                        "name": "Recent Album",
                        "release_date": "2026-01-15",
                        "album_type": "album",
                        "images": [{"url": "https://img.com/1.jpg"}],
                    },
                    {
                        "id": "alb2",
                        "name": "Old Album",
                        "release_date": "2020-01-01",
                        "album_type": "album",
                        "images": [],
                    },
                ],
                "next": None,
            }),
        )
        mock_get.return_value.raise_for_status = MagicMock()

        client = SpotifyClient()
        albums = client.get_artist_albums("art1", min_date=date(2025, 4, 10))

        assert len(albums) == 1
        assert albums[0]["name"] == "Recent Album"
        assert albums[0]["image_url"] == "https://img.com/1.jpg"

    @patch("ingesta.clients.spotify.requests.post")
    @patch("ingesta.clients.spotify.requests.get")
    def test_returns_empty_on_failure(self, mock_get, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"access_token": "tok"}),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        mock_get.side_effect = requests.RequestException("timeout")

        client = SpotifyClient()
        albums = client.get_artist_albums("art1")

        assert albums == []


@pytest.mark.django_db
class TestGetTrack:
    @patch("ingesta.clients.spotify.requests.post")
    @patch("ingesta.clients.spotify.requests.get")
    def test_returns_isrc(self, mock_get, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"access_token": "tok"}),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "id": "track1",
                "name": "La cançó",
                "duration_ms": 210000,
                "external_ids": {"isrc": "ES1234567890"},
                "artists": [{"id": "art1", "name": "Zoo"}],
            }),
        )
        mock_get.return_value.raise_for_status = MagicMock()

        client = SpotifyClient()
        track = client.get_track("track1")

        assert track is not None
        assert track["isrc"] == "ES1234567890"
        assert track["name"] == "La cançó"
