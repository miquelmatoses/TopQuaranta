# CLAUDE_PIPELINE.md — Data Pipeline, API Clients, Management Commands

---

## 1. Artist Discovery Pipeline

Multiple sources feed a shared candidate queue (artists with `aprovat=False`).
A human approves or rejects each candidate via Django admin before the artist
enters any ranking. This is the quality gate against false positives.

### Sources

1. **Collaborator detection (Deezer)**: `obtenir_metadata` reads `track["contributors"]`.
   Creates `Artista(aprovat=False, font_descoberta='collaborador')` for unknown collaborators.

2. **Viasona scraper** (pendent): viasona.cat is a Catalan-language music platform.
   Legacy code: `scripts/update_from_viasona.py` — BeautifulSoup scraper.

3. **Manual entry**: admin adds artist directly with `aprovat=True`.

### Discovery flow

```
Collaborator detection  ─┐
Viasona scraper (TODO)  ─┼─→  Artista(aprovat=False, font_descoberta=...)
Manual admin entry      ─┘         (or aprovat=True for manual)
                                          │
                             Human review in Django admin
                             (ArtistaPendentAdmin, filter: aprovat=False)
                                          │
                             Approve → aprovat=True
                             Reject  → delete or keep with aprovat=False
                                          │
                             obtenir_novetats (hourly cron)
                             Deezer: tracks released in last 12 months
                             Store ISRC on each Canco
                                          │
                             obtenir_senyal (daily cron)
                             Last.fm: playcount + listeners
```

---

## 2. API Clients

### 2.1 Last.fm (`ingesta/clients/lastfm.py`)

**Endpoint:** `GET https://ws.audioscrobbler.com/2.0/?method=track.getInfo`
- Params: `api_key`, `artist`, `track`, `format=json`, `autocorrect=1`
- Returns: `{playcount: int, listeners: int}` or `None`
- Rate limit: 0.2s between calls
- Retry: 3 attempts, exponential backoff (2^n seconds)
- Never raises

### 2.2 Deezer (`ingesta/clients/deezer.py`) — PRIMARY METADATA SOURCE

**API:** Public, no authentication. Base URL: `https://api.deezer.com`

**Functions:**
- `search_artist(nom)` → `{"id": int, "name": str}` or `None` (normalized matching)
- `get_artist_info(deezer_id)` → `{id, name, nb_fan, nb_album}`
- `get_artist_albums(deezer_id, min_date)` → list of album dicts (paginated)
- `get_album_tracks(album_id)` → list of track dicts with ISRC + contributors

Rate limit: 1.0s. Retry: 3x with backoff. Quota detection (error code 4) stops session.

### 2.3 Spotify (`ingesta/clients/spotify.py`) — FALLBACK

Blocked since 2024 (requires Premium). Client implemented but returns 403.
Kept as fallback if Premium is restored.

---

## 3. Management Commands

### Rules for all commands

- `self.stdout.write()` — never `print()`
- `raise CommandError(...)` — never `sys.exit()`
- All DB writes inside `transaction.atomic()`
- Idempotent where possible
- End with summary line: processed / success / errors

### 3.1 obtenir_senyal (daily — 06:00)

```
python manage.py obtenir_senyal [--data YYYY-MM-DD] [--limit N] [--dry-run]
```

Queries verified + active + recent + approved tracks. Calls Last.fm, stores
`SenyalDiari`. Computes `score_entrada` via percent_rank at end.

### 3.2 actualitzar_score_entrada (daily — 06:30, safety net)

```
python manage.py actualitzar_score_entrada [--data YYYY-MM-DD] [--tots]
```

Backfills `score_entrada` for rows where it is NULL. Uses `percentileofscore`.

### 3.3 calcular_ranking (daily provisional + weekly official)

```
python manage.py calcular_ranking [--setmana YYYY-MM-DD] [--territori CODE] [--dry-run] [--provisional]
```

- `--provisional`: writes to `RankingProvisional` (all eligible territories, daily 07:00)
- Without flag: writes to `RankingSetmanal` (fixed territories, Saturday 08:00)

### 3.4 obtenir_novetats (hourly)

```
python manage.py obtenir_novetats [--limit N]
```

Incremental Deezer ingestion with 3-tier priority queue:
- P1: backfill ISRC + preview for tracks missing them
- P2: fetch tracks for albums with `cancons_obtingudes=False`
- P3: check approved artists for new albums (oldest-checked first)

### 3.5 obtenir_metadata (on demand)

```
python manage.py obtenir_metadata [--artista-id N] [--force] [--dry-run] [--limit N]
```

Deezer metadata fetch for approved artists. ISRC validation flow.

### 3.6 netejar_caducades (daily — 04:00)

```
python manage.py netejar_caducades
```

Deletes unverified tracks older than 12 months.

### 3.7 importar_legacy (one-off)

```
python manage.py importar_legacy [--artistes] [--cancons] [--dry-run]
```

### 3.8 Other utility commands

- `matching_isrc_deezer` — find Deezer ID via legacy ISRC
- `fix_artista_principal` — correct main artist using Deezer contributors
- `deduplicar_isrc` — merge Canco records with same ISRC
- `fix_album_dates` — correct dates from Deezer
- `backfill_deezer_artistes` — populate deezer_nb_fan, deezer_nb_album
- `backfill_preview_url` — fetch preview URLs
- `poblar_isrc` — populate ISRC from legacy spotify_tracks

---

## 4. Track Verification System

### ML pre-classification (`music/ml.py`)

Dual classifier: Random Forest (if >= 20 training samples) or heuristic fallback.

**19 features** + 200 TF-IDF char n-gram features. Classes: A (green, >= 0.7), B (orange, 0.4-0.7), C (red, < 0.4).

Model at `music/ml_model.joblib`, TF-IDF at `music/ml_tfidf.joblib`.
Retrained automatically via `recalcular_ml_si_cal()` when >= 5 new decisions.

### Admin actions with motiu

All reject actions show intermediate confirmation page with required motiu dropdown.
Every action calls `crear_historial()` before modifying/deleting records.

---

## 5. Cron Schedule

File: `/etc/cron.d/topquaranta` — runs as user `topquaranta`

```cron
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
DJANGO_SETTINGS_MODULE=topquaranta.settings.production

# Hourly Deezer novelty ingestion
0 * * * *   topquaranta   obtenir_novetats >> novetats.log

# Daily cleanup of expired unverified tracks — 04:00
0 4 * * *   topquaranta   netejar_caducades >> neteja.log

# Daily signal ingestion — 06:00
0 6 * * *   topquaranta   obtenir_senyal >> senyal.log

# Safety net: recompute score_entrada — 06:30
30 6 * * *  topquaranta   actualitzar_score_entrada >> senyal.log

# Daily provisional ranking — 07:00
0 7 * * *   topquaranta   calcular_ranking --provisional >> provisional.log

# Weekly official ranking — Saturday 08:00
0 8 * * 6   topquaranta   calcular_ranking >> ranking.log
```
