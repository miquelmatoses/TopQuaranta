# Model comparison results

## Ground truth: 19 clips (10 instrumental Patinet + 9 staff-verified Catalan vocals)

| Model | Instr. vocal_p max | Vocal vocal_p min | Gap | Speed/clip | Verdict |
|---|---:|---:|---:|---:|---|
| **Silero VAD** | 0.00 (47 clips eval) | 0.10 (51% below) | — | 0.5s | ❌ Speech-only; structurally wrong for singing. Reverted 2026-04-18. |
| **inaSpeechSegmenter** | "music" 100% | "music" 100% | 0 | 3.0s | ❌ Distinguishes podcast-vs-music, not instr-vs-vocal in music. |
| **Spleeter (2stems)** | 0.366 | 0.242 | **−0.124** | 13s | ⚠ Overlap zone. 1 false positive, 1 borderline. Discarded. |
| **Demucs (htdemucs)** | 0.161 | 0.178 | **+0.017** | 55s | ✅ 100% separation, tight gap. Slow (7h for 8k tracks). |
| **MusicNN (MTT_musicnn)** | 0.086 | 0.114 | **+0.028** | 4s | ✅ 100% separation, widest gap. 13× faster than Demucs. |

## Raw data

### MusicNN per-clip (vocal_p tag = "vocal" + "vocals" mean probability over time segments)

```
Instrumental (Patinet, 10 clips):
  17723 v=0.019   1 de Maig
  17739 v=0.035   1 de Maig (Versió Ionic South)
  17703 v=0.013   450 Mulberry Street
  10338 v=0.013   A Flash In The Pan
  17751 v=0.023   All You Need Is Glub
  17769 v=0.086   A Merry Free For All      ← max
  17706 v=0.011   Antarctic Day
   9811 v=0.007   A Phoney Situation        ← min
  17725 v=0.008   Arribant a l'Illa
  17787 v=0.012   Astrosurfing

Vocal (staff-verified, 9 clips):
  19801 v=0.118   Va Com Va — Remei de Ca la Fresca
  20623 v=0.147   Murs d'Altaveus — Sobre Mi Gata
  13111 v=0.534   Sense Tu, No És el Mar — Clara Bonfill   ← max
  23438 v=0.358   Sota una Estrella — Sopa de Cabra
  23574 v=0.114   Ja Tens l'Amor — Jofre Bardagí           ← min
   9965 v=0.155   He Pecat — Borrissol
  16754 v=0.450   Batre de Pepe Moreno — Jonatan Penalba
  16791 v=0.516   Yoga els Dimecres — Jordi Maranges
  22028 v=0.251   Tota la Nit (Demo) — Wildside
```

Threshold `vocal_p ≥ 0.10` classifies 19/19 correctly on this set.

### MusicNN bonus tags: male/female voice

MusicNN also emits `male voice` and `female voice` probabilities. Reasonable
correlation with known gender on the ground-truth clips:

- Sopa de Cabra (male lead): m=0.358, f=0.078 ✓
- Clara Bonfill (female lead): m=0.121, f=0.442 ✓
- Jonatan Penalba (male lead): m=0.510, f=0.042 ✓
- Jordi Maranges (male lead): m=0.235, f=0.182 ✓
- Borrissol (mixed, male-dominant in this track): m=0.143, f=0.016 ✓

Potentially useful for a future "% female voice in the ranking" metric
**without any additional model** — free side channel from the same inference.

### Demucs per-clip (vocal_p = vocal stem RMS / total RMS)

```
Instrumental range: 0.098 – 0.161 (max: A Merry Free For All)
Vocal        range: 0.178 – 0.421 (min: Ja Tens l'Amor)
```

### Spleeter per-clip (2stems, vocal stem RMS ratio)

```
Instrumental range: 0.097 – 0.366 (max: A Merry Free For All)
Vocal        range: 0.242 – 0.481 (min: Ja Tens l'Amor)
```

Note: *A Merry Free For All* is the hardest instrumental for every model —
it's Patinet's most "band-like" arrangement with brass and percussion. Ja
Tens l'Amor is the most understated vocal — acoustic ballad, low voice in
the mix.

## Earlier evaluations (superseded)

### Silero VAD (reverted 2026-04-18)

Measured against 47 staff-verified Catalan vocal tracks (different set from
the current manifest, pre-dates this harness):

- 51% of vocal tracks scored **<10% voice probability** → false negatives.
- Sopa de Cabra live recordings (known vocal): 0–7%.
- Katarrama (hardcore with screaming): 1.7%.
- Aquarella "Aire Pur" (clear female vocal): 0%.

Silero is trained on speech (phone calls, podcasts). Singing phonemes are
stretched and pitched; speech VAD features collapse. Structural mismatch,
not a tuning issue.

Also discarded: **inaSpeechSegmenter** (INA France) — classifies all music
as "music", no instr/vocal distinction within music.

## Next candidate: song language identification (Whisper / VoxLingua107)

See `runners/run_whisper_lid.py` (TODO). Expected separation task: 9 Catalan
vocals vs ≥5 Spanish/English control clips. Target metric: `p(ca) ≥ 0.7`
with `p(ca) − p(es) ≥ 0.15`.
