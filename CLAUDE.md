# CLAUDE.md — TopQuaranta System Architecture

> Persistent memory for Claude Code. Read this file before making any change.
> Last updated: 2026-04-14 — Phase 5 done, reestructura docs
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

**Current state (2026-04-14):** the pipeline (ingesta -> senyal -> ranking) is
operational. Weekly Top 40 published via ranking provisional admin. Distribution
via web publica is a future phase.

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

---

## 2. Migration Strategy

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
- Legacy CMS at `/root/TopQuaranta/web_cms/` keeps running until Phase 6
- New project runs pipeline + ranking + admin. Does NOT serve public website yet

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

## 5. Testing

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

## 6. Code Conventions

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

## 7. Key Decisions and Rationale

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
