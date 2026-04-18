"""
Regenerate clips/*.wav from manifest.tsv.

Looks up each Canco by pk, fetches a fresh Deezer preview URL (preview URLs are
signed and expire in hours), downloads the MP3, and converts to 16 kHz mono WAV
via ffmpeg — the format every runner expects.

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

from ingesta.clients.deezer import DeezerClient  # noqa: E402
from music.models import Canco  # noqa: E402

HERE = Path(__file__).resolve().parent
CLIPS = HERE / "clips"
MANIFEST = HERE / "manifest.tsv"


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
    client = DeezerClient()
    rows = MANIFEST.read_text().strip().split("\n")[1:]
    ok = failed = 0
    for row in rows:
        label, pk, nom, artista, _mp3, _wav = row.split("\t")
        wav = CLIPS / f"{pk}.wav"
        if wav.exists():
            ok += 1
            continue
        canco = Canco.objects.filter(pk=int(pk)).first()
        if not canco or not canco.deezer_id:
            print(f"  [{label:5}] {pk:>5} SKIP no deezer_id  {nom[:40]}")
            failed += 1
            continue
        try:
            data = client.track(canco.deezer_id)
            preview = data.get("preview")
            if not preview:
                print(f"  [{label:5}] {pk:>5} SKIP no preview  {nom[:40]}")
                failed += 1
                continue
            mp3 = CLIPS / f"{pk}.mp3"
            _download(preview, mp3)
            _to_wav(mp3, wav)
            mp3.unlink()
            ok += 1
            print(f"  [{label:5}] {pk:>5} OK  {nom[:40]}")
        except Exception as exc:
            print(f"  [{label:5}] {pk:>5} FAIL {exc!r}  {nom[:40]}")
            failed += 1
    print(f"\n{ok} OK, {failed} failed, {len(rows)} total.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
