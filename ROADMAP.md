# ROADMAP.md — TopQuaranta Implementation Phases

> Updated: 2026-04-15 — Phase 7 P1-P6 staff panel DONE

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
- [x] Create `ranking/models.py` (`ConfiguracioGlobal`, `SenyalDiari`, `RankingSetmanal`) and migrate
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
- [x] Implement `obtenir_senyal` management command
- [x] Run `obtenir_senyal --dry-run --limit 50`, inspect output
- [x] Set up cron: `obtenir_senyal` daily at 06:00 (`/etc/cron.d/topquaranta`)
- [x] `obtenir_senyal` filters by `verificada=True` — safe from Deezer false positives
- [ ] Fix `lastfm_nom` mismatches (manual or heuristic) ← **next**
- [ ] Run daily ingestion for 7 consecutive days

**Current state (2026-04-12):**
- Emergency fix: 6,002 Deezer-only cançons (no `spotify_id`) reverted to `verificada=False`
  - Root cause: bulk verification on 2026-04-11 included non-Catalan false positives from Deezer
  - 57.4% error rate in daily cron triggered the fix
- Eligible tracks (verified, recent, approved): recalculated from 10,351 legacy-only verified
- `obtenir_senyal` only processes `verificada=True` cançons — Deezer tracks now excluded until manual review
- Idempotency verified (re-run skips already-ingested)

**Go/no-go (pending):**
- ≥ 80% of active tracks have successful Last.fm data after 5 days
- Error rate < 20%
- `SenyalDiari` rows show non-zero `playcount` and `listeners`
- `score_entrada` is NULL everywhere (correct — formula not defined yet)

---

## Phase 3 — Signal formula definition `DONE`

**Goal:** look at real data and decide how to normalize.

- [x] Write one-off analysis script (`scripts/explorar_senyal.py`) → print distribution stats
- [x] Discuss formula in conversation — chose Formula B (percent_rank)
- [x] Ranking simulation (`scripts/simular_ranking.py`) validated algorithm with real data
- [x] Implement formula inline in `obtenir_senyal` (normalization step at end of ingestion)
- [x] Implement `actualitzar_score_entrada` command (`--data`, `--tots`)
- [x] Backfill all 5 existing days: 4,523 rows updated, 0 NULL remaining
- [x] Cron: `actualitzar_score_entrada` at 06:30 as safety net after `obtenir_senyal`
- [x] Verify: `score_entrada` not NULL for 100% of success rows, distribution 0–100

**Formula:** `score_entrada = percentileofscore(day_playcounts, playcount, kind='rank')`
- playcount=0 → score_entrada=0.0
- Computed per-day over all successful tracks
- Average ~50, std ~29, full 0–100 range

---

## Phase 4 — Ranking algorithm adaptation `DONE`

**Goal:** run the existing algorithm with the new signal.

- [x] Extract SQL from `vw_top40_weekly_cat` PostgreSQL view
- [x] Port to `ranking/algorisme.py` — 14-CTE SQL with adapted table/column names
  - `ranking_diari` → `ranking_senyaldiari` via `cancons_territori` bridge CTE
  - `popularitat` → `score_entrada`
  - Territory derived from `music_artista_territoris` M2M (not stored on signal)
  - `artistes_ids[1]` → `music_canco.artista_id` FK
  - `configuracio_global` → `ranking_configuracioglobal`
- [x] Implement `calcular_ranking` management command (`--setmana`, `--territori`, `--dry-run`)
- [x] First run (2026-04-14): CAT=40, VAL=40, BAL=40 positions saved for week 2026-04-13
- [ ] Write `test_algorisme.py` (fixture-based, known expected output)
- [x] Added to cron: Saturday 08:00 (official), daily 07:00 (provisional)

**Go/no-go:** all passed
- Rankings for CAT, VAL, BAL without SQL errors
- Each territory = 40 entries
- Results validated against Python simulation (`scripts/simular_ranking.py`)
- Top artists culturally plausible (Companyia Elèctrica Dharma, Feliu Ventura, Rudymentari)

---

## Phase 5 — Provisional ranking + admin review `DONE`

**Goal:** daily provisional ranking for admin review, weekly official ranking on Saturdays.

- [x] `RankingProvisional` model — rolling daily ranking, truncated and rebuilt each run (migration 0004)
- [x] `calcular_ranking --provisional` flag — writes to `RankingProvisional` instead of `RankingSetmanal`
- [x] `algorisme.py`: collaborator territory join (LEFT JOIN `artistes_col`), returns `dies_en_top`
- [x] `RankingProvisionalAdmin` — read-only list with Deezer/Last.fm links
- [x] Admin actions: rebutjar cançó (verificada=False + historial), rebutjar artista (deezer_no_trobat + esborrar cançons)
- [x] `TerritoriProvisionalFilter` — defaults to CAT
- [x] Cron: provisional ranking daily at 07:00, official ranking Saturday at 08:00

**Summary:** RankingProvisional model + admin amb accions de rebuig directe (rebutjar cançó / rebutjar artista), ranking provisional diari a les 07:00, ranking oficial dissabtes a les 08:00.

> **Distribution (Telegram + images): SHELVED INDEFINITELY.**
> Originally Phase 5b. Shelved because:
> - Original assets (TTF fonts, SVG logos per territory) were on an inaccessible local machine
> - Instagram via Telegram was the only distribution channel
> - Replaced by future web publica (Phase 6) as primary distribution channel

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
- [x] Implement `obtenir_metadata` command using Deezer
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

- **obtenir_metadata complete:** 2,273 artists processed
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

- `obtenir_senyal` (daily cron) only processes `verificada=True` tracks
- New Deezer tracks enter with `verificada=False` — blocked from ranking
- Admin must review and approve before tracks enter the pipeline
- Prevents false positives (Aion metal, anime, etc.) from polluting rankings

### Track verification system (2026-04-12) `DONE`

- [x] `HistorialRevisio` model — records every approve/reject with motiu and snapshot (migration 0009)
- [x] Artista Deezer metadata: `deezer_nb_fan`, `deezer_nb_album`, `deezer_nom`, `deezer_nom_similitud`
- [x] `music/verificacio.py::crear_historial()` — snapshot helper called before delete/modify
- [x] Admin actions with intermediate confirmation page and required motiu
- [x] ML Random Forest classifier `music/ml.py::pre_classificar()` — classes A/B/C (607 samples, heuristic fallback)
- [x] ML column in CancoAdmin with color and tooltip, MLClasseFilter
- [x] `HistorialRevisioAdmin` — read-only admin for review history
- [x] 50 initial decisions imported via `scripts/importar_decisions_inicials.py`

### Collaborator extraction from Deezer (2026-04-12) `DONE`

- [x] `deezer.get_artist_info()` — fetches nb_fan, nb_album for metadata
- [x] `deezer.get_album_tracks()` — now returns `contributors` list from full track endpoint
- [x] `obtenir_metadata._upsert_track()` — reads contributors, creates collaborator Artista if needed
- [x] `obtenir_metadata._resolve_deezer_id()` → populates `deezer_nb_fan`, `deezer_nb_album`, `deezer_nom`, `deezer_nom_similitud`

### Territory expansion (2026-04-12) `DONE`

- [x] Territori.codi expanded from max_length=3 to 4 (migration 0013)
- [x] 7 new territories added (migration 0014): CNO, AND, FRA, ALG, CAR, ALT, PPCC
- [x] `importar_legacy` updated: comarca → `municipis` table → territory code mapping
- [x] Update-in-place instead of delete+recreate (preserves Deezer metadata)
- [x] 2,313 artists reimported: CAT=1748, VAL=316, BAL=209, ALT=19, CNO=10, AND=9, FRA=1, ALG=1
- [x] `ConfiguracioGlobal.min_cancons_ranking_propi` (default=20) for threshold
- [x] `ranking/algorisme.py::territoris_amb_ranking_propi()`: CAT/VAL/BAL always, others if ≥ threshold
- [x] `RankingSetmanal.territori` expanded to max_length=4

### Incremental Deezer ingestion (2026-04-12) `DONE`

- [x] `Artista.last_checked_deezer` and `Album.cancons_obtingudes` fields (migration 0015)
- [x] `obtenir_novetats` command with priority queue:
  - P1: backfill ISRC + preview for tracks missing them
  - P2: fetch tracks for albums with `cancons_obtingudes=False`
  - P3: check approved artists for new albums (oldest-checked first)
- [x] Cron: daily at 05:00 (`/etc/cron.d/topquaranta`)
- [x] Deezer rate limit increased: 0.1s → 1.0s to avoid quota exhaustion
- [x] `fix_artista_principal` complete: 10,638 tracks checked, 1,316 main artists fixed, 5,063 collaborators added

### Terminology refactoring (2026-04-13) `DONE`

- [x] Renamed: ingestar_novetats→obtenir_novetats, ingestar_senyal→obtenir_senyal, ingestar_metadata→obtenir_metadata
- [x] Renamed: cancons_ingerades→cancons_obtingudes (migration 0016)
- [x] Renamed: IngestaDiari→SenyalDiari (migration ranking/0003, RenameModel preserving data)
- [x] Album.descartat field (migration 0016) — marks rejected albums, skipped by obtenir_novetats
- [x] Admin marks album.descartat=True on all reject actions
- [x] Random Forest classifier trained with 607 decisions (replaces heuristic)
  - Top features: ratio_rebuig_artista (36%), ratio_rebuig_isrc_prefix (28%), isrc_es (10%)
  - Model at music/ml_model.joblib, retrained on each recalcular_ml call

### Pending

- [ ] Audit `scripts/update_from_viasona.py` → rebuild in `ingesta/clients/viasona.py`
- [ ] Implement `descobrir_artistes` command
- [ ] Migrate CMS pages to read from new models
- [ ] Clean up false positive `deezer_id` matches (Aion, Animal, etc.) — manual review
- [x] Populate `deezer_nb_fan`/`deezer_nb_album` for existing 1,894 artists with `deezer_id` (backfill)

**Go/no-go:**
- Discovery runs without crash
- New candidates appear in Wagtail admin
- Website displays data from new models
- Full pipeline: discovery → approval → metadata → signal → ranking → distribution

---

## Phase 6 — Web pública `IN PROGRESS`

**Goal:** build topquaranta.cat as the primary public distribution channel.

Built on: Django 5.2 + Wagtail 7.0 + `web/` app + mm-design tokens.
Served via gunicorn port 8083 (`topquaranta.settings.web_server`), Caddy reverse proxy.

### Architectural decisions (permanent reference)

| Decision | Detail |
|---|---|
| **mm-design** | npm git dependency (`github:miquelmatoses/mm-design`), tokens via `STATICFILES_DIRS` + `{% static %}`. Never hardcode hex values. |
| **Logo SVG** | Created from scratch (`web/static/web/img/logo-topquaranta.svg`). Original PNG was on an inaccessible local machine. All fills use `var(--mm-color-*)`. |
| **Domain flip** | After S3 is complete: Caddy routes all public paths to port 8083 instead of legacy Wagtail. Legacy only keeps `/nou-admin/`. |
| **Wagtail** | Keep admin for now. Migrate admin tools to web pública in Phase 7. Uninstall Wagtail when the last tool is migrated. |
| **User architecture** | Three roles: anonymous, verified artist, admin. App `comptes/` with custom `Usuari` model extending `AbstractUser`. |
| **API** | Django REST Framework under `/api/v1/`. Used for GeoJSON map data and future artist portal. |
| **Territory colors** | CAT=`--mm-color-yellow`, VAL=`--mm-color-red`, BAL=`--mm-color-blue`, PPCC=`--mm-color-green`. Applied via CSS class `territori-<code>` on `<body>`. |

### S1 — Homepage CAT `DONE`

- [x] `web/` Django app: views, urls, apps, context_processors
- [x] `web/templates/web/base.html` — loads mm-design tokens via `{% static %}`
- [x] `web/templates/web/homepage.html` — Top 40 CAT, fallback RankingSetmanal → RankingProvisional
- [x] `web/static/web/css/style.css` — zero hex colors, all mm-design tokens
- [x] `topquaranta/settings/web_server.py` — gunicorn port 8083
- [x] `topquaranta-web.service` systemd unit
- [x] Caddy config: `/` + `/static/*` → port 8083

### S2 — Ranking per territori + arxiu setmanal `DONE`

- [x] `/ranking/<territori>/` — CAT, VAL, BAL, PPCC (current week)
- [x] `/ranking/<territori>/<setmana>/` — specific week (YYYY-MM-DD, must be Monday)
- [x] Territory nav in `base.html` with accent colors
- [x] Invalid territory or date → 404
- [x] PPCC: no RankingProvisional fallback — empty state if no RankingSetmanal
- [x] Design audit: all border-radius, spacing, colors use mm-design tokens

### S3 — Perfil artista + directori `DONE`

- [x] `Artista.slug` field (SlugField, auto from `nom`, unique). Data migration to populate all.
- [x] `/artistes/` — directory of approved artists, filterable by territory (CAT/VAL/BAL), searchable by name. Paginated (40/page).
- [x] `/artista/<slug>/` — artist profile: nom, territories, location, last 10 weeks in `RankingSetmanal`, discography.
- [x] Artist profiles linked from ranking entries.
- [x] Caddy: `/artista/*` and `/artistes/*` routes to port 8083.

### S4 — Mapa D3.js + GeoJSON `DONE`

- [x] `djangorestframework` installed, `/api/v1/mapa/artistes/` endpoint.
- [x] `/mapa/` — three-level zoomable SVG map with D3.js (CDN):
  - Level 1: 8 territory shapes (merged from QGIS shapefiles via shapely)
  - Level 2: 97 comarca shapes per territory
  - Level 3: 1,826 municipality shapes per comarca, with artist data overlay
- [x] GeoJSON files generated from original QGIS shapefiles (`temp/geodata/`):
  - `territoris.geojson` (89 KB), `comarques-ppcc.geojson` (556 KB), `municipis.geojson` (2.3 MB)
- [x] Territory accent colors from mm-design CSS variables via `getComputedStyle()`.
- [x] Caddy: `/mapa/*` and `/api/*` routes to port 8083.

### S5 — App `comptes/` — registre, login, dashboard `DONE`

- [x] `comptes/` app with `Usuari(AbstractUser)` model, `AUTH_USER_MODEL`, migration.
- [x] `/compte/registre/` — email + password form, verification email, inactive until confirmed.
- [x] `/compte/login/` — login → redirect `/compte/dashboard/`.
- [x] `/compte/logout/` — POST logout.
- [x] `/compte/dashboard/` — login required, account info + artist verification status.
- [x] All templates extend `web/base.html`, mm-design tokens only.
- [x] Caddy: `/compte/*` route to port 8083.

### S6 — Portal artista verificat `DONE`

- [x] `UserArtista` model (OneToOne Usuari, FK Artista, `verificat`, `sollicitud_text`). Migration 0002.
- [x] `/compte/artista/sol·licitud/` — login required, select artist + justification text. Creates `UserArtista(verificat=False)`. Shows status if already exists.
- [x] `/compte/artista/` — login required + `verificat=True`. Shows: artist info, weekly evolution chart (HTML/CSS), last 10 weeks ranking history, provisional ranking, pending songs.
- [x] `/compte/artista/` returns 403 for unverified users.
- [x] Dashboard updated: shows link to solicitud/portal/pending status.
- [x] Admin email notification (`mail_admins`) on new `UserArtista` creation.
- [x] Wagtail admin: `UserArtistaViewSet` (snippet) for staff to set `verificat=True`.
- [x] Django admin: `UserArtistaAdmin` with `list_editable = ("verificat",)`.

### Domain flip `DONE`

- [x] `www.topquaranta.cat` → port 8083 (new web) as default handler.
- [x] `legacy.topquaranta.cat` → port 8081 (legacy Wagtail). DNS A record pending.
- [x] `/nou-admin/*` → port 8082 (admin server, unchanged).
- [x] `/static/*` → staticfiles directory (unchanged).
- [x] Legacy gunicorn ALLOWED_HOSTS updated.

### Pending (not yet scheduled)

- [ ] Disseny responsive polish (mobile-first testing across devices)
- [ ] SEO: meta tags, Open Graph, sitemap.xml
- [ ] DNS A record for `legacy.topquaranta.cat` → `188.245.60.20`

---

## Phase 7 — Staff panel (`/staff/`) `IN PROGRESS`

**Goal:** migrate all admin tools from Django/Wagtail admin to custom `/staff/` web interface, then remove Wagtail entirely.

### P1 — Infraestructura base `DONE`

- [x] Convert `web/views.py` → `web/views/__init__.py` package
- [x] Create `web/views/staff/` package with `staff_required` decorator and `paginate()` helper
- [x] Create `base_staff.html` (extends `web/base.html`, staff nav, messages)
- [x] Create `confirmar_accio.html` (reusable confirmation page with motiu select)
- [x] Create `staff/dashboard.py` + template — landing page at `/staff/`
- [x] Wire `/staff/` URL prefix in `topquaranta/urls.py`
- [x] Staff CSS: nav, badge, messages, tables, filters, actions bar, tool cards
- [x] Staff returns 403 for anonymous, 403 for non-staff, 200 for staff users

### P2 — Cançons (`/staff/cancons/`) `DONE`

- [x] List view: ML class, nom, artista, album, data, Deezer/Viasona links, ISRC, verificada, territoris
- [x] Filters: verificada (defaults to non-verified), ml_classe, data_llancament (year)
- [x] Search by nom and artista__nom
- [x] Bulk actions: aprovar, rebutjar (esborrar), rebutjar àlbum sencer — with motiu select
- [x] Ordered by -ml_confianca
- [x] Custom template tags: `ml_badge`, `territori_list`, `query_string`

### P3 — Ranking provisional (`/staff/ranking/`) `DONE`

- [x] List by territory (defaults to CAT), all 10 territories available
- [x] Columns: posicio, artista, cançó, playcount, dies_en_top, Deezer/Last.fm links
- [x] Actions: rebutjar cançó, rebutjar artista — with motiu select

### P4 — Artistes (`/staff/artistes/`) `DONE`

- [x] List view with filters (aprovat, deezer, territori), search by nom
- [x] Edit page for individual artist (nom, lastfm_nom, deezer_id, localitat, comarca, territoris, aprovat)
- [x] Actions: marcar sense Deezer, aprovar artista (with comarca→territory auto-assign)
- [x] Deezer ID change triggers cleanup of old unverified tracks

### P5 — Artistes pendents (`/staff/artistes/pendents/`) `DONE`

- [x] Cascading selects: territori → comarca → localitat (3 JSON API endpoints)
- [x] Per-row approve/discard buttons (AJAX with fetch API)
- [x] Ordered by verified tracks count (descending)
- [x] Row fades on approve/discard

### P6 — Eines restants `DONE`

- [x] `/staff/historial/` — read-only log with decisio/motiu filters and search
- [x] `/staff/senyal/` — daily signal list with date filter, errors-only filter, search
- [x] `/staff/verificacio/` — UserArtista management with verify/unverify toggle
- [x] `/staff/configuracio/` — ConfiguracioGlobal edit form (all 15 coefficients)

### P7 — Eliminació Wagtail + Django admin `PENDING`

- [ ] Remove `wagtail.*` from INSTALLED_APPS
- [ ] Remove Django admin URLs
- [ ] Remove admin.py files across all apps
- [ ] Remove wagtail_hooks.py files
- [ ] Clean up dependencies (requirements.txt)
- [ ] Eliminate gunicorn on port 8082 (admin_server)
- [ ] Update Caddyfile (remove `/nou-admin/*` routes)

### P8 — Refactoring i consolidació `PENDING`

- [ ] Analysis of dead code after Wagtail removal
- [ ] Settings simplification (remove admin_server.py)
- [ ] Template/CSS cleanup

---

## Phase 8 — Legacy cleanup

**Goal:** remove legacy tables and views, clean up.

- [ ] Verify all functions work from new pipeline for >= 4 weeks
- [ ] Drop legacy SQL views (`vw_top40_*`, etc.)
- [ ] Drop legacy tables — **only after backup confirmed**
- [ ] Remove `legacy/` app from project
- [ ] Remove old cron jobs
- [ ] Archive `/root/TopQuaranta/` directory
- [ ] Full test suite passes, coverage >= 70%

**This phase requires explicit approval before each destructive step.**
