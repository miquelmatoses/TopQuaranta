"""Silero VAD client — voice activity detection over Deezer previews.

Given a track's preview_url, we:
  1. Download the 30-second MP3 clip.
  2. Convert to 16 kHz mono WAV via ffmpeg (Silero expects that).
  3. Run the Silero VAD model to find speech segments.
  4. Return the fraction of the clip classified as voice (0.0-1.0).

The model itself (~1 MB) is downloaded on first use by silero-vad's
`load_silero_vad()` and cached in `~/.cache/torch/hub/`. No network
needed on subsequent runs.

We deliberately do NOT run Silero in the web process — it loads torch
into memory (~500 MB) and is too heavy to be always resident. It runs
via `manage.py analitzar_silero` as a nightly cron.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Silero VAD expects 16 kHz mono 16-bit PCM WAV.
_SAMPLE_RATE = 16000

# Singleton: the model is expensive to load (~500 ms + 500 MB RAM for torch),
# so we cache it at module level. Set lazily in `_get_model()`.
_model = None
_get_speech_timestamps = None


def _get_model():
    """Lazy-load the Silero VAD model; cache at module level."""
    global _model, _get_speech_timestamps
    if _model is None:
        # Imports deferred so Django startup doesn't pay the torch cost.
        from silero_vad import get_speech_timestamps, load_silero_vad

        _model = load_silero_vad()
        _get_speech_timestamps = get_speech_timestamps
    return _model, _get_speech_timestamps


def _download_preview(url: str, dest: Path) -> bool:
    """Download the Deezer preview MP3 to `dest`. Returns True on success."""
    try:
        r = requests.get(url, timeout=15, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
        return dest.stat().st_size > 1024  # Guard against empty responses
    except requests.RequestException as exc:
        logger.warning("Silero: preview download failed for %s: %s", url, exc)
        return False


def _mp3_to_wav(mp3: Path, wav: Path) -> bool:
    """Transcode MP3 → 16 kHz mono WAV via ffmpeg. Returns True on success."""
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(mp3),
                "-ac",
                "1",
                "-ar",
                str(_SAMPLE_RATE),
                "-f",
                "wav",
                str(wav),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return wav.exists() and wav.stat().st_size > 1024
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        logger.warning("Silero: ffmpeg failed on %s: %s", mp3, exc)
        return False


def _voice_fraction(wav_path: Path) -> float | None:
    """Return the fraction of `wav_path` classified as voice by Silero.

    None on any processing error. On success: 0.0 means no voice detected
    anywhere (likely instrumental), 1.0 means voice throughout.
    """
    try:
        import torch
        import torchaudio

        model, get_speech_timestamps = _get_model()
        waveform, sr = torchaudio.load(str(wav_path))
        if sr != _SAMPLE_RATE:
            # Shouldn't happen because we force it in ffmpeg, but be defensive.
            waveform = torchaudio.transforms.Resample(sr, _SAMPLE_RATE)(waveform)
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        total_samples = waveform.shape[1]
        if total_samples == 0:
            return None
        segments = get_speech_timestamps(
            waveform.squeeze(0),
            model,
            sampling_rate=_SAMPLE_RATE,
            return_seconds=False,
        )
        voice_samples = sum(s["end"] - s["start"] for s in segments)
        return voice_samples / total_samples
    except Exception as exc:
        logger.warning("Silero: VAD inference failed on %s: %s", wav_path, exc)
        return None


def _refresh_preview_url(deezer_track_id: int) -> str | None:
    """Fetch a fresh preview URL from Deezer.

    Deezer signs preview URLs with an `hdnea=exp=…` token that expires in
    hours. The URL we stored at ingestion time is typically stale by the
    time the nightly Silero run picks the track up, so we re-fetch.
    """
    from ingesta.clients.deezer import API_BASE, _get

    data = _get(f"{API_BASE}/track/{deezer_track_id}")
    if data is None:
        return None
    return data.get("preview") or None


def analyze_preview(
    preview_url: str | None, deezer_track_id: int | None = None
) -> float | None:
    """Download + analyse a Deezer preview, return voice fraction.

    Returns None if:
      - The preview URL returns a non-audio / empty body and we can't
        refresh it via Deezer API.
      - ffmpeg cannot decode the MP3.
      - Silero inference fails.
    Caller should treat None as "analysis failed; leave silero_processat_at
    NULL so the track is retried on the next run".

    If `deezer_track_id` is provided, we first try the given URL; on
    failure (e.g. expired token), we refresh via Deezer API and retry.
    """
    with tempfile.TemporaryDirectory(prefix="silero-") as tmpdir:
        tmp = Path(tmpdir)
        mp3 = tmp / "preview.mp3"
        wav = tmp / "preview.wav"

        got = False
        if preview_url:
            got = _download_preview(preview_url, mp3)
        if not got and deezer_track_id:
            fresh = _refresh_preview_url(deezer_track_id)
            if fresh:
                got = _download_preview(fresh, mp3)
        if not got:
            return None
        if not _mp3_to_wav(mp3, wav):
            return None
        return _voice_fraction(wav)
