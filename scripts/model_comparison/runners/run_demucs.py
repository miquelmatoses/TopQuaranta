"""Run Demucs htdemucs on all clips, compute vocal ratio."""

import sys
import time
from pathlib import Path

import torch
import torchaudio
from demucs.apply import apply_model
from demucs.pretrained import get_model

HERE = Path(__file__).resolve().parent.parent
CLIPS = HERE / "clips"
MANIFEST = HERE / "manifest.tsv"

print("Loading htdemucs...")
model = get_model("htdemucs")
model.eval()
SOURCES = model.sources  # drums, bass, other, vocals

rows = MANIFEST.read_text().strip().split("\n")[1:]
results = []
for row in rows:
    parts = row.split("\t")
    label, pk, nom, artista = parts[0], parts[1], parts[2], parts[3]
    idioma = parts[4] if len(parts) > 4 else ""
    wav_path = CLIPS / f"{pk}.wav"
    if not wav_path.exists():
        continue
    wf, sr = torchaudio.load(str(wav_path))
    if wf.shape[0] == 1:
        wf = torch.cat([wf, wf], dim=0)
    wf = wf.unsqueeze(0)
    start = time.time()
    with torch.no_grad():
        sources = apply_model(model, wf, split=True, progress=False)
    elapsed = time.time() - start
    # RMS of each source
    rms = {
        name: sources[0, i].pow(2).mean().sqrt().item()
        for i, name in enumerate(SOURCES)
    }
    total = sum(rms.values())
    vocal_ratio = rms["vocals"] / total if total else 0.0
    results.append((label, pk, nom[:30], artista[:25], vocal_ratio, elapsed))
    print(
        f"  [{label:5}] {pk:>5} v={rms['vocals']:.3f} d={rms['drums']:.3f} b={rms['bass']:.3f} o={rms['other']:.3f} vratio={vocal_ratio:.3f} ({elapsed:.0f}s)  {nom[:30]} — {artista[:20]}",
        flush=True,
    )

print("\n━━ Summary ━━")
print(
    f"  Instrumental vocal_ratio range: {min(r[4] for r in results if r[0]=='inst'):.3f} – {max(r[4] for r in results if r[0]=='inst'):.3f}"
)
print(
    f"  Vocal        vocal_ratio range: {min(r[4] for r in results if r[0]=='vocal'):.3f} – {max(r[4] for r in results if r[0]=='vocal'):.3f}"
)
