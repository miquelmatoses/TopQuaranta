"""Run MusicNN on all clips, extract 'voice' and 'vocals' tag probabilities."""

import os
import sys
import time

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
# Suppress TF startup chatter
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from musicnn.extractor import extractor

HERE = Path(__file__).resolve().parent.parent
CLIPS = HERE / "clips"
MANIFEST = HERE / "manifest.tsv"

rows = MANIFEST.read_text().strip().split("\n")[1:]
results = []
print(f"Running MusicNN on {len(rows)} clips...", flush=True)

for row in rows:
    parts = row.split("\t")
    label, pk, nom, artista = parts[0], parts[1], parts[2], parts[3]
    idioma = parts[4] if len(parts) > 4 else ""
    wav = str(CLIPS / f"{pk}.wav")
    if not Path(wav).exists():
        continue
    start = time.time()
    try:
        result = extractor(wav, model="MTT_musicnn", input_overlap=1)
        taggram = result[0]
        tags = result[1] if len(result) > 1 else None
        # tags is a list of 50 labels; taggram is [time_segments, 50] probabilities
        import numpy as np

        mean_probs = np.mean(taggram, axis=0)
        tag2prob = dict(zip(tags, mean_probs))
        # Key tags: 'vocal', 'vocals', 'no vocal', 'male voice', 'female voice', 'instrumental'
        vocal_p = float(tag2prob.get("vocal", 0) + tag2prob.get("vocals", 0))
        no_vocal_p = float(tag2prob.get("no vocal", 0) + tag2prob.get("no vocals", 0))
        instrumental_p = float(tag2prob.get("instrumental", 0))
        male_p = float(tag2prob.get("male voice", 0) + tag2prob.get("male vocal", 0))
        female_p = float(
            tag2prob.get("female voice", 0) + tag2prob.get("female vocal", 0)
        )
        elapsed = time.time() - start
        results.append(
            (
                label,
                pk,
                nom[:30],
                artista[:25],
                vocal_p,
                no_vocal_p,
                instrumental_p,
                male_p,
                female_p,
                elapsed,
            )
        )
        print(
            f"  [{label:5}] {pk:>5} v={vocal_p:.3f} !v={no_vocal_p:.3f} inst={instrumental_p:.3f} m={male_p:.3f} f={female_p:.3f}  ({elapsed:.1f}s)  {nom[:30]} — {artista[:20]}",
            flush=True,
        )
    except Exception as exc:
        print(f"  [{label:5}] {pk:>5} FAILED: {exc}", flush=True)

print("\n━━ Summary ━━")
inst = [r for r in results if r[0] == "inst"]
vocal = [r for r in results if r[0] == "vocal"]
if inst:
    print(
        f"  Instrumental vocal_p range: {min(r[4] for r in inst):.3f} – {max(r[4] for r in inst):.3f}"
    )
if vocal:
    print(
        f"  Vocal        vocal_p range: {min(r[4] for r in vocal):.3f} – {max(r[4] for r in vocal):.3f}"
    )
if inst:
    print(
        f"  Instrumental instrumental_p range: {min(r[6] for r in inst):.3f} – {max(r[6] for r in inst):.3f}"
    )
if vocal:
    print(
        f"  Vocal        instrumental_p range: {min(r[6] for r in vocal):.3f} – {max(r[6] for r in vocal):.3f}"
    )
