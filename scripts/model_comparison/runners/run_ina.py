import os
import sys
import time

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
from pathlib import Path

from inaSpeechSegmenter import Segmenter

HERE = Path(__file__).resolve().parent.parent
CLIPS = HERE / "clips"
MANIFEST = HERE / "manifest.tsv"

print("Loading ina Segmenter...", flush=True)
seg = Segmenter(vad_engine="smn", detect_gender=False)  # smn = speech/music/noise

rows = MANIFEST.read_text().strip().split("\n")[1:]
results = []
for row in rows:
    label, pk, nom, artista, mp3, wav = row.split("\t")
    if not Path(wav).exists():
        continue
    start = time.time()
    segs = seg(wav)  # returns [(label, start, end), ...]
    elapsed = time.time() - start
    total_s = sum(e - s for _, s, e in segs)
    music_s = sum(e - s for lbl, s, e in segs if lbl == "music")
    speech_s = sum(e - s for lbl, s, e in segs if lbl == "speech")
    noise_s = sum(e - s for lbl, s, e in segs if lbl == "noise")
    noEnergy_s = sum(e - s for lbl, s, e in segs if lbl == "noEnergy")
    results.append(
        (
            label,
            pk,
            nom[:30],
            artista[:25],
            speech_s / total_s,
            music_s / total_s,
            elapsed,
        )
    )
    print(
        f"  [{label:5}] {pk:>5} music={music_s/total_s:.2f} speech={speech_s/total_s:.2f} noise={noise_s/total_s:.2f} noE={noEnergy_s/total_s:.2f}  ({elapsed:.1f}s)  {nom[:30]} — {artista[:20]}",
        flush=True,
    )

print("\n━━ Summary ━━")
inst = [r for r in results if r[0] == "inst"]
vocal = [r for r in results if r[0] == "vocal"]
if inst:
    print(
        f"  Instrumental speech_ratio range: {min(r[4] for r in inst):.2f} – {max(r[4] for r in inst):.2f}"
    )
if vocal:
    print(
        f"  Vocal        speech_ratio range: {min(r[4] for r in vocal):.2f} – {max(r[4] for r in vocal):.2f}"
    )
if inst:
    print(
        f"  Instrumental music_ratio range:  {min(r[5] for r in inst):.2f} – {max(r[5] for r in inst):.2f}"
    )
if vocal:
    print(
        f"  Vocal        music_ratio range:  {min(r[5] for r in vocal):.2f} – {max(r[5] for r in vocal):.2f}"
    )
