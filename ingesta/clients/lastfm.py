import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"
RATE_LIMIT_SLEEP = 0.2
MAX_RETRIES = 3


def get_track_info(artist_name: str, track_name: str) -> dict | None:
    """
    Fetch cumulative playcount and listeners for a track from Last.fm.
    Returns {'playcount': int, 'listeners': int} or None on any failure.
    Never raises.
    """
    params = {
        "method": "track.getInfo",
        "api_key": settings.LASTFM_API_KEY,
        "artist": artist_name,
        "track": track_name,
        "format": "json",
        "autocorrect": 1,
    }

    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(RATE_LIMIT_SLEEP)
            response = requests.get(LASTFM_API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.warning(
                    "Last.fm error %s for '%s' / '%s': %s",
                    data["error"],
                    artist_name,
                    track_name,
                    data.get("message"),
                )
                return None

            track = data.get("track", {})
            return {
                "playcount": int(track.get("playcount", 0)),
                "listeners": int(track.get("listeners", 0)),
            }

        except requests.RequestException as exc:
            wait = 2**attempt
            logger.warning(
                "Last.fm attempt %d/%d failed for '%s'/'%s': %s — retry in %ds",
                attempt + 1,
                MAX_RETRIES,
                artist_name,
                track_name,
                exc,
                wait,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)

    logger.error(
        "Last.fm: all retries exhausted for '%s' / '%s'", artist_name, track_name
    )
    return None
