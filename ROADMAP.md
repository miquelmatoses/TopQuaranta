# ROADMAP.md — TopQuaranta Implementation Phases

> Updated: 2026-04-10

---

## Phase 0 — New project skeleton `DONE`

**Goal:** clean foundation, connected to existing DB, running on dedicated user.

- [x] Create OS user `topquaranta` with home `/home/topquaranta/`
- [x] Create `/home/topquaranta/app/` project directory
- [x] `git init`, connect to GitHub repo, `.gitignore`
- [x] Create virtualenv, install Django 5.2 + Wagtail 7.0 + dependencies
- [x] `django-admin startproject topquaranta .`
- [x] Create settings split: `base.py`, `local.py`, `production.py`
- [x] Configure `DATABASE_URL` pointing to existing `topquaranta` DB
- [x] Create apps: `music/`, `ingesta/`, `ranking/`, `distribucio/`, `legacy/`
- [x] Create `.env` + `.env.example` (only the new keys)
- [x] Set up `pytest.ini`, empty `conftest.py`, `requirements-dev.txt`
- [x] Run `python manage.py migrate` (Django system tables only)

**Go/no-go:** all passed.

---

## Phase 1 — Data migration from legacy `DONE`

**Goal:** import existing artists and tracks into new clean models.

- [x] Create `legacy/models.py` with unmanaged models (`LegacyArtista`, `LegacyCanco`)
- [x] Create `music/models.py` (`Territori` M2M, `Artista`, `Album`, `Canco`) and migrate
- [x] Create `ranking/models.py` (`ConfiguracioGlobal`, `IngestaDiari`, `RankingSetmanal`) and migrate
- [x] Write `importar_legacy` management command
  - Territory mapping: `'Catalunya'→CAT`, `'País Valencià'→VAL`, `'Balears'/'Illes'→BAL`
  - Status mapping: `'go'→actiu=True, aprovat=True`
  - Deduplicate cançons (legacy PK `id_canco+territori` → single row)
  - Artist lookup via `artistes_ids[0]` (spotify_id), not `artista_basat` (display name)
  - `lastfm_nom = nom` as initial default
- [x] Run `importar_legacy`, verify counts
- [x] Write `test_importar_legacy.py` (12 tests)

**Results:**
- Artistes: 2,273 (legacy `status='go'`)
- Albums: 4,250
- Cançons: 10,351 (deduplicated from 11,555 legacy rows)
- Skipped: 1,146 (no matching artist), 58 deduplicated
- Legacy tables untouched

---

## Phase 2 — Last.fm data collection `IN PROGRESS`

**Goal:** ingest raw data. No formula yet — just capture everything.

- [x] Obtain Last.fm API key
- [x] Add `LASTFM_API_KEY` + `LASTFM_API_SECRET` to `.env`
- [x] Implement `ingesta/clients/lastfm.py::get_track_info()`
- [ ] Write `test_lastfm_client.py` (mocked HTTP) ← **next**
- [x] Implement `ingestar_senyal` management command
- [x] Run `ingestar_senyal --dry-run --limit 50`, inspect output
- [ ] Fix `lastfm_nom` mismatches (manual or heuristic)
- [ ] Run daily ingestion for 7 consecutive days
- [ ] Set up cron: `ingestar_senyal` daily at 06:00

**Current state:**
- 808 eligible tracks (released within last 12 months)
- Test run (10 tracks): 9 success, 1 track-not-found
- Idempotency verified (re-run skips already-ingested)

**Go/no-go (pending):**
- ≥ 80% of active tracks have successful Last.fm data after 5 days
- Error rate < 20%
- `IngestaDiari` rows show non-zero `playcount` and `listeners`
- `score_entrada` is NULL everywhere (correct — formula not defined yet)

---

## Phase 3 — Signal formula definition

**Goal:** look at real data and decide how to normalize.

- [ ] Write one-off analysis script → print distribution stats
- [ ] Discuss formula in conversation (not in code)
- [ ] Implement formula in `ranking/senyal.py::calcular_score_entrada()`
- [ ] Implement `actualitzar_score_entrada` command and run backfill
- [ ] Verify: `score_entrada` not NULL for ≥ 95% of rows, distribution 0–100

---

## Phase 4 — Ranking algorithm adaptation

**Goal:** run the existing algorithm with the new signal.

- [ ] Extract SQL from `vw_top40_weekly_cat` PostgreSQL view
- [ ] Port to `ranking/algorisme.py` (parameterized territory, new table/column names)
- [ ] Write `test_algorisme.py` (fixture-based, known expected output)
- [ ] Implement `calcular_ranking` management command
- [ ] Run ranking, manually validate cultural plausibility
- [ ] Small coefficient tweaks only if distribution looks wrong

**Go/no-go:**
- Rankings for CAT, VAL, BAL without SQL errors
- Each territory ≥ 20 entries
- Results pass manual sense-check
- Runs in < 30 seconds

---

## Phase 5 — Distribution (Telegram + images)

**Goal:** restore weekly image publication.

- [ ] Audit legacy `utils/imagens.py` (41KB) — extract color palettes, layout logic
- [ ] Rebuild `distribucio/image_generator.py` (Pillow)
- [ ] Audit legacy Telegram bot code
- [ ] Rebuild `distribucio/telegram_bot.py`
- [ ] Implement `distribuir_ranking` command
- [ ] Test with `--dry-run` before sending to real channel

**Go/no-go:**
- `--dry-run` generates correct image for all territories
- Real Telegram send works

---

## Phase 6 — Artist discovery + CMS migration

**Goal:** automate discovery, migrate CMS to new models.

- [ ] Audit `scripts/update_from_viasona.py` → rebuild in `ingesta/clients/viasona.py`
- [ ] Implement collaborator detection in `ingesta/pipeline.py`
- [ ] Implement `descobrir_artistes` command
- [ ] Add Wagtail approval queue admin
- [ ] Migrate CMS pages to read from new models
- [ ] Implement `ingestar_metadata` command (Spotify, single credential pair)

**Go/no-go:**
- Discovery runs without crash
- New candidates appear in Wagtail admin
- Website displays data from new models
- Full pipeline: discovery → approval → metadata → signal → ranking → distribution

---

## Phase 7 — Legacy cleanup

**Goal:** remove legacy tables and views, clean up.

- [ ] Verify all functions work from new pipeline for ≥ 4 weeks
- [ ] Drop legacy SQL views (`vw_top40_*`, etc.)
- [ ] Drop legacy tables — **only after backup confirmed**
- [ ] Remove `legacy/` app from project
- [ ] Remove old cron jobs
- [ ] Archive `/root/TopQuaranta/` directory
- [ ] Full test suite passes, coverage ≥ 70%

**This phase requires explicit approval before each destructive step.**
