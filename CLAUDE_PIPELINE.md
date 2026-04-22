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

### `spotify.py` — playlist output (active since 2026-04)
- Two classes. `SpotifyClient` is the legacy Client-Credentials wrapper
  (ingest endpoints no longer available to us since Spotify gated Web API
  behind Premium in 2024).
- **`UserSpotifyClient`** is the live path: OAuth refresh-token flow for the
  admin account. Rotates access tokens on 401 mid-flight, honours 429
  `Retry-After`, persists a rotated refresh_token when Spotify issues one.
  Supports `search_isrc()` for resolution and chunked
  `replace_playlist_tracks()` for the daily sync (§3.9).
- Scopes used: `playlist-modify-private playlist-modify-public`.

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

### 3.7 `obtenir_metadata_musicbrainz` — every 15 min
```bash
python manage.py obtenir_metadata_musicbrainz [--refresh-days N]
                                              [--limit N] [--artista-id PK]
```
Pulls MusicBrainz metadata into our Artista / Album / Canço rows.
Single-instance `fcntl.flock` on `/tmp/mb_sync.lock`; MB's 1 req/s
rate limit is globally enforced by the client.

Per artist the flow is:
  1. If no `musicbrainz_id`: `search_artist(nom)` — strict exact-name
     + score ≥ 95 + PPCC area disambiguation. Ambiguous names (Crim,
     Apa, …) are skipped and left to staff.
  2. Otherwise: `get_artist` + `get_artist_release_groups` +
     `get_release_group_with_recordings` → fills type/gender/area/
     begin_date/end_date/disambiguation/sort_name/aliases/tags/rating,
     plus URL relationships (bandcamp/spotify/youtube/youtube music/
     soundcloud/wikipedia/viasona/facebook/myspace — never overwriting
     values staff already set).
  3. Reconciles Albums by normalised title (fuzzy 0.9+) →
     `mb_release_group_id`, `mb_type_secondary`, `mb_status`,
     `mbrainz_confirmed=True`.
  4. Reconciles Cançons by ISRC first, then normalised title →
     `mb_recording_id`, `mb_work_id`, `mb_lyrics_language`,
     `mbrainz_confirmed=True`. A `Work.language=='cat'` is logged
     and feeds the `mb_lyrics_cat` ML feature.
  5. Caches `{isrcs, titles}` on `Artista.mb_discography_cache` for
     quick future matches.
  6. Stamps `mb_last_sync` regardless of outcome, so idle retries
     don't thrash.

Queue priority: aprovat > pendent > descartat; within each, oldest
`mb_last_sync` first. Refresh every 7 days by default. The cron
exits when nobody needs attention — idle invocations are cheap.

### 3.9 `netejar_caducades` — daily 04:00
```bash
python manage.py netejar_caducades
```
Deletes unverified tracks with `data_llancament < today - DIES_CADUCITAT`.

### 3.10 Utility / ad-hoc commands (not cron-scheduled)
- `recalcular_ml` — force retrain the RF model and reclassify all unverified
  tracks. Normally runs automatically via `recalcular_ml_si_cal()` when 5+ new
  decisions have accumulated.
- `arxivar_senyal_vell` — quarterly archive of SenyalDiari rows older than 2 years
  (Φ6 retention).

**One-shot migrations already executed** live under
`scripts/archived_commands/` (out of `manage.py` reach):
`fix_album_dates`, `fix_artista_principal`, `deduplicar_isrc`,
`backfill_deezer_artistes`, `backfill_preview_url`,
`seed_spotify_playlists`. Preserved for history only.

### 3.11 Spotify playlist sync — daily 07:15 UTC
```bash
python manage.py actualitzar_playlists_spotify [--dry-run] [--only <codi>]
```
Reads every `SpotifyPlaylist` row with a configured `spotify_playlist_id`
and rewrites its tracklist in place. Runs 15 minutes after the provisional
ranking settles.

Per kind:
- `top` → `RankingProvisional.filter(territori=X).order_by('posicio')[:40]`
- `novetats` → `Canco.filter(data_llancament=yesterday, activa=True)[:100]`

Resolves each Canço to a Spotify URI via `UserSpotifyClient.search_isrc()`
and caches the result on `Canco.spotify_id` so subsequent runs skip the
search. Mismatches (ISRC not found on Spotify) are silently dropped; the
`SpotifyPlaylist.last_n_tracks` vs `last_n_matched` fields expose the
mismatch rate per run.

One-time setup (once per Spotify account):
```bash
# Prints the OAuth URL, takes the `code` from the callback, persists
# refresh_token to SpotifyAuth (singleton).
python manage.py autoritzar_spotify

# Attach the existing Spotify playlist IDs to the 5 seeded rows.
python manage.py configurar_spotify_playlists \
    --top-cat <id> --top-val <id> --top-bal <id> --top-alt <id> \
    --novetats <id>
```

## 4. Track verification (ML classifier)

`music/ml.py` — Random Forest (100 estimators, `class_weight="balanced"`)
trained on **4,371** decisions from `HistorialRevisio`. Post 2026-04-21
feature slim: **76 features** (16 structured + 4 Whisper LID + 60 TF-IDF
char n-grams of the track title).

5-fold CV metrics (2026-04-21, 4,371 training rows):
- ROC-AUC **0.9994** · F1 **0.9522** · Accuracy **0.9675**.
- Top 10 features carry **88%** of the signal (was 77% in the 223-feature
  model).

Top 5 features by importance:
1. `ratio_rebuig_artista` (22.2%) — Bayesian-smoothed (k=5, prior=0.5)
2. `ratio_rebuig_registrant` (14.9%)
3. `ratio_rebuig_isrc_prefix` (13.6%)
4. `nb_decisions_artista` (9.1%)
5. `nom_artista_len` (7.1%)

Bayesian smoothing on the three `ratio_rebuig_*` features: returns
`(rej + k*p) / (total + k)` with `k=5, p=0.5`, so an artist with few
decisions can't collapse to 0 or 1 from one or two calls. Prevents
feedback loops where an early false rebuig biases the model
permanently.

Classes: `A ≥ 0.7`, `B 0.4–0.7`, `C < 0.4`. Stored on `Canco.ml_classe` +
`ml_confianca`. Model files: `music/ml_model.joblib` + `ml_tfidf.joblib`.
Both cached in-memory with mtime-based invalidation.

Retraining triggers automatically via `recalcular_ml_si_cal()` when
≥ `MIN_NEW_DECISIONS=5` records have arrived since last run (marker:
`/tmp/tq_last_ml_recalc`). Runs in a daemon thread. If
< `MIN_TRAINING_SAMPLES=20` decisions exist, `pre_classificar` falls
back to a hand-tuned heuristic.

Live feature importances + training size + class distribution + mean
confidence are surfaced on `/staff/estat` via `/api/v1/staff/estat/`.

## 5. Cron schedule

File: `/etc/cron.d/topquaranta`. Commands go through
`/home/topquaranta/bin/tq-run` which captures each run's exit code and last
output into `/var/log/topquaranta/status/<tag>.status` — consumed by the
health check (§7).

```cron
# Pipeline
0 * * * *    topquaranta  tq-run obtenir_novetats                 # every hour
*/15 * * * * topquaranta  tq-run obtenir_metadata_musicbrainz     # every 15 min
30 1 * * *   topquaranta  tq-run analitzar_whisper --limit 700    # nightly LID
0 4 * * *    topquaranta  tq-run netejar_caducades                # 04:00
0 6 * * *    topquaranta  tq-run obtenir_senyal                   # 06:00
30 6 * * *   topquaranta  tq-run actualitzar_score_entrada        # 06:30
0 7 * * *    topquaranta  tq-run calcular_ranking --provisional   # 07:00
15 7 * * *   topquaranta  tq-run actualitzar_playlists_spotify    # 07:15 Spotify sync
0 8 * * 6    topquaranta  tq-run calcular_ranking                 # Sat 08:00 official

# DB backup
0 3 * * *   postgres      tq-backup                               # 03:00

# Retention
0 5 1 1,4,7,10 * topquaranta tq-run arxivar_senyal_vell           # quarterly
30 4 1 * *  postgres        tq-restore-test                       # monthly
*/30 * * * * topquaranta    tq-recover                            # recovery sweep
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
