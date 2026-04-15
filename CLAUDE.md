# CLAUDE.md — TopQuaranta System Architecture

> Persistent memory for Claude Code. Read this file before making any change.
> Last updated: 2026-04-15 — Phase 6 done (S1–S6), domain flip done
>
> See **ROADMAP.md** for implementation status.

---

## Supplementary documentation

- **CLAUDE_MODELS.md** — Models Django (Artista, Album, Canco, SenyalDiari, RankingSetmanal, RankingProvisional, HistorialRevisio)
- **CLAUDE_ALGORITHM.md** — Algoritme de ranking (14-CTE SQL, score_entrada, fases A/B/C/final)
- **CLAUDE_PIPELINE.md** — Pipeline de dades (clients API, management commands, crons)
- **CLAUDE_LEGACY.md** — Audit del sistema legacy (nomes referencia, no tocar)

---

## 1. Project Overview

TopQuaranta (topquaranta.cat) is a weekly music ranking system for Catalan-language
music across territories: Catalunya (CAT), Pais Valencia (VAL), Illes Balears (BAL),
and others (CNO, AND, FRA, ALG, CAR, ALT, PPCC).

Cultural mission: demonstrate that Catalan-language music is alive and growing.

**Current state (2026-04-15):** the pipeline (ingesta -> senyal -> ranking) is
operational. Public website live at topquaranta.cat with ranking pages, artist
profiles, geographic map, user accounts, and verified artist portal. Domain
flipped: www.topquaranta.cat → new web (port 8083), legacy at legacy.topquaranta.cat.

> **Image generation + Telegram distribution: indefinitely shelved.**
> The original Phase 5 planned Pillow image generation + Telegram sending for
> Instagram publication. This is shelved because:
> - Original assets (TTF fonts, SVG logos per territory) were on a local machine
>   that is no longer accessible
> - Instagram via Telegram was the only distribution channel — no web
> - We have decided to build a **public website** (topquaranta.cat) as the primary
>   distribution channel: public weekly ranking, artist database, geographic maps,
>   temporal evolution, registered artist portal
> - The web will be built on the new architecture (Django 5.2 + Wagtail 7.0 +
>   new models), not on legacy

### Why this refactor

The previous system used Spotify `popularity` (0-100), deprecated for Development
Mode apps in November 2024. The old `worker.py` (1,350-line monolith with TRUNCATE,
no transactions, sys.exit() throughout) is disabled. This is a full rewrite.

**New signal source:** Last.fm — `playcount` (cumulative total plays) and
`listeners` (unique listeners). Raw values stored daily. Normalization via
`percentileofscore` (Formula B, implemented in Phase 3).

### Infrastructure

- Server: Hetzner CX22, Ubuntu 22.04, IP 188.245.60.20
- Reverse proxy: Caddy (auto TLS)
- Database: PostgreSQL 14 (local), DB name `topquaranta`, user `topquaranta`
- Runtime: Python 3.10
- Legacy CMS: Django 5.1.11, Wagtail 6.4.2 (running at `/root/TopQuaranta/web_cms/`)
- New project: Django 5.2, Wagtail 7.0
- Repo: https://github.com/miquelmatoses/TopQuaranta (private)
- Process user: `topquaranta`
- Admin URL: `https://www.topquaranta.cat/nou-admin/`
- Public web: `https://www.topquaranta.cat/` → Caddy → gunicorn port 8083 (`web_server` settings)
- Staff panel: `https://www.topquaranta.cat/staff/` → same gunicorn, requires `is_staff=True`

---

## Design System (mm-design)

All frontend work uses mm-design (https://github.com/miquelmatoses/mm-design).

### Integration
- Git submodule at `static/mm-design/` (add with `git submodule add https://github.com/miquelmatoses/mm-design.git static/mm-design`)
- CSS tokens loaded via `{% static 'mm-design/tokens/colors.css' %}` etc. in base template
- Icons from `mm-design/icons/` — embed SVGs via `{% static %}` or include inline

### Rules
1. **Tokens**: All colors, fonts, spacing, and shadows must come from mm-design tokens (`var(--mm-*)`). Never hardcode hex values.
2. **Fonts**: Playfair Display (headings), Roboto (body), JetBrains Mono (code). No other fonts.
3. **Icons**: All icons come from mm-design/icons/. If a needed icon does not exist, add it to mm-design first (SVG + React export), then import.
4. **Components**: Use mm-design CSS component classes (.mm-btn, .mm-card, etc.) where applicable.
5. **README badges**: All shields.io badge hex colors must use the mm-design brand palette:
   - Red: cf3339 | Blue: 0047ba | Yellow: f1c22f | Green: 427c42 | Black: 111111
6. **No parallel design systems**: Never create local token files, color constants, or icon collections that duplicate mm-design.

---

## 2. Legacy System Audit (2026-04-10)

### 2.1 Legacy codebase location

Two copies exist on the server:
- `/root/TopQuaranta/` — git repo (1 commit: "Initial commit"), `.git` present
- `/root/TopQuaranta_dev/` — dev copy with venv at `/root/TopQuaranta_dev/venv`
- Symlink: `/root/TopQuaranta/venv -> /root/TopQuaranta_dev/venv`
- Everything runs as `root` — no `topquaranta` OS user exists yet
- No `/home/topquaranta/` directory exists

### 2.2 Legacy Django structure

```
/root/TopQuaranta/web_cms/
├── manage.py                    # DJANGO_SETTINGS_MODULE = tqcms.settings
├── tqcms/settings/
│   ├── base.py
│   ├── dev.py
│   └── production.py
└── home/                        # single Wagtail app — everything in one models.py
    ├── models.py                # 18 model classes (pages + data + admin)
    └── migrations/
```

Single app `home/` contains: Wagtail pages (HomePage, MusicIndexPage, RankingsPage,
etc.), data models (CmsArtista, CmsAlbum, CmsSong — unmanaged views), navigation,
theme/branding models, and admin forms. No separation of concerns.

### 2.3 Legacy scripts (not Django)

```
/root/TopQuaranta/scripts/
├── worker.py                    # 1,350-line monolith — DISABLED, the core problem
├── update_playlist_daily.py     # daily top 40 per territory + Spotify playlist
├── update_playlist_weekly.py    # weekly ranking generation (raw SQL INSERT ON CONFLICT)
├── generate_images.py           # ranking image rendering (PIL)
├── playlist_render_and_send.py  # Spotify playlist updates
├── bot_exclusions.py            # Telegram bot for exclusion management
├── update_from_viasona.py       # Viasona scraper (BeautifulSoup)
├── worker_update_artistes_viasona.py
└── worker_update_artistes_vmo.py

/root/TopQuaranta/utils/
├── imagens.py                   # 41KB — image generation + color palettes per territory
├── playlists.py                 # Spotify playlist ID mappings
├── logger.py
├── spotify_rate_guard.py
└── frases_instagram.py
```

### 2.4 Legacy database schema (actual state)

**Core tables:**

| Table | PK | Rows | Notes |
|---|---|---|---|
| `artistes` | `id_spotify` (varchar 50) | 6,477 (2,313 with status='go') | Main artist table |
| `cançons` | `(id_canco, territori)` composite | 11,555 active | Same track duplicated per territory! |
| `ranking_diari` | `(data, territori, posicio)` | 312,132 (2025-04-13 → 2026-03-09) | Daily snapshots — 126 MB |
| `ranking_setmanal` | `(data, territori, posicio)` | populated | Weekly results |
| `configuracio_global` | (single row) | 1 | 14 algorithm coefficients |
| `spotify_artists` | | | Spotify raw data — 3.4 MB |
| `spotify_albums` | | | Spotify raw data — 3.1 MB |
| `spotify_tracks` | | | Spotify raw data — 18 MB |
| `exclusions` | | | Track/album exclusion lists |
| `artistes_viasona` | | | Viasona enrichment data |
| `artistes_vmo` | | | VMO enrichment data |
| `cms_artists` | | | CMS denormalized view — 1.7 MB |
| `cms_albums` | | | CMS denormalized view (unmanaged) |
| `cms_songs` | | | CMS denormalized view (unmanaged) |

**Territory values in legacy (inconsistent):**
```
artistes.territori:  'Catalunya', 'País Valencià', 'Balears', 'Altres', 'Illes'
cançons.territori:   'cat', 'pv', 'ib', 'altres'
ranking views:       'cat', 'pv', 'ib', 'ppcc', 'altres'
```

**Key columns in `artistes`:**
```
id_spotify, nom, nom_spotify, imatge_url, popularitat, followers, generes,
status ('go'/'stop'/etc.), territori, català (boolean), localitat, comarca,
provincia, instagram, bio, web, youtube, tiktok, bluesky, bandcamp, deezer,
soundcloud, facebook, viquipedia, id_viasona, url_viasona, id_vmo, url_vmo,
data_actualitzacio, spotify_update, update_canco, font_dades
```

**Key columns in `cançons`:**
```
id_canco, territori, popularitat, titol, artistes (text[]), artista_basat,
exclosa (boolean), motiu_exclusio, artistes_ids (text[]), album_id,
album_titol, album_data, album_caratula_url, followers,
ultima_actualitzacio_spotify
```

**Key columns in `ranking_diari`:**
```
data, territori, posicio, id_canco, titol, artistes (text[]),
album_titol, popularitat, followers, artistes_ids (text[]),
album_id, album_data, album_caratula_url, canvi_posicio
```

### 2.5 The ranking algorithm — SQL views (not in code!)

The algorithm is NOT in Python. It lives as 5 PostgreSQL views:
`vw_top40_weekly_cat`, `vw_top40_weekly_pv`, `vw_top40_weekly_ib`,
`vw_top40_weekly_ppcc`, `vw_top40_weekly_altres`.

Each view is identical except for the territory filter. The CTE chain:

```
configuracio → dates → base → calculs_a → calcul_factor_a → amb_score_a
→ posicions_a → calculs_b → calcul_factor_b → amb_score_b → posicions_b
→ calculs_c → calcul_factor_c → amb_score_c → posicions_c
→ calcul_factor_final → amb_score_final → posicions_final
```

**How it works (summary):**
1. `configuracio`: reads coefficients from `configuracio_global` table
2. `dates`: computes current and previous ranking week boundaries
3. `base`: aggregates last 7 days of `ranking_diari` per track — computes
   `popularitat_mitjana`, `popularitat_inici` (days -7 to -5), `popularitat_final`
   (days -2 to 0), `dies_en_top`, `setmanes_top`, `antiguitat_dies`
4. `calculs_a` → `amb_score_a`: applies age penalty, descent penalty, stability
   weight, top-position penalty → produces `score_a`
5. `calculs_b` → `amb_score_b`: applies album monopoly and artist monopoly
   penalties → produces `score_b`
6. `calculs_c` → `amb_score_c`: applies new-entry bonus (weeks 0, 1, 2) →
   produces `factor_score_c`
7. `calcul_factor_final` → `amb_score_final`: applies smoothing factor based on
   position change → produces final `score_setmanal`
8. `posicions_final`: ranks by `score_setmanal` DESC, limits to top 40

**Input:** `ranking_diari.popularitat` (integer, 0–100, was Spotify popularity)
**Output:** ranked list with `score_setmanal`, `posicio`, `canvi_posicio`

**`configuracio_global` current values:**
```
dia_setmana_ranking              = 6      (Saturday)
penalitzacio_descens             = 0.025
exponent_penalitzacio_antiguitat = 2.5
max_factor_a                     = 1.0
max_factor_b                     = 1.0
max_factor_c                     = 1.0
max_factor_final                 = 1.5
penalitzacio_album_per_canco     = 0.25
penalitzacio_artista_per_canco   = 0.2
coeficient_penalitzacio_top      = 0.075
penalitzacio_setmana_0           = 0.1
penalitzacio_setmana_1           = 0.05
penalitzacio_setmana_2           = 0.0
suavitat                         = 5
```

### 2.6 Legacy SQL views (15 total)

```
vw_top40_cat, vw_top40_pv, vw_top40_ib, vw_top40_altres     (daily top 40)
vw_top40_weekly_cat, vw_top40_weekly_pv, vw_top40_weekly_ib,
vw_top40_weekly_ppcc, vw_top40_weekly_altres                  (weekly ranking — the algorithm)
vw_albums_recents, vw_cancons_caigudes, vw_novetats           (CMS helper views)
vw_geodata_artistes, artistes_discrepants, pending_update     (admin/maintenance views)
```

### 2.7 Legacy cron

```
0 * * * *    worker.sh              (hourly — DISABLED, was Spotify popularity)
0 */4 * * *  update_playlist_daily   (every 4h)
0 3 * * 6    update_playlist_weekly  (Saturday 03:00)
0 3 * * 0    send_telegram_pv
0 3 * * 1    send_telegram_album
0 3 * * 2    send_telegram_cat
0 3 * * 3    send_telegram_singles
0 3 * * 4    send_telegram_ib
```

### 2.8 Legacy .env keys (relevant subset)

```
DB_USER, DB_PASSWORD, DB_NAME, DB_HOST, DB_PORT
SPOTIPY_CLIENT_ID_WORKER_A1..E1  (7 credential pairs for rotation!)
SPOTIPY_CLIENT_SECRET_WORKER_A1..E1
SPOTIPY_CLIENT_ID_PLAYLIST, SPOTIPY_CLIENT_SECRET_PLAYLIST
SPOTIFY_REFRESH_TOKEN_PLAYLIST
TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
OPENAI_API_KEY
DJANGO_SECRET_KEY, DJANGO_DEBUG, DJANGO_ALLOWED_HOSTS
```

No Last.fm credentials exist yet — must be obtained from https://www.last.fm/api/account/create

---

## 3. Migration Strategy

### Principle: new project, same database

The new project connects to the same PostgreSQL database (`topquaranta`).
New tables are created via Django migrations alongside legacy tables.
Legacy tables are never modified by the new code — they are read-only references
during migration. Once a function is fully migrated and validated, the legacy
table/view can be dropped (Phase 8).

### What gets migrated vs. rebuilt

| Component | Strategy |
|---|---|
| `artistes` data | Migrated: new `Artista` model via one-off import script |
| `cançons` data | Migrated: new `Canco` model, deduplicated |
| `ranking_diari` data | NOT migrated: Spotify popularity data, useless for Last.fm |
| `ranking_setmanal` data | NOT migrated: regenerated from new signal |
| Ranking algorithm | Extracted from SQL views -> `ranking/algorisme.py` |
| `configuracio_global` | Migrated to Django model, same values |
| Spotify client | Rebuilt, blocked since 2024 (needs Premium). Kept as fallback |
| Last.fm client | New: primary signal source |
| Deezer client | New: primary metadata source (replaces Spotify) |
| Image generator | **Shelved indefinitely** — replaced by future web publica |
| Telegram bot | **Shelved indefinitely** — replaced by future web publica |
| CMS (Wagtail pages) | Will be rebuilt for new web publica (Phase 6) |

### Coexistence rules

- New project: `topquaranta`. Legacy: `tqcms`
- New tables: `music_artista`, `music_canco`, etc. Legacy tables untouched
- Legacy CMS at `/root/TopQuaranta/web_cms/` moved to `legacy.topquaranta.cat` (port 8081)
- New project runs pipeline + ranking + admin + public website (web/ app on port 8083)

---

## 3. New Project Structure

```
/home/topquaranta/app/             # new project root
├── manage.py
├── .env                           # single env file — NEVER commit
├── .env.example                   # all keys, empty values — committed
├── requirements.txt               # all production deps, pinned
├── requirements-dev.txt           # pytest, factory-boy, responses, etc.
├── pytest.ini
├── topquaranta/                   # Django project package
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   ├── production.py
│   │   ├── admin_server.py
│   │   └── test.py
│   ├── urls.py
│   └── wsgi.py
├── music/                         # core models: Artista, Album, Canco, HistorialRevisio
│   ├── models.py
│   ├── admin.py                   # CancoAdmin, ArtistaAdmin, ArtistaPendentAdmin
│   ├── ml.py                      # Random Forest + heuristic classifier
│   ├── verificacio.py             # crear_historial() — audit trail
│   ├── migrations/
│   └── tests/
├── ingesta/                       # all data pipeline code
│   ├── clients/
│   │   ├── deezer.py              # primary metadata source
│   │   ├── lastfm.py              # daily signal
│   │   └── spotify.py             # fallback (blocked)
│   ├── management/commands/
│   │   ├── obtenir_senyal.py      # daily Last.fm ingestion
│   │   ├── obtenir_novetats.py    # hourly Deezer incremental
│   │   ├── obtenir_metadata.py    # on-demand Deezer metadata
│   │   ├── actualitzar_score_entrada.py  # safety net backfill
│   │   ├── netejar_caducades.py   # daily cleanup
│   │   ├── importar_legacy.py     # one-off legacy import
│   │   └── ...                    # utility commands
│   └── tests/
├── ranking/                       # algorithm + signal storage
│   ├── models.py                  # ConfiguracioGlobal, SenyalDiari, RankingSetmanal, RankingProvisional
│   ├── admin.py                   # RankingProvisionalAdmin with rejection actions
│   ├── algorisme.py               # 14-CTE SQL extracted from legacy views
│   ├── management/commands/
│   │   └── calcular_ranking.py    # weekly official + daily provisional
│   └── tests/
├── web/                           # public website + staff panel
│   ├── views/
│   │   ├── __init__.py            # public views (homepage, ranking, artistes, mapa)
│   │   └── staff/                 # staff panel views (/staff/)
│   │       ├── __init__.py        # staff_required decorator, paginate() helper
│   │       ├── dashboard.py       # staff landing page
│   │       └── urls.py            # staff URL routing
│   ├── urls.py
│   ├── context_processors.py      # current_year for templates
│   ├── templates/web/
│   │   ├── base.html              # base template loading mm-design tokens
│   │   ├── homepage.html          # Top 40 ranking page
│   │   └── staff/                 # staff panel templates
│   │       ├── base_staff.html    # staff layout (extends base.html)
│   │       ├── confirmar_accio.html  # reusable confirmation page
│   │       └── dashboard.html     # staff landing page
│   └── static/web/css/
│       └── style.css              # site CSS consuming mm-design tokens
├── comptes/                       # user accounts + artist verification portal
│   ├── models.py                  # Usuari(AbstractUser), UserArtista
│   ├── views.py                   # registre, login, dashboard, portal artista
│   ├── forms.py                   # RegistreForm, SollicitudArtistaForm
│   ├── admin.py                   # UserArtistaAdmin
│   ├── wagtail_hooks.py           # UserArtistaViewSet (snippet)
│   └── templates/comptes/
├── distribucio/                   # SHELVED — placeholder only
│   └── (empty models/admin/views)
└── legacy/                        # read-only Django models for legacy tables
    ├── models.py                  # unmanaged models pointing to legacy tables
    └── README.md
```

---

## 4. Environment Variables (.env)

```dotenv
# Django
DJANGO_SECRET_KEY=
DJANGO_SETTINGS_MODULE=topquaranta.settings.production
ALLOWED_HOSTS=topquaranta.cat,www.topquaranta.cat
DEBUG=False

# Database (same DB as legacy — coexistence)
DATABASE_URL=postgres://topquaranta:PASSWORD@localhost:5432/topquaranta

# Spotify (fallback — blocked since 2024)
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=

# Last.fm (primary signal source)
LASTFM_API_KEY=
LASTFM_API_SECRET=
```

Load with `python-decouple`. Always read via `from django.conf import settings`.

---

## 5. Design System (mm-design)

The public website uses **mm-design** (`github.com/miquelmatoses/mm-design`), a
centralized design token system shared across all Miquel Matoses projects.

### Installation

Installed as an npm git dependency. No build step required.

```bash
npm install                        # reads package.json, installs to node_modules/
```

`package.json` at project root declares: `"mm-design": "github:miquelmatoses/mm-design"`.

### Django integration

```python
# settings/base.py
STATICFILES_DIRS = [
    ("mm-design", BASE_DIR / "node_modules" / "mm-design"),
]
```

In templates, load tokens via `{% static %}`:

```html
<link rel="stylesheet" href="{% static 'mm-design/tokens/colors.css' %}">
<link rel="stylesheet" href="{% static 'mm-design/tokens/typography.css' %}">
<link rel="stylesheet" href="{% static 'mm-design/tokens/spacing.css' %}">
```

After install or update: `python manage.py collectstatic --noinput`.

### Rules (enforced by mm-design/CLAUDE.md)

1. **Tokens**: all colors, fonts, spacing, and shadows come from mm-design. Never hardcode hex values.
2. **Fonts**: Playfair Display (headings), Roboto (body). Loaded via Google Fonts `@import` in `typography.css`.
3. **Naming**: all CSS custom properties use `--mm-[category]-[name]` (e.g. `--mm-color-primary`).
4. **Brand colors**: red (`--mm-color-primary`), blue, yellow, green. Never place two brand colors directly on each other — always brand color + white or brand color + black.
5. **Updating**: `npm update mm-design && python manage.py collectstatic --noinput`.

---

## 6. Testing

```ini
# pytest.ini
[pytest]
DJANGO_SETTINGS_MODULE = topquaranta.settings.test
python_files = tests/test_*.py
python_classes = Test*
python_functions = test_*
```

Coverage target: >= 70% on `ingesta/` and `ranking/`.
Mock all external HTTP — never make real API calls in tests.
Use `@pytest.mark.django_db` for any test touching the DB.

---

## 7. Code Conventions

- No `print()` -> `logging` or `self.stdout.write()`
- No `sys.exit()` -> `raise CommandError(...)`
- No `TRUNCATE` -> Django ORM deletes inside `transaction.atomic()`
- No raw DDL outside migrations
- No raw psycopg2 — always Django ORM (except `algorisme.py` raw SQL via `connection.cursor()`)
- All DB writes in `transaction.atomic()`
- Type hints on all new functions
- f-strings preferred in code, `%s` formatting in logger calls
- black + isort formatting
- Comments and docstrings: English only

### Development environment

Claude Code runs directly on the Hetzner production server (CX22, 188.245.60.20).
No separate local development environment.

- Working directory: `/home/topquaranta/app/`
- Direct access to the production PostgreSQL database
- Virtualenv: `/home/topquaranta/app/.venv/`

### Git workflow

Claude Code (server) -> `git push` -> GitHub (source of truth).
Always pull before pushing if remote has diverged (`git pull --rebase`).
GitHub is canonical; server is just the active checkout.

### Roadmap tracking

At the end of every work session, update `ROADMAP.md` to reflect the real state.

---

## 8. Key Decisions and Rationale

| Decision | Rationale |
|---|---|
| New project, not incremental cleanup | Legacy has incompatible PKs, no tests, no migrations, monolithic scripts |
| Same database, coexistence | Zero data loss risk; legacy CMS continues running; rollback possible |
| Last.fm as signal source | Spotify popularity deprecated Nov 2024; Last.fm has public playcount + listeners |
| Deezer as metadata source | Spotify API requires Premium (403 since 2024). Deezer is public, 100% ISRC |
| Algorithm extracted, not rewritten | Well-founded 14-CTE logic; port to Python, adapt inputs, keep math identical |
| Territory on artist (M2M), not track | Legacy duplicated tracks per territory. Territory is a property of the artist |
| Image generation shelved | Original assets inaccessible. Distribution will be via web publica instead |
| Human approval for all auto-discovered artists | Prevents false positives (Marató, one-off collabs) |
| ISRC on every Canco | Universal cross-system key; enables future integrations |
| 12-month track cutoff | TopQuaranta tracks current music, not back-catalogue |
| No Celery | Daily/weekly cron is sufficient; avoids broker complexity |
| Legacy code is reference only | Never import, never subclass — read, understand, reimplement cleanly |
