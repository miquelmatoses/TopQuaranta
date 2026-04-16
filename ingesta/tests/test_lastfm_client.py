from unittest.mock import patch, call

import pytest
import requests

from ingesta.clients.lastfm import get_track_info, RATE_LIMIT_SLEEP, MAX_RETRIES


FAKE_API_KEY = "test_api_key_123"


@pytest.fixture(autouse=True)
def lastfm_settings(settings):
    settings.LASTFM_API_KEY = FAKE_API_KEY


class TestGetTrackInfoSuccess:
    @patch("ingesta.clients.lastfm.time.sleep")
    @patch("ingesta.clients.lastfm.requests.get")
    def test_success(self, mock_get, mock_sleep):
        """Mocked 200 → correct playcount and listeners."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = {
            "track": {
                "name": "Benvolguts",
                "artist": {"name": "Txarango"},
                "playcount": "12345",
                "listeners": "678",
            }
        }

        result = get_track_info("Txarango", "Benvolguts")

        # R5: response includes the names Last.fm actually returned so the
        # caller can detect silent autocorrect drift.
        assert result == {
            "playcount": 12345,
            "listeners": 678,
            "returned_track": "Benvolguts",
            "returned_artist": "Txarango",
        }
        mock_get.assert_called_once()
        params = mock_get.call_args[1]["params"]
        assert params["artist"] == "Txarango"
        assert params["track"] == "Benvolguts"
        assert params["api_key"] == FAKE_API_KEY
        assert params["autocorrect"] == 1


class TestGetTrackInfoTrackNotFound:
    @patch("ingesta.clients.lastfm.time.sleep")
    @patch("ingesta.clients.lastfm.requests.get")
    def test_track_not_found(self, mock_get, mock_sleep):
        """Last.fm error 6 → returns None, no exception."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = {
            "error": 6,
            "message": "Track not found",
        }

        result = get_track_info("Unknown Artist", "Unknown Track")

        assert result is None
        # Should not retry on API-level errors
        assert mock_get.call_count == 1


class TestGetTrackInfoNetworkError:
    @patch("ingesta.clients.lastfm.time.sleep")
    @patch("ingesta.clients.lastfm.requests.get")
    def test_network_error(self, mock_get, mock_sleep):
        """RequestException → None after MAX_RETRIES."""
        mock_get.side_effect = requests.RequestException("Connection refused")

        result = get_track_info("Txarango", "Benvolguts")

        assert result is None
        assert mock_get.call_count == MAX_RETRIES


class TestGetTrackInfoRateLimit:
    @patch("ingesta.clients.lastfm.time.sleep")
    @patch("ingesta.clients.lastfm.requests.get")
    def test_rate_limit_sleep(self, mock_get, mock_sleep):
        """time.sleep called with RATE_LIMIT_SLEEP before each request."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = {
            "track": {"playcount": "1", "listeners": "1"}
        }

        get_track_info("Zoo", "Bona Nit")

        # First call to sleep should be the rate limit
        assert mock_sleep.call_args_list[0] == call(RATE_LIMIT_SLEEP)
