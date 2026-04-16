# CLAUDE.md — TopQuaranta

> Persistent memory for Claude Code. Read this file first on every session.
> Last updated: 2026-04-16 — Post-Phase-8 audit & consolidation.

## Other docs
- **`CLAUDE_MODELS.md`** — every Django model with fields, relations, indexes.
- **`CLAUDE_PIPELINE.md`** — ingest → signal → ranking flow, API clients, crons.
- **`CLAUDE_STAFF.md`** — staff panel architecture, views, permissions, flows.
- **`CLAUDE_ALGORITHM.md`** — 14-CTE ranking algorithm details.
- **`CLAUDE_LEGACY.md`** — historical audit of the pre-2026 system (reference only).
- **`ROADMAP.md`** — phase status; current state and next steps.

---

## 1. Project

TopQuaranta (`topquaranta.cat`) is a weekly music ranking for Catalan-language
music across 10 territories: `CAT`, `VAL`, `BAL`, `PPCC` (aggregate), `ALT`,
`CNO`, `AND`, `FRA`, `ALG`, `CAR`. Cultural mission: show that Catalan-language
music is alive and growing.

**Signal source:** Last.fm (`playcount` + `listeners`, normalized via
`percentileofscore`). **Metadata source:** Deezer (public, ISRC on every track).
Spotify is a dead fallback (blocked since 2024, needs Premium).

**Image generation + Telegram distribution: indefinitely shelved.** Original
assets inaccessible. The public website is the distribution channel instead.

## 2. Infrastructure

- **Server:** Hetzner CX22 (`188.245.60.20`), Ubuntu 22.04.
- **Runtime:** Python 3.10, Django 5.2, PostgreSQL 14.
- **Reverse proxy:** Caddy (auto TLS). Config: `/etc/caddy/Caddyfile`.
- **Process:** `topquaranta-web.service` → gunicorn :8083, settings
  `topquaranta.settings.web_server`, user `topquaranta`. Single gunicorn serves
  the public web **and** the staff panel.
- **DB:** `topquaranta` on localhost, user `topquaranta`. 25 tables, 44 MB.
- **Working dir:** `/home/topquaranta/app/`. Virtualenv: `.venv/`.
- **Repo:** `github.com/miquelmatoses/TopQuaranta` (private).

Legacy Wagtail code is preserved read-only at `/root/TopQuaranta/` but the
service is stopped and disabled. Port 8081 is free.

## 3. Project structure

```
/home/topquaranta/app/
├── manage.py
├── .env                 # never commit
├── package.json         # declares mm-design npm git dep
├── topquaranta/         # Django project
│   ├── settings/        # base.py, production.py, web_server.py, local.py, test.py
│   └── urls.py
├── music/               # Artista, Album, Canco, Municipi, ArtistaLocalitat, HistorialRevisio,
│   │                    # Territori, ArtistaDeezer + constants, ml.py, services.py, verificacio.py
│   ├── models.py
│   └── migrations/      # 26 migrations
├── ingesta/             # pipeline code only
│   ├── clients/         # deezer.py, lastfm.py, spotify.py (fallback), viasona.py (stub)
│   └── management/commands/  # obtenir_novetats, obtenir_senyal, obtenir_metadata, netejar_caducades, ...
├── ranking/             # ConfiguracioGlobal, SenyalDiari, RankingSetmanal, RankingProvisional
│   ├── algorisme.py     # 14-CTE SQL + PPCC aggregation
│   └── management/commands/calcular_ranking.py
├── web/                 # public website + staff panel
│   ├── views/
│   │   ├── __init__.py  # public views (homepage, ranking, artistes, mapa, artist/album/canco profiles)
│   │   └── staff/       # dashboard, cancons, albums, ranking, artistes, pendents, eines — see CLAUDE_STAFF.md
│   ├── api/             # /api/v1/ — DRF map endpoint + location reference API
│   ├── templates/web/
│   │   ├── base.html
│   │   └── staff/       # base_staff, _pagination, _select_all, + one template per page
│   └── static/web/css/style.css
├── comptes/             # Usuari (custom user), UserArtista, PropostaArtista, solicitud flows
├── scripts/             # ad-hoc analysis scripts (not management commands)
└── backups/             # pg_dump snapshots (owned by postgres)
```

## 4. Design system (mm-design)

Single source of truth: `github.com/miquelmatoses/mm-design`. Installed as an
npm git dependency; `STATICFILES_DIRS` points to `node_modules/mm-design/`.
Tokens loaded in `base.html` via `{% static 'mm-design/tokens/*.css' %}`.

**Rules:**
1. All colors, fonts, spacing, shadows come from `var(--mm-*)`. **Never hardcode
   hex values** in templates, inline styles, or CSS. One acceptable fallback:
   chaining `var(--mm-color-white)` after `var(--mm-color-background)`.
2. Fonts: Playfair Display (headings), Roboto (body). No others.
3. Brand colors never touch directly — always brand + white or brand + black.
4. Territory accent: `--tq-accent` set by body class `territori-<code>`.
5. After `npm update`, run `python manage.py collectstatic --noinput`.

## 5. Key decisions

| Decision | Rationale |
|---|---|
| Last.fm as signal | Spotify popularity deprecated 2024-11; Last.fm has public playcount + listeners. |
| Deezer as metadata | Spotify API 403 (Premium). Deezer public + 100% ISRC. |
| Algorithm ported, not rewritten | 14-CTE SQL from legacy views → Python in `ranking/algorisme.py`, same math. |
| PPCC aggregates, not computes | Takes top 40 of each non-aggregate territory, applies position penalty `score × (1 - (pos-1)·0.04)`, dedupes by canco. |
| Territory on artist (M2M), not track | Legacy duplicated tracks per territory. Territory auto-syncs from `ArtistaLocalitat → Municipi → Territori`. |
| Human approval for every auto-discovered artist | Prevents false positives (metal "Aion", anime "Animal"). |
| ISRC on every Canco | Universal key; enables future cross-system integrations. |
| 12-month track cutoff | Current music only (`DIES_CADUCITAT` in `music/constants.py`). |
| No Celery | Daily/weekly cron is enough; avoids broker complexity. |
| Single gunicorn | Public + staff in one process; `@staff_required` gates `/staff/*`. |
| Legacy DB reference only | All legacy tables dropped in Phase 8 (see `ROADMAP.md`). |

## 6. Shared constants

Import from `music/constants.py` rather than duplicating:
- `DIES_CADUCITAT = 365`, `MAX_POSICIONS_TOP = 40`
- `TERRITORI_NOMS` (dict), `TERRITORIS_VALIDS` (tuple of ranking-eligible codes)
- `ML_CLASSE_A_THRESHOLD`, `ML_CLASSE_B_THRESHOLD`, `MIN_TRAINING_SAMPLES`,
  `MIN_NEW_DECISIONS`
- `DEEZER_RATE_LIMIT`, `LASTFM_RATE_LIMIT`, `MAX_API_RETRIES`
- `MOTIUS_REBUIG`, `MOTIUS_VALIDS`

## 7. Environment (.env)

```dotenv
DJANGO_SECRET_KEY=
DJANGO_SETTINGS_MODULE=topquaranta.settings.production
ALLOWED_HOSTS=topquaranta.cat,www.topquaranta.cat
DEBUG=False
DATABASE_URL=postgres://topquaranta:PASSWORD@localhost:5432/topquaranta
LASTFM_API_KEY=
LASTFM_API_SECRET=
SPOTIFY_CLIENT_ID=   # fallback only
SPOTIFY_CLIENT_SECRET=
```

Loaded via `python-decouple`. Always access via `from django.conf import settings`.

## 8. Testing

```ini
# pytest.ini
DJANGO_SETTINGS_MODULE = topquaranta.settings.test
python_files = tests/test_*.py
```

Mock all external HTTP — no real API calls in tests.
Run: `.venv/bin/python -m pytest -q`.

## 9. Code conventions

- No `print()` → `logging` or `self.stdout.write()`.
- No `sys.exit()` → `raise CommandError(...)`.
- No `TRUNCATE` or raw DDL outside migrations.
- No raw psycopg2 — always Django ORM (exception: `ranking/algorisme.py` uses
  raw SQL via `connection.cursor()` for the 14-CTE).
- All DB writes inside `transaction.atomic()`.
- Type hints on new functions. `f-strings` in code, `%s` in `logger` calls.
- black + isort. Comments and docstrings in English.
- Catalan for user-facing strings (templates, messages, labels).

## 10. Workflow

Claude Code runs on the production server. GitHub is canonical:
`git pull --rebase` before pushing. Never commit without explicit request.
At the end of each session, update `ROADMAP.md` to reflect reality.
