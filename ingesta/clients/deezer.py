import logging
import time
import unicodedata
from datetime import date

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.deezer.com"
RATE_LIMIT_SLEEP = 0.1
MAX_RETRIES = 3


def _normalize(name: str) -> str:
    """Lowercase, strip accents, strip whitespace."""
    name = name.strip().lower()
    # Decompose unicode, remove combining marks (accents)
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _get(url: str, params: dict | None = None) -> dict | None:
    """GET with retry and rate limiting. Returns parsed JSON or None."""
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(RATE_LIMIT_SLEEP)
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # Deezer returns {"error": {...}} on some failures
            if "error" in data:
                logger.warning("Deezer error for %s: %s", url, data["error"])
                return None

            return data

        except requests.RequestException as exc:
            wait = 2 ** attempt
            logger.warning(
                "Deezer attempt %d/%d failed for %s: %s — retry in %ds",
                attempt + 1, MAX_RETRIES, url, exc, wait,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)

    logger.error("Deezer: all retries exhausted for %s", url)
    return None


def search_artist(nom: str) -> dict | None:
    """
    Search Deezer for an artist by name.
    Returns {"id": int, "name": str} for the best match, or None.

    Matching strategy:
    1. Exact normalized name match
    2. Containment (Deezer name contains ours or vice versa)
    Never returns the first result without verification.
    """
    data = _get(f"{API_BASE}/search/artist", params={"q": nom, "limit": 10})
    if not data:
        return None

    results = data.get("data", [])
    if not results:
        return None

    nom_norm = _normalize(nom)

    # Pass 1: exact normalized match
    for artist in results:
        if _normalize(artist["name"]) == nom_norm:
            return {"id": artist["id"], "name": artist["name"]}

    # Pass 2: containment — our name in theirs or theirs in ours
    for artist in results:
        deezer_norm = _normalize(artist["name"])
        if nom_norm in deezer_norm or deezer_norm in nom_norm:
            return {"id": artist["id"], "name": artist["name"]}

    logger.info("Deezer: no matching artist for '%s' (candidates: %s)",
                nom, [a["name"] for a in results[:3]])
    return None


def get_artist_albums(deezer_id: int, min_date: date | None = None) -> list[dict]:
    """
    Fetch albums for a Deezer artist, optionally filtered by release date.
    Returns list of dicts: {id, title, release_date, cover_xl, record_type}.
    """
    albums = []
    url = f"{API_BASE}/artist/{deezer_id}/albums"
    params = {"limit": 100}

    while url:
        data = _get(url, params=params)
        if not data:
            break

        for item in data.get("data", []):
            release_str = item.get("release_date", "")
            release_date = _parse_date(release_str)

            if min_date and release_date and release_date < min_date:
                continue

            record_type = item.get("record_type", "album")

            albums.append({
                "id": item["id"],
                "title": item.get("title", ""),
                "release_date": release_date,
                "cover_xl": item.get("cover_xl", ""),
                "record_type": record_type,
            })

        next_url = data.get("next")
        if next_url:
            url = next_url
            params = None
        else:
            break

    return albums


def get_album_tracks(album_id: int) -> list[dict]:
    """
    Fetch tracks for a Deezer album.
    For each track, fetches the full track endpoint to get ISRC.
    Returns list of dicts: {id, title, duration, isrc, artist_id, artist_name}.
    """
    data = _get(f"{API_BASE}/album/{album_id}/tracks")
    if not data:
        return []

    tracks = []
    for item in data.get("data", []):
        track_id = item["id"]

        # Fetch full track to get ISRC
        full = _get(f"{API_BASE}/track/{track_id}")
        isrc = full.get("isrc", "") if full else ""

        artist = item.get("artist", {})
        tracks.append({
            "id": track_id,
            "title": item.get("title", ""),
            "duration": item.get("duration", 0),
            "isrc": isrc,
            "artist_id": artist.get("id"),
            "artist_name": artist.get("name", ""),
        })

    return tracks


def _parse_date(date_str: str) -> date | None:
    """Parse YYYY-MM-DD date string."""
    if not date_str:
        return None
    try:
        parts = date_str.split("-")
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, TypeError):
        return None
    return None
