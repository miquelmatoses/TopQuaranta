"""
Regenerate clips/*.wav from manifest.tsv.

Manifest columns: label, pk, nom, artista, idioma.
- `pk` starting with a digit is a Canco primary key (DB lookup → fresh preview URL).
- `pk` starting with `d` is a raw Deezer track id for non-catalogued clips used for
  LID and out-of-distribution tests.

For each row, fetches a fresh Deezer preview URL (signed, expires in hours),
downloads the MP3, and converts to 16 kHz mono WAV via ffmpeg — the format
every runner expects.

Run from the project root with the full Django environment:

    DJANGO_SETTINGS_MODULE=topquaranta.settings.production \\
        .venv/bin/python scripts/model_comparison/fetch_clips.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen

import django

django.setup()

from ingesta.clients.deezer import _get  # noqa: E402
from music.models import Canco  # noqa: E402

HERE = Path(__file__).resolve().parent
CLIPS = HERE / "clips"
MANIFEST = HERE / "manifest.tsv"


def _preview_url_for(pk: str) -> str | None:
    """Resolve a manifest pk to a Deezer preview URL."""
    if pk.startswith("d"):
        deezer_id = int(pk[1:])
    else:
        canco = Canco.objects.filter(pk=int(pk)).first()
        if not canco or not canco.deezer_id:
            return None
        deezer_id = canco.deezer_id
    data = _get(f"https://api.deezer.com/track/{deezer_id}")
    return (data or {}).get("preview")


def _download(url: str, dest: Path) -> None:
    req = Request(url, headers={"User-Agent": "topquaranta-harness/1.0"})
    with urlopen(req, timeout=15) as resp:
        dest.write_bytes(resp.read())


def _to_wav(mp3: Path, wav: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(mp3),
            "-ar",
            "16000",
            "-ac",
            "1",
            str(wav),
        ],
        check=True,
    )


def main() -> int:
    CLIPS.mkdir(exist_ok=True)
    rows = MANIFEST.read_text().strip().split("\n")[1:]
    ok = skipped = failed = 0
    for row in rows:
        parts = row.split("\t")
        label, pk, nom, artista = parts[0], parts[1], parts[2], parts[3]
        wav = CLIPS / f"{pk}.wav"
        if wav.exists():
            skipped += 1
            continue
        try:
            preview = _preview_url_for(pk)
            if not preview:
                print(f"  [{label:5}] {pk:>14} SKIP no preview  {nom[:40]}")
                failed += 1
                continue
            mp3 = CLIPS / f"{pk}.mp3"
            _download(preview, mp3)
            _to_wav(mp3, wav)
            mp3.unlink()
            ok += 1
            print(f"  [{label:5}] {pk:>14} OK  {nom[:40]} — {artista[:30]}")
        except Exception as exc:
            print(f"  [{label:5}] {pk:>14} FAIL {exc!r}  {nom[:40]}")
            failed += 1
    print(
        f"\n{ok} fetched, {skipped} already present, {failed} failed, {len(rows)} total."
    )
    # Exit codes:
    #   0 — clean run (nothing failed, or at least something got fetched)
    #   1 — every attempt failed (all previews expired, or Deezer down)
    #   2 — mixed: some failures, some successes (investigate but not a disaster)
    if failed == 0:
        return 0
    if ok == 0 and skipped == 0:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
