"""
Run SpeechBrain VoxLingua107 ECAPA-TDNN LID on all clips.

Model: speechbrain/lang-id-voxlingua107-ecapa (107 languages, Catalan included).
Trained on speech from YouTube — untested on singing officially; treated here
as a second-opinion to Whisper.
"""

import sys
import time
from pathlib import Path

import torch
import torchaudio
from speechbrain.inference.classifiers import EncoderClassifier

HERE = Path(__file__).resolve().parent.parent
CLIPS = HERE / "clips"
MANIFEST = HERE / "manifest.tsv"
CACHE_DIR = Path.home() / ".cache" / "speechbrain-voxlingua"

print("Loading VoxLingua107 ECAPA-TDNN...", flush=True)
clf = EncoderClassifier.from_hparams(
    source="speechbrain/lang-id-voxlingua107-ecapa",
    savedir=str(CACHE_DIR),
)

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
        signal, sr = torchaudio.load(str(wav))
        if sr != 16000:
            signal = torchaudio.functional.resample(signal, sr, 16000)
        # Mono + 1D
        if signal.dim() == 2 and signal.shape[0] > 1:
            signal = signal.mean(dim=0, keepdim=True)
        out = clf.classify_batch(signal)
        # out = (scores_per_class, index, label_prob, label_name)
        # label_name like "ca: Catalan"
        predicted_raw = out[3][0]
        predicted = predicted_raw.split(":")[0].strip()
        label_prob = float(out[1].exp().item())
        # Score distribution
        scores = out[0][0]  # log probs / logits
        probs = scores.exp()
        probs = probs / probs.sum()
        # Top-3
        topk = torch.topk(probs, 3)
        # Map indices to language codes via the classifier label encoder
        lab2idx = clf.hparams.label_encoder.lab2ind
        idx2lab = {v: k for k, v in lab2idx.items()}
        top3 = [
            (idx2lab[int(i)].split(":")[0].strip(), float(p))
            for p, i in zip(topk.values, topk.indices)
        ]
        top3_str = " ".join(f"{k}={v:.2f}" for k, v in top3)
        p_ca = (
            float(probs[lab2idx.get("ca: Catalan", -1)])
            if "ca: Catalan" in lab2idx
            else 0.0
        )
        p_es = (
            float(probs[lab2idx.get("es: Spanish", -1)])
            if "es: Spanish" in lab2idx
            else 0.0
        )
        elapsed = time.time() - start
        correct = (predicted == idioma) if idioma else None
        mark = "✓" if correct else ("✗" if correct is False else "—")
        results.append(
            (
                label,
                pk,
                idioma,
                predicted,
                label_prob,
                p_ca,
                p_es,
                elapsed,
                nom,
                artista,
            )
        )
        print(
            f"  [{label:5}|{idioma or '--':3}] {pk:>14} {mark} pred={predicted} p={label_prob:.2f}  {top3_str}  ({elapsed:.1f}s)  {nom[:30]} — {artista[:20]}",
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

from collections import Counter

by_true = Counter(r[2] for r in tagged)
print(f"  Ground-truth breakdown: {dict(by_true)}")
wrong = [r for r in tagged if r[3] != r[2]]
if wrong:
    print(f"\n  Errors ({len(wrong)}):")
    for r in wrong:
        label, pk, idioma, predicted, prob, p_ca, p_es, elapsed, nom, artista = r
        print(
            f"    {idioma}→{predicted} (p={prob:.2f}, p_ca={p_ca:.2f}, p_es={p_es:.2f})  {nom[:40]} — {artista[:25]}"
        )

ca_clips = [r for r in tagged if r[2] == "ca"]
if ca_clips:
    print(f"\n  Catalan clips — p(ca) vs p(es):")
    for r in ca_clips:
        label, pk, idioma, predicted, prob, p_ca, p_es, elapsed, nom, artista = r
        print(
            f"    p_ca={p_ca:.2f} p_es={p_es:.2f} Δ={p_ca-p_es:+.2f}  {nom[:40]} — {artista[:20]}"
        )
