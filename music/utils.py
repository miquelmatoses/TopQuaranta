"""Shared helpers for the music app.

Small reusable utilities that don't belong to any single model or
command. Keep this file dependency-minimal — importing heavy modules
from here creates import cycles.
"""

from __future__ import annotations

import unicodedata


def normalize_nom(s: str) -> str:
    """Fold a name for duplicate detection.

    NFKD → strip diacritics → lowercase → collapse whitespace.
    Used by the /staff/artistes/?duplicats=si filter and the
    artist-create duplicate guard; lives here so new callers don't
    re-roll their own.
    """
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())
