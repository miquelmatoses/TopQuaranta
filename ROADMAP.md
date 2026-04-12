# ROADMAP.md — TopQuaranta Implementation Phases

> Updated: 2026-04-12 — emergency fix: reverted 6,002 Deezer-only cançons to verificada=False

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
  - Status mapping: `'go'→aprovat=True`
  - Deduplicate cançons (legacy PK `id_canco+territori` → single row)
  - Artist lookup via `artistes_ids[0]` (spotify_id), not `artista_basat` (display name)
  - `lastfm_nom = nom` as initial default
- [x] Run `importar_legacy`, verify counts
- [x] Write `test_importar_legacy.py` (12 tests)
- [x] Populate ISRC from legacy `spotify_tracks.external_ids` via `poblar_isrc` command
  - 749/10,351 cançons matched (legacy `spotify_tracks` only has 2,805 rows)
- [x] Refactor: removed `Artista.actiu` field (was derived state, not manual attribute)

**Results:**
- Artistes: 2,273 (legacy `status='go'`)
- Albums: 4,250
- Cançons: 10,351 (deduplicated from 11,555 legacy rows)
- ISRCs populated: 749 (from legacy `spotify_tracks`)
- Skipped: 1,146 (no matching artist), 58 deduplicated
- Legacy tables untouched

---

## Phase 2 — Last.fm data collection `IN PROGRESS`

**Goal:** ingest raw data. No formula yet — just capture everything.

- [x] Obtain Last.fm API key
- [x] Add `LASTFM_API_KEY` + `LASTFM_API_SECRET` to `.env`
- [x] Implement `ingesta/clients/lastfm.py::get_track_info()`
- [x] Write `test_lastfm_client.py` (4 tests: success, track_not_found, network_error, rate_limit_sleep)
- [x] Implement `ingestar_senyal` management command
- [x] Run `ingestar_senyal --dry-run --limit 50`, inspect output
- [x] Set up cron: `ingestar_senyal` daily at 06:00 (`/etc/cron.d/topquaranta`)
- [x] `ingestar_senyal` filters by `verificada=True` — safe from Deezer false positives
- [ ] Fix `lastfm_nom` mismatches (manual or heuristic) ← **next**
- [ ] Run daily ingestion for 7 consecutive days

**Current state (2026-04-12):**
- Emergency fix: 6,002 Deezer-only cançons (no `spotify_id`) reverted to `verificada=False`
  - Root cause: bulk verification on 2026-04-11 included non-Catalan false positives from Deezer
  - 57.4% error rate in daily cron triggered the fix
- Eligible tracks (verified, recent, approved): recalculated from 10,351 legacy-only verified
- `ingestar_senyal` only processes `verificada=True` cançons — Deezer tracks now excluded until manual review
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

## Phase 6 — Metadata pipeline, artist discovery + CMS migration

**Goal:** automate discovery, feed the ranking with verified new tracks.

### Deezer metadata pipeline `DONE`

- [x] Implement Deezer client: `ingesta/clients/deezer.py`
  - Public API, no authentication needed
  - `search_artist()`: normalized name matching (lowercase, strip accents)
  - `get_artist_albums()`: with date filter + pagination
  - `get_album_tracks()`: fetches full track endpoint for ISRC (100% coverage)
  - Rate limit 0.1s, retry 3x with backoff, never raises
- [x] Implement `ingestar_metadata` command using Deezer
  - Iterates `Artista.objects.filter(aprovat=True)`
  - Artist resolution: search by name → ISRC cross-validation → save `deezer_id`
  - If ISRC validation fails or no search match → `deezer_no_trobat=True`, skip
  - Creates Album + Canco with `deezer_id`, stores ISRC on every track
  - Flags: `--artista-id`, `--force`, `--dry-run`, `--limit`
  - New tracks always enter with `verificada=False`
  - Fix: IntegrityError on duplicate `deezer_id` now caught gracefully — logs warning, continues
- [x] Model changes (migrations 0003–0007):
  - Removed `Artista.actiu` (was derived state)
  - Added `deezer_id` (BigIntegerField) on Artista, Album, Canco
  - Added `deezer_no_trobat` (BooleanField) on Artista
  - Added `verificada` (BooleanField, default=False) on Canco
  - Data migration: 10,351 legacy cançons → `verificada=True`
- [x] Tests: 54 passing (15 Deezer client, 10 command, 12 legacy, 5 Spotify, 4 Last.fm, 5 parse, 3 misc)
- [x] Spotify client kept as fallback (`ingesta/clients/spotify.py`) — blocked by Premium requirement

### ISRC-based Deezer matching (2026-04-11) `DONE`

- [x] `matching_isrc_deezer` command: finds ISRC in legacy `spotify_tracks`, queries Deezer `/track/isrc:{isrc}`
  - Name verification: checks main artist + contributors to avoid false positives
  - Result: 208 matched, 5 not found, 713 had no ISRC in legacy
- [x] Bulk verification script: 5,993 Deezer-matched tracks → `verificada=True`
- [x] **Reverted (2026-04-12):** 6,002 Deezer-only cançons (`spotify_id` NULL or empty) set back to `verificada=False` — 57.4% cron error rate caused by non-Catalan false positives

### Location fields migration (2026-04-11) `DONE`

- [x] Added `localitat`, `comarca`, `provincia` to `Artista` model (migration 0008)
- [x] Copied values from legacy `artistes` table via `spotify_id` matching
  - 2,273 artists updated (localitat: 2,273, comarca: 2,273, provincia: 49)

### Production runs (2026-04-10 → 2026-04-11) `DONE`

- **ingestar_metadata complete:** 2,273 artists processed
  - 1,894 with `deezer_id` (83%) — name search + ISRC matching combined
  - 370 `deezer_no_trobat=True` (16%)
  - 10 pending (no Deezer match yet, not marked as not found)
- **matching_isrc_deezer:** 208 additional artists matched via legacy ISRC cross-check
- **Known false positives** (generic names matched to international artists):
  Aion (479 albums, metal), Animal (121), Aïsha (55), Atman (43), Apa (35),
  Arrap (32), Benitozz (30), Bizarre (17), Aradia (17), Amulet (16)
- **Containment match issues:** Abast→'La Abasto Reggae', Addenda→'addeN'

### Database state (2026-04-11)

| Table | Count | Details |
|---|---|---|
| `music_artista` | 2,273 | 1,894 with `deezer_id` (83%), 370 `deezer_no_trobat`, 10 pending |
| `music_album` | ~6,795 | 4,250 legacy + ~2,545 from Deezer |
| `music_canco` | 22,145 | 10,351 `verificada=True` (legacy only) + 11,794 `verificada=False` (Deezer tracks pending review) |
| Deezer tracks with ISRC | ~5,801 | 100% coverage on Deezer-sourced tracks |

### Safety gate: `verificada` field

- `ingestar_senyal` (daily cron) only processes `verificada=True` tracks
- New Deezer tracks enter with `verificada=False` — blocked from ranking
- Admin must review and approve before tracks enter the pipeline
- Prevents false positives (Aion metal, anime, etc.) from polluting rankings

### Track verification system (2026-04-12) `DONE`

- [x] `HistorialRevisio` model — records every approve/reject with motiu and snapshot (migration 0009)
- [x] Artista Deezer metadata: `deezer_nb_fan`, `deezer_nb_album`, `deezer_nom`, `deezer_nom_similitud`
- [x] `music/verificacio.py::crear_historial()` — snapshot helper called before delete/modify
- [x] Admin actions with intermediate confirmation page and required motiu
- [x] ML heuristic classifier `music/ml.py::pre_classificar()` — classes A/B/C
- [x] ML column in CancoAdmin with color and tooltip, MLClasseFilter
- [x] `HistorialRevisioAdmin` — read-only admin for review history
- [x] 50 initial decisions imported via `scripts/importar_decisions_inicials.py`

### Collaborator extraction from Deezer (2026-04-12) `DONE`

- [x] `deezer.get_artist_info()` — fetches nb_fan, nb_album for metadata
- [x] `deezer.get_album_tracks()` — now returns `contributors` list from full track endpoint
- [x] `ingestar_metadata._upsert_track()` — reads contributors, creates collaborator Artista if needed
- [x] `ingestar_metadata._resolve_deezer_id()` → populates `deezer_nb_fan`, `deezer_nb_album`, `deezer_nom`, `deezer_nom_similitud`

### Pending

- [ ] Audit `scripts/update_from_viasona.py` → rebuild in `ingesta/clients/viasona.py`
- [ ] Implement `descobrir_artistes` command
- [ ] Add Wagtail approval queue admin (artists: `aprovat=False`)
- [ ] Migrate CMS pages to read from new models
- [ ] Clean up false positive `deezer_id` matches (Aion, Animal, etc.) — manual review
- [ ] Populate `deezer_nb_fan`/`deezer_nb_album` for existing 1,894 artists with `deezer_id` (backfill)

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
