# Runner dependencies

Each runner owns a separate venv because model dependencies conflict.
All venvs are git-ignored — recreate with the commands below.

## Demucs

```bash
cd scripts/model_comparison/runners
python3 -m venv demucs_venv
source demucs_venv/bin/activate
pip install --extra-index-url https://download.pytorch.org/whl/cpu \
    torch torchaudio demucs
```

First run downloads `htdemucs` (~80 MB) to `~/.cache/torch/hub`.

## Spleeter

```bash
python3 -m venv spleeter_venv
source spleeter_venv/bin/activate
pip install spleeter
```

Needs TF 2.x. First run downloads `2stems` (~90 MB) to `pretrained_models/`.

## inaSpeechSegmenter

```bash
python3 -m venv ina_venv
source ina_venv/bin/activate
pip install inaSpeechSegmenter
```

Uses TF 2.x. Discarded for our use case (classifies all music as "music",
does not distinguish instr vs vocal). Kept here for reproducibility.

## MusicNN

```bash
python3 -m venv musicnn_venv
source musicnn_venv/bin/activate
pip install "tensorflow>=2.3,<2.16" "librosa>=0.10,<0.11" "numpy<1.24"
pip install --no-deps musicnn
```

`--no-deps` avoids pulling in the ancient `scipy==1.6.1` source build that
`musicnn`'s setup.py pins. Manual deps above satisfy runtime.

## Planned: Whisper LID

```bash
python3 -m venv whisper_venv
source whisper_venv/bin/activate
pip install --extra-index-url https://download.pytorch.org/whl/cpu \
    torch faster-whisper
```

Pipeline: Demucs → `vocals.wav` → `WhisperModel("large-v3").detect_language()`.
See `../resultats.md` for expected metric.
