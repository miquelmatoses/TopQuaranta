# CLAUDE_PIPELINE.md — Ingest → Signal → Ranking

> Daily + hourly automation. All commands run as user `topquaranta` from
> `/etc/cron.d/topquaranta`, with `DJANGO_SETTINGS_MODULE=topquaranta.settings.production`.

---

## 1. Overview

```
     Deezer (hourly, obtenir_novetats)     Last.fm (daily, obtenir_senyal)
           │                                        │
           ▼                                        ▼
   new Canco (verificada=False)              SenyalDiari
           │                                        │
   staff review → verificada=True ──────────────────┤
                                                    ▼
                                          score_entrada (percent_rank)
                                                    │
                                                    ▼
                                   calcular_ranking (daily provisional,
                                                     Saturday official)
                                                    │
                                                    ▼
                                        RankingProvisional / RankingSetmanal
```

## 2. API clients (`ingesta/clients/`)

All clients import `DEEZER_RATE_LIMIT`, `LASTFM_RATE_LIMIT`, `MAX_API_RETRIES`
from `music/constants.py`. Never raise — return `None` on any failure.

### `deezer.py` — primary metadata source
- Public API, no auth. Base: `https://api.deezer.com`.
- Rate limit 1.0 s, retry 3× with exponential backoff.
- Detects error code 4 ("Quota limit exceeded"), sets a session-scoped flag
  that stops further calls until next day (`quota_exhausted()`).
- Functions: `search_artist`, `get_artist_info`, `get_artist_albums`,
  `get_album_tracks`. Returns dict or `None`.

### `lastfm.py` — daily signal
- Endpoint: `track.getInfo?autocorrect=1`.
- Rate 0.2 s, retry 3×.
- On error 6 ("Track not found"), automatically retries once with the track
  name normalized: strips `(feat. X)`, `(Acoustic Version)`, `- Live`, `- Remix`,
  etc., and converts Unicode quotes to ASCII. Recovers ~10–15% of errors.

### `spotify.py` — fallback (unused)
- Blocked since 2024 (requires Premium). Kept for reference; no command imports it.

### `viasona.py` — stub (TODO)
- Placeholder. The Viasona scraper was on the Phase 6 wishlist but is not
  implemented. Safe to remove when the project decides against it.

## 3. Management commands

### Rules (all commands)
- `self.stdout.write()`, never `print()`.
- `raise CommandError(...)`, never `sys.exit()`.
- All DB writes inside `transaction.atomic()`.
- Idempotent where possible.
- Final line: counts of processed / success / errors.

### 3.1 `obtenir_senyal` — daily 06:00
```bash
python manage.py obtenir_senyal [--data YYYY-MM-DD] [--limit N] [--dry-run]
```
Selects `verificada=True AND activa=True AND artista.aprovat=True AND
data_llancament ≥ today - DIES_CADUCITAT` tracks, calls Last.fm per track,
writes `SenyalDiari`. At end, calls `ranking.senyal.normalize_score_entrada`
to compute percent_rank over the day. Skips tracks already ingested for that
date (idempotent).

### 3.2 `actualitzar_score_entrada` — daily 06:30 (safety net)
```bash
python manage.py actualitzar_score_entrada [--data YYYY-MM-DD] [--tots]
```
Backfills `score_entrada` for rows where it is NULL or where yesterday was
missed.

### 3.3 `calcular_ranking`
```bash
python manage.py calcular_ranking [--setmana YYYY-MM-DD] [--territori CODE]
                                   [--dry-run] [--provisional]
```
- Without `--provisional`: writes `RankingSetmanal`. Run Saturday 08:00.
  Territories processed: `TERRITORIS_FIXOS = {CAT, VAL, BAL}` + aggregates
  `{ALT, PPCC}`. Each territory is `delete + bulk_create` inside a transaction
  (prevents stale entries from previous runs).
- With `--provisional`: writes `RankingProvisional`. Run daily 07:00. Includes
  all eligible territories (fixed + aggregates + optional if they cross the
  `min_cancons_ranking_propi` threshold).
- Aggregates (ALT, PPCC) must run last — they read the just-computed individual
  rankings in memory (`algorisme.calcular_ppcc_ranking` calls the per-territory
  function for each source territory).

### 3.4 `obtenir_novetats` — hourly (every :00)
```bash
python manage.py obtenir_novetats [--limit N] [--dry-run]
```
Incremental Deezer ingestion with a 3-tier priority queue:
- **P1** — tracks with `deezer_id` but no ISRC; fetches full track to backfill.
- **P2** — albums with `cancons_obtingudes=False`; fetches tracks.
- **P3** — approved artists, oldest `last_checked_deezer` first; fetches albums
  released within `DIES_CADUCITAT` days.

Uses an `fcntl.flock` on `/tmp/obtenir_novetats.lock` — if a run is still
going, the next hour's run exits cleanly. All created Canco records start
with `verificada=False`; `classificar_i_guardar(canco)` applies the ML class.

### 3.5 `obtenir_metadata` — on demand
```bash
python manage.py obtenir_metadata [--artista-id N] [--force] [--dry-run] [--limit N]
```
For approved artists without an `ArtistaDeezer` link, resolves the
Deezer ID (name search + ISRC cross-validation) and pulls albums +
tracks. Previously the filter was `deezer_no_trobat=False`, but that
flag is a stale cache — the signal-cleared M2M relation is the source
of truth, so the command now targets `deezer_ids__isnull=True`
artists. The flag is still written on the failure path for
backwards-compat readers.

Not in the cron by default — run on demand when staff approves a
batch of new artists without Deezer ids, or before a marketing push
that needs fresh fan counts.

### 3.6 `analitzar_whisper` — nightly 01:30 UTC
```bash
python manage.py analitzar_whisper [--limit N] [--refresh-older-than DAYS]
                                    [--canco-id PK] [--dry-run]
```
Runs `faster-whisper large-v3 .detect_language()` on each Canco's
30-second Deezer preview. Populates `Canco.whisper_lang`,
`whisper_p`, `whisper_all_probs` (99-lang JSON), `whisper_processat_at`.
Processes tracks never analysed first, optionally re-analyses rows
older than N days. Cron window is 01:30 → ~06:45 UTC with
`--limit 700` (~27 s/track on CPU, 15-min buffer before the 07:00
provisional ranking). Full backfill ETA ≈ 9 days for ~6 300 pending
tracks from a cold start.

See `scripts/model_comparison/resultats.md` for the eval numbers
that justified this integration.

### 3.7 `netejar_caducades` — daily 04:00
```bash
python manage.py netejar_caducades
```
Deletes unverified tracks with `data_llancament < today - DIES_CADUCITAT`.

### 3.8 Utility / ad-hoc commands (not cron-scheduled)
- `fix_album_dates`, `fix_artista_principal` — one-off corrections from Deezer.
- `deduplicar_isrc` — merges Cancons that share an ISRC.
- `backfill_deezer_artistes`, `backfill_preview_url` — populate new fields.
- `recalcular_ml` — force retrain the RF model and reclassify all unverified
  tracks. Normally runs automatically via `recalcular_ml_si_cal()` when 5+ new
  decisions have accumulated.

## 4. Track verification (ML classifier)

`music/ml.py` — Random Forest (100 estimators, `class_weight="balanced"`) on
1,448 decisions from `HistorialRevisio`. 219 features: 19 structured + 200
TF-IDF char n-grams of the track title. 5-fold CV: **97.2% accuracy, 99.8% ROC
AUC**. Top features: rejection ratio per artist / per ISRC prefix / per ISRC
registrant (~44% of importance combined).

Classes: `A ≥ 0.7`, `B 0.4–0.7`, `C < 0.4`. Stored on `Canco.ml_classe` +
`ml_confianca`. Model files: `music/ml_model.joblib` + `ml_tfidf.joblib`.

Retraining is triggered automatically by `recalcular_ml_si_cal()` when there
are ≥ `MIN_NEW_DECISIONS` new records since last run (marker file
`/tmp/tq_last_ml_recalc`). Runs in a daemon thread; both files and the marker
must be writable by the `topquaranta` user.

If < `MIN_TRAINING_SAMPLES=20` decisions exist, `pre_classificar` falls back to
a hand-tuned heuristic in `_heuristic_classificar`.

## 5. Cron schedule

File: `/etc/cron.d/topquaranta`. Commands go through
`/home/topquaranta/bin/tq-run` which captures each run's exit code and last
output into `/var/log/topquaranta/status/<tag>.status` — consumed by the
health check (§7).

```cron
# Pipeline
0 * * * *   topquaranta   /home/topquaranta/bin/tq-run obtenir_novetats            >> /var/log/topquaranta/novetats.log    2>&1
0 4 * * *   topquaranta   /home/topquaranta/bin/tq-run netejar_caducades           >> /var/log/topquaranta/neteja.log      2>&1
0 6 * * *   topquaranta   /home/topquaranta/bin/tq-run obtenir_senyal              >> /var/log/topquaranta/senyal.log      2>&1
30 6 * * *  topquaranta   /home/topquaranta/bin/tq-run actualitzar_score_entrada   >> /var/log/topquaranta/senyal.log      2>&1
0 7 * * *   topquaranta   /home/topquaranta/bin/tq-run calcular_ranking --provisional >> /var/log/topquaranta/provisional.log 2>&1
0 8 * * 6   topquaranta   /home/topquaranta/bin/tq-run calcular_ranking            >> /var/log/topquaranta/ranking.log     2>&1

# DB backup
0 3 * * *   postgres      /home/topquaranta/bin/tq-backup                          >> /var/log/topquaranta/backup.log      2>&1
```

## 6. Backups

`/home/topquaranta/bin/tq-backup` runs daily at 03:00 as `postgres`.
Tiered retention in `/home/topquaranta/backups/`:
- `daily/` — last 7 days
- `weekly/` — Sundays, last 4 weeks
- `monthly/` — 1st of month, last 12 months

DB is ~45 MB uncompressed; gzipped ≈ 3 MB per backup. Total retention
worst case ≈ 60 MB.

## 7. Monitoring / health check

No external services. Everything is file-based on the server.

- **`errors.log`** (`/var/log/topquaranta/errors.log`): every `logger.error(...)`
  / `logger.exception(...)` call across the project ends up here (configured
  in `settings/base.py::LOGGING`). Tests are isolated via a `NullHandler` in
  `settings/test.py` so this file only ever captures real production errors.
- **Per-command status files** (`/var/log/topquaranta/status/<tag>.status`):
  written by `tq-run`. Contain `status=OK|FAIL`, `exit_code`, `last_run`
  (ISO-8601), and the last 20 lines of output.
- **`/home/topquaranta/bin/tq-health`**: prints a summary table and exits
  non-zero if any command is FAIL, STALE (past its expected cadence), or if
  there are any Django ERROR-level entries logged today. Safe to pipe to a
  notifier or to read manually when inspecting the server.

## 6. Artist discovery

1. **Deezer contributor detection** — `obtenir_novetats` P3 reads an album's
   tracks; unknown contributors get created as
   `Artista(aprovat=False, auto_descobert=True, pendent_review=True,
   font_descoberta="collaborador")` — `pendent_review=True` enqueues
   it for staff review; `auto_descobert` is immutable provenance.
2. **User proposal** — `PropostaArtista` submitted via `/compte/artista/proposta/`;
   staff approves via `/staff/propostes/<pk>/` which creates the Artista
   together with its Deezer IDs + locations in one transaction.
3. **Manual** — staff can create an approved artist directly.

All auto-discovered artists sit in the pending queue (`/staff/artistes/pendents/`)
until a human approves them with a municipality assignment (which auto-sets
the territory via the `ArtistaLocalitat` → `Municipi` → `Territori` chain).
