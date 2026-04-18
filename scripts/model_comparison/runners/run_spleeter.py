"""Run Spleeter 2stems on all clips, compute vocal/accompaniment energy ratio."""

import os
import sys
import time

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
from pathlib import Path

import numpy as np
from spleeter.audio.adapter import AudioAdapter
from spleeter.separator import Separator

HERE = Path(__file__).resolve().parent.parent
CLIPS = HERE / "clips"
MANIFEST = HERE / "manifest.tsv"

print("Loading Spleeter 2stems...", flush=True)
sep = Separator("spleeter:2stems")
audio = AudioAdapter.default()

rows = MANIFEST.read_text().strip().split("\n")[1:]
results = []
for row in rows:
    label, pk, nom, artista, mp3, wav = row.split("\t")
    if not Path(wav).exists():
        continue
    start = time.time()
    waveform, sr = audio.load(wav, sample_rate=44100)
    preds = sep.separate(waveform)
    elapsed = time.time() - start
    voc_rms = float(np.sqrt(np.mean(preds["vocals"] ** 2)))
    acc_rms = float(np.sqrt(np.mean(preds["accompaniment"] ** 2)))
    vratio = voc_rms / (voc_rms + acc_rms) if (voc_rms + acc_rms) > 0 else 0.0
    results.append((label, pk, nom[:30], artista[:25], vratio, elapsed))
    print(
        f"  [{label:5}] {pk:>5} vocal={voc_rms:.3f} accomp={acc_rms:.3f} vratio={vratio:.3f}  ({elapsed:.0f}s)  {nom[:30]} — {artista[:20]}",
        flush=True,
    )

print("\n━━ Summary ━━")
inst = [r for r in results if r[0] == "inst"]
vocal = [r for r in results if r[0] == "vocal"]
if inst:
    print(
        f"  Instrumental vratio range: {min(r[4] for r in inst):.3f} – {max(r[4] for r in inst):.3f}"
    )
if vocal:
    print(
        f"  Vocal        vratio range: {min(r[4] for r in vocal):.3f} – {max(r[4] for r in vocal):.3f}"
    )
