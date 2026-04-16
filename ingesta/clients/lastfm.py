import logging
import re
import time

import requests
from django.conf import settings

from music.constants import LASTFM_RATE_LIMIT, MAX_API_RETRIES

logger = logging.getLogger(__name__)

LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"
RATE_LIMIT_SLEEP = LASTFM_RATE_LIMIT
MAX_RETRIES = MAX_API_RETRIES

# Regex strips applied when a track is "not found" with the original name.
# Each pattern removes the matched suffix (anchored to end of string).
_TRACK_SUFFIX_STRIP = [
    # Parenthetical features / collaborations
    re.compile(
        r"\s*[\(\[]\s*(feat\.?|ft\.?|with|amb|featuring)\s+[^)\]]*[\)\]]\s*$", re.I
    ),
    # Parenthetical version/live/remix/etc tags (single trailing parenthetical)
    re.compile(
        r"\s*[\(\[]\s*("
        r"acoustic|acústica|live|en directe|en viu|directe|directo|"
        r"remix|version|versió|version|remaster(ed)?|"
        r"radio edit|edit|extended|instrumental|"
        r"bonus track|demo|single version|album version"
        r")[^)\]]*[\)\]]\s*$",
        re.I,
    ),
    # Catch-all trailing parenthetical with year reference (e.g. "(en Directe ... 2022)")
    re.compile(r"\s*[\(\[][^)\]]*\b(19|20)\d{2}\b[^)\]]*[\)\]]\s*$"),
    # Dash-separated version/live/etc suffixes
    re.compile(
        r"\s+-\s+("
        r"acoustic|acústica|live|en directe|en viu|directe|directo|"
        r"remix|version|versió|remaster(ed)?|"
        r"radio edit|edit|extended|instrumental|demo|"
        r"single version|album version|bonus track"
        r")\b.*$",
        re.I,
    ),
]

_UNICODE_PUNCT = {
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote / apostrophe
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
}


def _normalize_unicode(text: str) -> str:
    """Replace curly quotes and dashes with ASCII equivalents."""
    for src, dst in _UNICODE_PUNCT.items():
        text = text.replace(src, dst)
    return text


def _normalize_track(name: str) -> str:
    """Aggressive normalization for retry: strip parentheticals and suffixes."""
    name = _normalize_unicode(name)
    prev = None
    while prev != name:
        prev = name
        for pattern in _TRACK_SUFFIX_STRIP:
            name = pattern.sub("", name).strip()
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _api_call(artist_name: str, track_name: str) -> tuple[dict | None, int | None]:
    """
    Single Last.fm call with retries.
    Returns (data_dict, error_code) — data_dict is the parsed track on success,
    None otherwise; error_code is the Last.fm error number (e.g. 6 = not found)
    or None for transport errors.
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
                return None, int(data.get("error", 0))

            return data.get("track", {}), None

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

    return None, None


def _extract_returned_names(track: dict) -> tuple[str, str]:
    """Pull the name/artist Last.fm ACTUALLY returned (after autocorrect=1).

    Returns (returned_track, returned_artist). Empty strings if absent.
    The artist block can be either a dict ({"name": "X"}) or a string,
    depending on the API response shape — cover both.
    """
    returned_track = (track.get("name") or "").strip()
    artist_field = track.get("artist", "")
    if isinstance(artist_field, dict):
        returned_artist = (artist_field.get("name") or "").strip()
    elif isinstance(artist_field, str):
        returned_artist = artist_field.strip()
    else:
        returned_artist = ""
    return returned_track, returned_artist


def get_track_info(artist_name: str, track_name: str) -> dict | None:
    """
    Fetch cumulative playcount and listeners for a track from Last.fm.
    Returns a dict with playcount/listeners AND the names Last.fm actually
    returned (may differ from the input because autocorrect=1), or None
    on any failure.

    R5: `returned_track` and `returned_artist` are the names the API
    responded with. The caller compares them against what we asked for
    and flags silent drift. Without this, a track with a common name
    can accumulate playcount from a completely different artist without
    any signal that we're conflating them.

    On Last.fm "Track not found" (error 6), retries once with a normalized
    track name (parentheticals like "(feat. X)" / "(Acoustic Version)" and
    suffixes like " - Live" stripped, plus unicode quotes converted to ASCII).
    Never raises.
    """
    track, err = _api_call(artist_name, track_name)
    if track is not None:
        rt, ra = _extract_returned_names(track)
        return {
            "playcount": int(track.get("playcount", 0)),
            "listeners": int(track.get("listeners", 0)),
            "returned_track": rt,
            "returned_artist": ra,
        }

    # Retry with normalized name only on "Track not found"
    if err == 6:
        normalized = _normalize_track(track_name)
        if normalized and normalized != track_name:
            track2, err2 = _api_call(artist_name, normalized)
            if track2 is not None:
                logger.info(
                    "Last.fm recovered '%s'/'%s' via normalization to '%s'",
                    artist_name,
                    track_name,
                    normalized,
                )
                rt, ra = _extract_returned_names(track2)
                return {
                    "playcount": int(track2.get("playcount", 0)),
                    "listeners": int(track2.get("listeners", 0)),
                    "returned_track": rt,
                    "returned_artist": ra,
                }
            err = err2 if err2 is not None else err

    if err is not None:
        logger.warning(
            "Last.fm error %s for '%s' / '%s'",
            err,
            artist_name,
            track_name,
        )
    else:
        logger.error(
            "Last.fm: all retries exhausted for '%s' / '%s'",
            artist_name,
            track_name,
        )
    return None
