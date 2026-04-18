# Model comparison harness

Standalone evaluation bench for candidate ML audio models **before** integrating
them into the project. Lesson from the Silero VAD experiment (Sessió 15, fully
reverted): **never integrate a model before validating it against labelled
ground-truth clips from our own catalogue.**

## Contract

A "runner" is a script under `runners/run_<model>.py` that:

1. Reads `manifest.tsv` (tab-separated: `label, pk, nom, artista, mp3, wav`).
2. For each row, runs the candidate model on `clips/<pk>.wav` and extracts a
   single **vocal probability** (or the natural equivalent for the model).
3. Prints one line per clip with the probability and any auxiliary tags.
4. At the end, prints **min/max vocal_p per label group** so we can read off
   the separation gap.

Each runner owns its own venv (deps may conflict — e.g. TF 2.x for Spleeter,
PyTorch for Demucs). Installation notes go in `runners/<model>.md`.

## Ground truth

Current manifest (19 clips):

- **`inst` (10):** Lluís Paloma a.k.a. *Patinet* — documented instrumental
  project. High confidence these have no vocals.
- **`vocal` (9):** staff-verified Catalan vocal tracks spanning pop, rock,
  folk, hardcore, female-led, male-led, live recordings.

The manifest is a git-tracked TSV. Add a new row whenever you encounter a
case that trips a model in production.

## Clips directory

`clips/*.wav` (16 kHz mono) is **git-ignored** for repo size. To regenerate:

```bash
python scripts/model_comparison/fetch_clips.py
```

The fetcher reads `manifest.tsv`, looks up each Canco by pk, downloads its
Deezer preview (`canco.deezer_preview_url`), converts to 16 kHz mono WAV
with ffmpeg. Previews are signed URLs with ~hours TTL, so the fetcher
refreshes the URL via Deezer's `/track/{id}` endpoint when it finds an
expired 403.

## Running a model

```bash
cd /home/topquaranta/app
source scripts/model_comparison/runners/<model>_venv/bin/activate
python scripts/model_comparison/runners/run_<model>.py
```

Output goes to stdout. Redirect to `runners/<model>.log` if you want to save
it.

## Evaluation metric

For a vocal/instrumental classifier, the only metric that matters is:

```
gap = min(vocal_p for clips labelled "vocal")
    − max(vocal_p for clips labelled "inst")
```

- **gap > 0** → there exists a threshold that classifies all ground-truth
  clips correctly. The wider, the more robust.
- **gap ≤ 0** → overlap zone. Some threshold will misclassify at least one
  clip. Model is suspect for production use.

See `resultats.md` for the comparative table.

## Adding a new candidate model

1. Create `runners/<model>_venv`, install the model's deps inside it.
2. Copy `runners/run_musicnn.py` as a template; replace the inference call.
3. Run against the current manifest. Append your row to `resultats.md` with
   min/max ranges, gap, speed per clip, and a one-line verdict.
4. If the model passes, propose integration (schema change, management
   command, cron, ML feature) in a follow-up session.

**The harness is a gatekeeper, not a fast-lane.** A model passing here is a
necessary but not sufficient condition for integration.
