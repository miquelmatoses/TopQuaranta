"""
Run faster-whisper large-v3 LID on all clips.

For each clip: call `detect_language()` on the 30s clip (raw, no source
separation). Prints top-3 language probabilities + the `idioma` ground truth
from the manifest. Final summary: accuracy on clips with a known `idioma`.

Future variant: Demucs-vocals preprocessing. For now we want to see the
baseline without separation.
"""

import os
import sys
import time
from pathlib import Path

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from faster_whisper import WhisperModel

HERE = Path(__file__).resolve().parent.parent
CLIPS = HERE / "clips"
MANIFEST = HERE / "manifest.tsv"

print("Loading faster-whisper large-v3 (CPU, int8)...", flush=True)
model = WhisperModel("large-v3", device="cpu", compute_type="int8")

rows = MANIFEST.read_text().strip().split("\n")[1:]
results = []

for row in rows:
    parts = row.split("\t")
    label, pk, nom, artista = parts[0], parts[1], parts[2], parts[3]
    idioma = parts[4] if len(parts) > 4 else ""
    wav = CLIPS / f"{pk}.wav"
    if not wav.exists():
        continue

    start = time.time()
    try:
        # detect_language: load audio, run encoder, return (lang, prob, all_probs)
        # faster-whisper exposes it via the transcribe() call too, but we only
        # need LID — use the lower-level API.
        import faster_whisper.audio as fwa

        audio = fwa.decode_audio(str(wav), sampling_rate=16000)
        # Restrict to first 30s (previews are 30s anyway but just in case).
        audio = audio[: 16000 * 30]
        lang, prob, all_probs = model.detect_language(audio)
        # all_probs is List[Tuple[str, float]], convert to dict for easy lookup.
        if isinstance(all_probs, list):
            all_probs = dict(all_probs)
        elapsed = time.time() - start
        # Top-3
        top3 = sorted(all_probs.items(), key=lambda kv: -kv[1])[:3]
        top3_str = " ".join(f"{k}={v:.2f}" for k, v in top3)
        predicted = lang
        correct = (predicted == idioma) if idioma else None
        mark = "✓" if correct else ("✗" if correct is False else "—")
        results.append(
            (label, pk, idioma, predicted, prob, all_probs, elapsed, nom, artista)
        )
        print(
            f"  [{label:5}|{idioma or '--':3}] {pk:>14} {mark} pred={predicted} p={prob:.2f}  {top3_str}  ({elapsed:.1f}s)  {nom[:30]} — {artista[:20]}",
            flush=True,
        )
    except Exception as exc:
        print(f"  [{label:5}|{idioma or '--':3}] {pk:>14} FAILED: {exc}", flush=True)

print("\n━━ Summary ━━")
tagged = [r for r in results if r[2]]
correct = [r for r in tagged if r[3] == r[2]]
print(f"  Tagged clips: {len(tagged)}")
print(
    f"  Correct:      {len(correct)} / {len(tagged)} = {100*len(correct)/max(1,len(tagged)):.1f}%"
)
print()
# Confusion breakdown
from collections import Counter

by_true = Counter(r[2] for r in tagged)
print(f"  Ground-truth breakdown: {dict(by_true)}")
wrong = [r for r in tagged if r[3] != r[2]]
if wrong:
    print(f"\n  Errors ({len(wrong)}):")
    for r in wrong:
        label, pk, idioma, predicted, prob, all_probs, elapsed, nom, artista = r
        p_true = all_probs.get(idioma, 0.0)
        print(
            f"    {idioma}→{predicted} (p={prob:.2f}, p_true={p_true:.2f})  {nom[:40]} — {artista[:25]}"
        )

# Margin analysis for Catalan: p(ca) − p(es) on ca-tagged clips
ca_clips = [r for r in tagged if r[2] == "ca"]
if ca_clips:
    print(f"\n  Catalan clips — p(ca) vs p(es):")
    for r in ca_clips:
        label, pk, idioma, predicted, prob, all_probs, elapsed, nom, artista = r
        p_ca = all_probs.get("ca", 0.0)
        p_es = all_probs.get("es", 0.0)
        print(
            f"    p_ca={p_ca:.2f} p_es={p_es:.2f} Δ={p_ca-p_es:+.2f}  {nom[:40]} — {artista[:20]}"
        )
