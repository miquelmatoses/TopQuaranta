# Model comparison results

## Project framing (important!)

TopQuaranta's goal is a catalogue of **Catalan-language music**. The filter is
**binary**: `ca` vs everything else (other languages, instrumentals,
ambiguous). We don't care what Whisper hallucinates for an instrumental as
long as that hallucination isn't `ca`. So the metric that matters is:

- **Precision(ca) — of everything the classifier accepts as `ca`, how much
  really is `ca`?** This must approach 100% or the catalogue gets polluted.
- **Recall(ca)** — of true Catalan tracks, how many pass the filter? Lower
  recall just means staff review rescues more, which is fine.

Everything below — vocal/instrumental detection, gender tagging — is
secondary and was explored for its own sake.

---

# Language Identification (LID) — 48 clips

## Ground truth

48 clips = 23 Catalan vocals + 5 Spanish + 5 English + 2 French + 2 Italian +
1 Portuguese + 10 Patinet instrumentals (label `ca=—`, must not get
classified as `ca`).

Catalan clips span: pop (Remei, Borrissol, Wildside), folk (Maria del Mar
Bonet), rock (Sopa de Cabra live, Germans Tanner), hardcore (Wildside, SX3),
cantautor (David Torné, Andreu Valor), female-lead (Clara Bonfill, Laia dels
Vents, Martina Burón), prog live (Companyia Elèctrica Dharma), feat. tracks
(Jonatan Penalba + Pepe Moreno).

Foreign clips are Deezer search hits by famous single-language artists
(Rosalía, Bad Bunny, C. Tangana, Rozalén, Ed Sheeran, Billie Eilish, Taylor
Swift, The Weeknd, Adele, Stromae, Angèle, Måneskin, Pausini, Caetano Veloso).

## Whisper large-v3 (faster-whisper, CPU int8) — PRIMARY MODEL

`detect_language()` on the raw 30 s clip. No source separation.

**Binary confusion matrix (ca vs no-ca, 48 clips) — after user-verified
ground-truth correction:**

|  | **Predicted ca** | **Predicted no-ca** |
|---|---:|---:|
| **Is ca (21)** | 17 (TP) | 4 (FN) |
| **Not ca (27)** | **0 (FP)** | 27 (TN) |

**Precision(ca) = 17/17 = 100 %**
**Recall(ca)    = 17/21 = 81.0 %**
**Specificity   = 27/27 = 100 %**

Staff verified the 6 clips Whisper flagged as non-Catalan:
- **2 turned out to be OUR catalogue errors**: `In The Rain` (Martina Burón,
  pk=7925) is actually English; `Visions Tàctils` (Marc Parrot, pk=721) is
  actually instrumental. Both were `verificada=True` with `idioma=ca` in
  our DB — Whisper correctly flagged them as non-Catalan. **Recommend
  rebutjar(motiu="no_catala")** for both.
- **3 are genuine Whisper false negatives**: Tarquim, Batre de Pepe Moreno
  (both Jonatan Penalba), Tape - Remix (Adrien Broadway). Two of three are
  the same artist — Penalba's vocal timbre may be systematically
  misclassified as Spanish. Demucs-vocals preprocessing is a candidate
  fix for a follow-up iteration.
- **1 inconclusive**: Jofre Bardagí *Ja Tens l'Amor* — Deezer preview
  broken, staff can't re-verify.

Ground-truth corrections applied to `manifest.tsv`: In The Rain → `en`;
Visions Tàctils → `inst`.

### The 6 Catalan false negatives (by what Whisper saw)

| Track | Predicted | p(ca) | p(predicted) | Hypothesis |
|---|---|---:|---:|---|
| Jofre Bardagí — *Ja Tens l'Amor* | es | 0.15 | 0.71 | Quiet acoustic, low vocal energy, ca/es phoneme drift |
| Jonatan Penalba — *Batre de Pepe Moreno* (feat.) | es | 0.07 | 0.83 | Feat. verse may actually be Spanish |
| Martina Burón — *In The Rain* | en | 0.00 | 0.81 | **English title — likely bilingual/actually English lyric.** Recommend staff re-verification. |
| Marc Parrot — *Visions Tàctils* | en | 0.00 | 0.74 | Marc Parrot has bilingual catalogue; this specific track may be English. Recommend re-verification. |
| Jonatan Penalba — *Tarquim* | es | 0.04 | 0.72 | Similar to Batre pattern |
| Adrien Broadway — *Tape - Remix* | es | 0.02 | 0.44 | English title, Whisper also sees Italian (0.23). Recommend re-verification. |

Three of the six (*In The Rain*, *Visions Tàctils*, *Tape - Remix*) have
English titles and very low `p(ca)` — plausibly **genuine label errors in
our DB**, not model errors. If true, effective recall on correct labels is
86–90 %.

### The 25 non-Catalan clips — maximum p(ca) observed

All 25 stay safely below any reasonable threshold:

| Clip group | max p(ca) observed | predicted language at max |
|---|---:|---|
| 10 Patinet instrumentals | ≤ 0.05 | always `en` (Whisper default hallucination) |
| 5 Spanish (Rosalía, Bad Bunny, C. Tangana, Manuel Carrasco, Rozalén) | 0.01 | always `es` |
| 5 English | ≤ 0.02 | always `en` |
| 2 French (Stromae, Angèle) | < 0.01 | always `fr` |
| 2 Italian (Måneskin, Pausini) | < 0.01 | always `it` |
| 1 Portuguese (Caetano) | < 0.01 | `pt` |

### Threshold calibration

Whisper's natural top-1 rule (`predicted == "ca"`) gives precision 100 % and
recall 74 % on this set. Relaxing to `p(ca) ≥ 0.10` would recover *Ja Tens
l'Amor* (+1 TP) without introducing any FP. `p(ca) ≥ 0.05` would also
recover *Batre de Pepe Moreno*. Below that, risk of FPs rises.

### Recommended pipeline

```
Deezer 30s preview → WAV 16 kHz mono → faster-whisper large-v3 .detect_language()

if predicted_language == "ca":            accept (auto)
elif p(ca) >= 0.10 and p(ca) - p(es) >= 0.05:  accept + staff review
else:                                     reject (but staff can override)
```

- Primary cost: ~27 s/clip on CPU (Hetzner CX22). 8 000 tracks = ~60 h one-
  shot, or bounded via nightly cron of a few hundred new tracks per day.
- Model storage: 1.5 GB for large-v3 int8 (`~/.cache/huggingface`).
- Could move to `large-v3-turbo` (distilled) if speed becomes a problem —
  community benchmarks suggest 2–3× faster with marginal LID degradation.

### Honest caveats

- 48 clips is small. Foreign-language sample is especially small (5 es, 5 en,
  2 fr, 2 it, 1 pt). Fine for a go/no-go decision; not fine for a formal
  benchmark.
- The 6 false negatives might hide label errors in our catalogue. Staff
  should listen to *In The Rain*, *Visions Tàctils*, *Tape - Remix* to
  confirm they really are in Catalan.
- We have not tested the **hardest adversarial case**: Catalan songs with a
  long Spanish/English featured verse that dominates the 30 s preview. If
  such tracks exist, they'd be Catalan by album attribution but sound
  foreign to Whisper.
- Untested: Demucs-vocals preprocessing. Community claim is it helps on
  mixed mastering; we saw 100 % precision without it, so there's no
  motivation to add complexity.

## SpeechBrain VoxLingua107 ECAPA-TDNN — SECOND-OPINION, rejected

Ran the same 48 clips through `speechbrain/lang-id-voxlingua107-ecapa` as a
sanity check against Whisper. Results disqualify it for our pipeline:

- **Multi-class accuracy: 14/38 = 36.8 %** (vs Whisper 84.2 %).
- **Two false positives on `ca`** — unacceptable:
  - C. Tangana *Tú Me Dejaste De Querer* → predicted ca (0.44), p_es=0.13
  - Rozalén *La Puerta Violeta* → predicted ca (0.44), p_es=0.15
- Wild hallucinations on Catalan clips (predicted `jw`, `my`, `ar`, `la`,
  `cy`, `zh`, `sco`, `yi`, `ba`, `eu`) — consistent with the known issue
  that VoxLingua is trained on YouTube speech, not singing, and degrades
  badly on music.
- Only 8 of 23 Catalan clips got `p(ca) ≥ 0.5` (vs 17 for Whisper).

Keeping the runner in the repo for future reference — it proves negative
results are real, not an install problem.

---

# Vocal / instrumental detection — 19 clips (legacy, superseded)

**Superseded by the simpler LID framing above.** If Whisper rejects an
instrumental as non-Catalan, we don't need a separate instrumental filter.

Kept for reference — the MusicNN `male voice` / `female voice` tags remain
potentially useful for a future "% female voice" metric.

| Model | Instr. vocal_p max | Vocal vocal_p min | Gap | Speed/clip | Verdict |
|---|---:|---:|---:|---:|---|
| **Silero VAD** | 0.00 (47 clips eval) | 0.10 (51% below) | — | 0.5s | ❌ Speech-only; structurally wrong for singing. Reverted 2026-04-18. |
| **inaSpeechSegmenter** | "music" 100% | "music" 100% | 0 | 3.0s | ❌ Distinguishes podcast-vs-music, not instr-vs-vocal in music. |
| **Spleeter (2stems)** | 0.366 | 0.242 | **−0.124** | 13s | ⚠ Overlap zone. 1 false positive, 1 borderline. Discarded. |
| **Demucs (htdemucs)** | 0.161 | 0.178 | **+0.017** | 55s | ✅ 100% separation, tight gap. |
| **MusicNN (MTT_musicnn)** | 0.086 | 0.114 | **+0.028** | 4s | ✅ 100% separation, widest gap. |

Full per-clip numbers in git history at
`scripts/model_comparison/resultats.md` commit `9c83908`.

---

# Recommendation for TopQuaranta

**Integrate faster-whisper large-v3 LID** as a new staff signal on `Canco`:

1. Schema: `Canco.whisper_lang` (CharField(max_length=3, blank=True)) +
   `Canco.whisper_p` (FloatField(null=True)) + `Canco.whisper_processat_at`.
2. Management command `analitzar_whisper` — batched over
   `Canco.objects.filter(whisper_processat_at__isnull=True)`, nightly cron.
3. Staff triage badge on `/staff/cancons/`: red flag if
   `whisper_lang != "ca"` and staff hasn't yet reviewed. Faster false-
   negative cleanup (*Ja Tens l'Amor*-type cases).
4. ML feature (after backfill): `whisper_p_ca` as an extra input to the RF
   classifier — no extra ground-truth labelling needed.
5. No hard rejection — staff verification remains the source of truth. This
   is a **signal**, not a gate.

**Do NOT integrate MusicNN instrumental detection** as a primary filter —
LID subsumes it. MusicNN may come back later as a source for `male_voice` /
`female_voice` probabilities when we need the % female metric.
