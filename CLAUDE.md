# CLAUDE.md — TopQuaranta System Architecture

> Persistent memory for Claude Code. Read this file before making any change.
> Last updated: 2026-04-11 — ISRC matching + location fields
>
> See **ROADMAP.md** for implementation status.

> **Strategy: new project, same database.**
> The legacy codebase (`/root/TopQuaranta/`) is a reference, not a starting point.
> The new project is built from scratch with clean structure, connecting to the
> existing PostgreSQL database. Legacy tables coexist with new ones until each
> function is fully migrated and validated. Legacy code is never imported — only
> read, understood, and reimplemented cleanly.

---

## 1. Project Overview

TopQuaranta (topquaranta.cat) is a weekly music ranking system for Catalan-language
music across three territories: Catalunya (CAT), País Valencià (VAL), and
Illes Balears (BAL). Cultural mission: demonstrate that Catalan-language music is
alive and growing. Weekly Top 40 published via Telegram and a public Wagtail website.

### Why this refactor

The previous system used Spotify `popularity` (0–100), deprecated for Development
Mode apps in November 2024. The old `worker.py` (1,350-line monolith with TRUNCATE,
no transactions, sys.exit() throughout) is disabled. This is a full rewrite.

**New signal source:** Last.fm — `playcount` (cumulative total plays) and
`listeners` (unique listeners). Raw values stored daily. The exact normalization
formula that maps these to the existing algorithm's `score_entrada` field is
**deferred until we have real data** to inspect (see Phase 3).

### Infrastructure

- Server: Hetzner CX22, Ubuntu 22.04, IP 188.245.60.20
- Reverse proxy: Caddy (auto TLS)
- Database: PostgreSQL 14 (local), DB name `topquaranta`, user `topquaranta`
- Runtime: Python 3.10
- Legacy: Django 5.1.11, Wagtail 6.4.2 (to be upgraded)
- Target: Django 5.2, Wagtail 7.0
- Repo: https://github.com/miquelmatoses/TopQuaranta (private)
- Process user: `topquaranta` (non-root, to be created in Phase 0)

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
table/view can be dropped (Phase 6).

### What gets migrated vs. rebuilt

| Component | Strategy |
|---|---|
| `artistes` data | Migrated: new `Artista` model reads from legacy via one-off import script |
| `cançons` data | Migrated: new `Canco` model, deduplicated (remove territory duplication) |
| `ranking_diari` data | NOT migrated: 126 MB of Spotify popularity data, useless for Last.fm |
| `ranking_setmanal` data | NOT migrated: will be regenerated from new signal |
| Ranking algorithm | Extracted from SQL views → Python in `ranking/algorisme.py` |
| `configuracio_global` | Migrated to Django model, same values |
| Spotify client | Rebuilt clean: 1 credential pair, individual calls only |
| Last.fm client | New: does not exist in legacy |
| Viasona scraper | Audited and rebuilt from `scripts/update_from_viasona.py` |
| Image generator | Audited and rebuilt from `utils/imagens.py` |
| Telegram bot | Rebuilt from `scripts/generate_images.py` + bot code |
| CMS (Wagtail pages) | Deferred: website continues running on legacy until Phase 5 |

### Coexistence rules

- New project uses a **different Django project name** (`topquaranta`) vs legacy (`tqcms`)
- New tables get Django-standard names (`music_artista`, `music_canco`, etc.)
- Legacy tables (`artistes`, `cançons`, `ranking_diari`, etc.) are untouched
- The legacy CMS at `/root/TopQuaranta/web_cms/` keeps running during migration
- The new project does NOT serve the website initially — only runs pipeline + ranking
- When the new pipeline is producing valid rankings, the CMS switches to read from
  new tables (Phase 5)

---

## 4. New Project Structure

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
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── music/                         # core models: Artista, Album, Canco
│   ├── migrations/
│   ├── models.py
│   ├── admin.py
│   └── tests/
├── ingesta/                       # all data pipeline code
│   ├── clients/
│   │   ├── spotify.py             # metadata only (individual calls)
│   │   ├── lastfm.py              # daily signal
│   │   └── viasona.py             # scraper for artist discovery
│   ├── management/commands/
│   │   ├── ingestar_metadata.py
│   │   ├── ingestar_senyal.py
│   │   ├── descobrir_artistes.py
│   │   └── importar_legacy.py     # one-off: import artistes + cançons from legacy
│   ├── pipeline.py
│   └── tests/
├── ranking/                       # algorithm + signal storage
│   ├── migrations/
│   ├── models.py                  # IngestaDiari, RankingSetmanal, ConfiguracioGlobal
│   ├── management/commands/
│   │   └── calcular_ranking.py
│   ├── algorisme.py               # 14-CTE SQL extracted from legacy views
│   ├── senyal.py                  # DEFERRED: formula to compute score_entrada
│   └── tests/
├── distribucio/                   # Telegram + image generation
│   ├── telegram_bot.py
│   ├── image_generator.py
│   ├── management/commands/
│   │   └── distribuir_ranking.py
│   └── tests/
└── legacy/                        # read-only Django models for legacy tables
    ├── models.py                  # unmanaged models pointing to legacy tables
    └── README.md                  # "These models are read-only. Do not migrate."
```

---

## 5. Data Models

All new models under Django migrations. Never use raw DDL outside migrations.

### music/models.py

```python
from django.db import models


class Territori(models.Model):
    """
    Territory for Catalan-language music rankings.
    Fixed set: CAT, VAL, BAL. Managed via data migration, not admin.
    """

    codi = models.CharField(max_length=3, primary_key=True)
    nom = models.CharField(max_length=50)

    class Meta:
        ordering = ["codi"]
        verbose_name = "Territori"
        verbose_name_plural = "Territoris"

    def __str__(self) -> str:
        return self.nom


class Artista(models.Model):
    """
    A music artist tracked by TopQuaranta.

    Territory is a manually curated field — Last.fm has no geographic signal.
    Artists can belong to multiple territories via M2M (e.g. Marala → CAT, VAL, BAL).
    A track appears in territory T if ANY of its artists (main or collaborator)
    belongs to T.
    """

    spotify_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    deezer_id = models.BigIntegerField(unique=True, null=True, blank=True)
    lastfm_nom = models.CharField(
        max_length=255,
        help_text="Exact name for Last.fm API calls (case-sensitive).",
    )
    lastfm_mbid = models.CharField(
        max_length=50, blank=True, null=True,
        help_text="MusicBrainz ID — improves Last.fm lookup accuracy.",
    )
    nom = models.CharField(max_length=255)
    territoris = models.ManyToManyField(
        Territori, related_name="artistes", blank=True,
        help_text="Territories this artist belongs to. Tracks appear in all.",
    )
    deezer_no_trobat = models.BooleanField(
        default=False,
        help_text="True if Deezer search failed ISRC validation — skip in future runs.",
    )
    # Discovery provenance
    auto_descobert = models.BooleanField(default=False)
    font_descoberta = models.CharField(
        max_length=50, blank=True,
        help_text="Source that proposed this artist: 'viasona', 'collaborador', 'manual'.",
    )
    aprovat = models.BooleanField(
        default=True,
        help_text="False = pending human review in Wagtail admin.",
    )
    # Location (from legacy artistes table)
    localitat = models.CharField(max_length=255, blank=True)
    comarca = models.CharField(max_length=255, blank=True)
    provincia = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Artista"
        verbose_name_plural = "Artistes"

    def __str__(self) -> str:
        codis = ",".join(self.territoris.values_list("codi", flat=True))
        return f"{self.nom} ({codis})" if codis else self.nom

    def get_territoris(self) -> list[str]:
        """Return list of territory codes for this artist."""
        return list(self.territoris.values_list("codi", flat=True))


class Album(models.Model):
    TIPUS_CHOICES = [
        ("album", "Àlbum"),
        ("single", "Single"),
        ("ep", "EP"),
    ]

    spotify_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    artista = models.ForeignKey(Artista, on_delete=models.CASCADE, related_name="albums")
    nom = models.CharField(max_length=500)
    data_llancament = models.DateField(null=True, blank=True)
    tipus = models.CharField(max_length=10, choices=TIPUS_CHOICES, default="album")
    imatge_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-data_llancament"]

    def __str__(self) -> str:
        return f"{self.nom} — {self.artista.nom}"


class Canco(models.Model):
    """
    A single track. Only tracks released within the last 12 months are ingested.

    In the new model, a track exists ONCE (not duplicated per territory like legacy).
    Territory is derived from the artists:
      - artista: main artist (FK, for display and default lookups)
      - artistes_col: collaborating artists (M2M)
    A track appears in territory T if ANY artist (main or collaborator) belongs to T.

    Examples:
      - Txarango (CAT) + La Fumiga (VAL) collab → track in CAT and VAL rankings
      - Marala (CAT, VAL, BAL) solo → track in all 3 rankings

    ISRC is the universal cross-system identifier:
      Spotify → ISRC → Last.fm / MusicBrainz (future cross-referencing)
    """

    spotify_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    isrc = models.CharField(
        max_length=15, blank=True,
        help_text="International Standard Recording Code — cross-system key.",
    )
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="cancons")
    artista = models.ForeignKey(
        Artista, on_delete=models.CASCADE, related_name="cancons",
        help_text="Main artist (for display). Territory also from collaborators.",
    )
    artistes_col = models.ManyToManyField(
        Artista, related_name="participacions", blank=True,
        help_text="Collaborating artists. Track appears in their territories too.",
    )
    nom = models.CharField(max_length=500)
    lastfm_nom = models.CharField(
        max_length=500, blank=True,
        help_text="Track name as returned by Last.fm (may differ from Spotify).",
    )
    lastfm_mbid = models.CharField(max_length=50, blank=True)
    lastfm_verificat = models.BooleanField(default=False)
    durada_ms = models.IntegerField(null=True, blank=True)
    data_llancament = models.DateField(
        null=True, blank=True,
        help_text="Tracks older than 12 months are excluded from ingestion.",
    )
    activa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Cançó"
        verbose_name_plural = "Cançons"

    def __str__(self) -> str:
        return f"{self.nom} — {self.artista.nom}"

    @property
    def lastfm_lookup_nom(self) -> str:
        """Return the best name for Last.fm API calls."""
        return self.lastfm_nom if self.lastfm_nom else self.nom

    def get_territoris(self) -> set[str]:
        """
        Return all territories this track should appear in.
        Union of main artist's territories + all collaborators' territories.
        """
        codis = set(self.artista.territoris.values_list("codi", flat=True))
        codis.update(
            Territori.objects.filter(
                artistes__participacions=self
            ).values_list("codi", flat=True)
        )
        return codis
```

### ranking/models.py

```python
from django.db import models
from music.models import Canco


class ConfiguracioGlobal(models.Model):
    """
    Ranking algorithm coefficients. Single-row table.
    Migrated from legacy `configuracio_global` table.
    """

    dia_setmana_ranking = models.IntegerField(default=6)
    penalitzacio_descens = models.DecimalField(max_digits=5, decimal_places=3, default=0.025)
    exponent_penalitzacio_antiguitat = models.DecimalField(max_digits=5, decimal_places=2, default=2.5)
    max_factor_a = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    max_factor_b = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    max_factor_c = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    max_factor_final = models.DecimalField(max_digits=5, decimal_places=2, default=1.5)
    penalitzacio_album_per_canco = models.DecimalField(max_digits=5, decimal_places=3, default=0.25)
    penalitzacio_artista_per_canco = models.DecimalField(max_digits=5, decimal_places=3, default=0.2)
    coeficient_penalitzacio_top = models.DecimalField(max_digits=5, decimal_places=3, default=0.075)
    penalitzacio_setmana_0 = models.DecimalField(max_digits=5, decimal_places=3, default=0.1)
    penalitzacio_setmana_1 = models.DecimalField(max_digits=5, decimal_places=3, default=0.05)
    penalitzacio_setmana_2 = models.DecimalField(max_digits=5, decimal_places=3, default=0.0)
    suavitat = models.DecimalField(max_digits=5, decimal_places=2, default=5.0)

    class Meta:
        verbose_name = "Configuració global"
        verbose_name_plural = "Configuració global"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class IngestaDiari(models.Model):
    """
    Daily Last.fm snapshot per track.

    Stores raw cumulative values (not deltas — algorithm computes those).
    One row per (canco, data). Use update_or_create — never insert duplicates.

    score_entrada is the normalized value fed to the ranking algorithm.
    It is NULL until Phase 3 defines the normalization formula.
    """

    canco = models.ForeignKey(Canco, on_delete=models.CASCADE, related_name="ingestes")
    data = models.DateField()

    # Raw Last.fm cumulative values
    lastfm_playcount = models.BigIntegerField(null=True)
    lastfm_listeners = models.IntegerField(null=True)

    # Normalized signal fed to the ranking algorithm.
    # Formula defined in Phase 3 after inspecting real data distributions.
    score_entrada = models.FloatField(
        null=True,
        help_text="Normalized score (0–100) for the ranking algorithm. NULL until formula defined.",
    )

    error = models.BooleanField(default=False)
    error_msg = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("canco", "data")]
        ordering = ["-data"]
        indexes = [
            models.Index(fields=["canco", "data"]),
            models.Index(fields=["data", "error"]),
        ]

    def __str__(self) -> str:
        return f"{self.canco} — {self.data}"


class RankingSetmanal(models.Model):
    """
    Weekly ranking result. setmana = Monday of the ranking week (ISO).
    Column names mirror the existing 14-CTE algorithm output.
    """

    TERRITORI_CHOICES = [
        ("CAT", "Catalunya"),
        ("VAL", "País Valencià"),
        ("BAL", "Illes Balears"),
    ]

    canco = models.ForeignKey(Canco, on_delete=models.CASCADE, related_name="rankings")
    territori = models.CharField(max_length=3, choices=TERRITORI_CHOICES)
    setmana = models.DateField()
    posicio = models.PositiveSmallIntegerField()
    score_setmanal = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("canco", "territori", "setmana")]
        ordering = ["territori", "posicio"]
        indexes = [models.Index(fields=["setmana", "territori"])]

    def __str__(self) -> str:
        return f"#{self.posicio} {self.canco.nom} ({self.territori}) — {self.setmana}"
```

### legacy/models.py (read-only, unmanaged)

```python
from django.db import models


class LegacyArtista(models.Model):
    """Read-only access to legacy `artistes` table for data migration."""

    id_spotify = models.CharField(max_length=50, primary_key=True)
    nom = models.CharField(max_length=255, null=True)
    nom_spotify = models.TextField(null=True)
    territori = models.CharField(max_length=50, null=True)
    status = models.CharField(max_length=20, null=True)
    catala = models.BooleanField(db_column="català", null=True)
    localitat = models.CharField(max_length=255, null=True)
    comarca = models.CharField(max_length=255, null=True)
    id_viasona = models.TextField(null=True)
    font_dades = models.CharField(max_length=255, null=True)

    class Meta:
        managed = False
        db_table = "artistes"


class LegacyCanco(models.Model):
    """Read-only access to legacy `cançons` table for data migration."""

    id_canco = models.CharField(max_length=50)
    territori = models.CharField(max_length=50)
    titol = models.TextField(null=True)
    artista_basat = models.TextField(null=True)
    album_id = models.CharField(max_length=50, null=True)
    album_titol = models.TextField(null=True)
    album_data = models.DateField(null=True)
    album_caratula_url = models.TextField(null=True)
    exclosa = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "cançons"
        unique_together = [("id_canco", "territori")]
```

---

## 6. The Ranking Algorithm

### Do not rewrite the algorithm logic — extract and adapt it.

The 14-CTE SQL currently lives inside PostgreSQL views (not versioned).
Phase 4 extracts it into `ranking/algorisme.py` as a parameterized Python function
that executes the SQL. The algorithm logic stays identical. Changes:

- Input: `score_entrada` from `IngestaDiari` (was `popularitat` from `ranking_diari`)
- Coefficients: read from `ConfiguracioGlobal` Django model (was `configuracio_global` raw table)
- Territory codes: `CAT`/`VAL`/`BAL` (was `cat`/`pv`/`ib` strings)
- Output: written to `RankingSetmanal` via Django ORM (was raw INSERT ON CONFLICT)

**Adaptation checklist:**
- [ ] Extract SQL from `vw_top40_weekly_cat` view definition
- [ ] Parameterize territory (single SQL, territory as parameter)
- [ ] Replace `ranking_diari` references → `ranking_ingestadiari`
- [ ] Replace `popularitat` → `score_entrada`
- [ ] Replace `configuracio_global` → `ranking_configuracionglobal`
- [ ] Replace `ranking_setmanal` references → `ranking_rankingsetmanal`
- [ ] Wrap in `transaction.atomic()`
- [ ] After Phase 3 data, run and inspect output
- [ ] Adjust coefficients only if distribution looks broken (small tweaks only)

### Phase 3 — Signal formula (DEFERRED)

After collecting 2–3 weeks of real Last.fm data, write an analysis script
(not a management command — a one-off exploration) that prints:

```
- min, max, median, p10, p90 of lastfm_playcount across the catalog
- min, max, median, p10, p90 of lastfm_listeners
- weekly delta distribution (playcount today - playcount 7 days ago)
- example: compare known big artist vs known small local artist
```

Then decide on the formula in conversation. Candidate options:

```
A) score = log10(playcount + 1) / log10(catalog_max + 1) * 100
   → absolute scale; Rosalía is #1 if she has the most plays — that is fine
B) score = percent_rank(playcount_within_week) * 100
   → relative; always produces spread 0–100 regardless of scale
C) score = 0.7 * percent_rank(delta_7d) + 0.3 * percent_rank(listeners)
   → rewards weekly momentum more than accumulated catalogue plays
```

The chosen formula goes in `ranking/senyal.py::calcular_score_entrada()`.
After definition, run `actualitzar_score_entrada` to backfill all existing rows.

```python
# ranking/senyal.py — placeholder until Phase 3

def calcular_score_entrada(playcount: int, listeners: int, **kwargs) -> float:
    """
    Compute the normalized score (0–100) fed to the ranking algorithm.
    Formula to be determined in Phase 3 after inspecting real data.
    """
    raise NotImplementedError("Phase 3: define after inspecting real data distribution.")
```

---

## 7. Artist Discovery Pipeline

Multiple sources feed a shared candidate queue (artists with `aprovat=False`).
A human approves or rejects each candidate via Wagtail admin before the artist
enters any ranking. This is the quality gate against false positives.

### 7.1 Viasona scraper (primary source)

Viasona (viasona.cat) is a Catalan-language music platform.

**Legacy code:** `scripts/update_from_viasona.py` — scrapes
`https://www.viasona.cat/grup/{slug}` with BeautifulSoup. Extracts localitat,
comarca, Instagram. Used for enrichment, not discovery.

**Known problem:** the TV3 Marató (charity marathon) causes non-Catalan artists
to appear in Viasona. The human approval step catches these.

**Action:** audit legacy code, rebuild in `ingesta/clients/viasona.py`.

### 7.2 Collaborator detection (Spotify featured-artist heuristic)

If artist X appears as a featured collaborator on N tracks by already-approved
Catalan artists (across distinct artists), X is probably also a Catalan-language artist.

Threshold: N ≥ 3 appearances across at least 2 distinct approved artists.
Creates: `Artista(aprovat=False, font_descoberta='collaborador')`.

### 7.3 Manual entry (Wagtail admin)

Always available. Any admin adds an artist directly with `aprovat=True`.

### Discovery flow (end-to-end)

```
Viasona scraper          ─┐
Collaborator detection   ─┼─→  Artista(aprovat=False, font_descoberta=...)
Manual Wagtail entry     ─┘         (or aprovat=True for manual)
                                           │
                              Human review in Wagtail admin
                              (default filter: aprovat=False)
                                           │
                              Approve → aprovat=True
                              Reject  → aprovat=False (keep, avoids re-discovery)
                                           │
                              ingestar_metadata command
                              Deezer: tracks released in last 12 months
                              Store ISRC on each Canco
                                           │
                              ingestar_senyal starts collecting daily Last.fm data
```

### Deezer metadata scope (approved artists only)

- Only fetch tracks with `data_llancament >= today - 365 days`
- Deezer API is public, no authentication needed
- Artist matching: normalized name match → ISRC cross-validation
- If ISRC validation fails, artist is marked `deezer_no_trobat=True` and skipped
- Store `isrc` on every `Canco` (Deezer provides 100% ISRC coverage)
- Store `deezer_id` on `Artista`, `Album`, and `Canco`
- Spotify client kept as fallback but currently blocked (needs Premium)

---

## 8. API Clients

### 8.1 Last.fm (ingesta/clients/lastfm.py)

**Endpoint:** `GET https://ws.audioscrobbler.com/2.0/?method=track.getInfo`

Required params: `api_key`, `artist`, `track`, `format=json`, `autocorrect=1`

Returns: `track.playcount` (cumulative ever), `track.listeners` (unique ever).

Rate limit: max 5 req/sec → `time.sleep(0.2)` between calls.
Retry: 3 attempts with exponential backoff (`2 ** attempt` seconds) on network errors.
Never raise on failure — return `None`.

```python
import logging
import time
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"
RATE_LIMIT_SLEEP = 0.2
MAX_RETRIES = 3


def get_track_info(artist_name: str, track_name: str) -> dict | None:
    """
    Fetch cumulative playcount and listeners for a track from Last.fm.
    Returns {'playcount': int, 'listeners': int} or None on any failure.
    Never raises.
    """
    params = {
        "method": "track.getInfo",
        "api_key": settings.LASTFM_API_KEY,
        "artist": artist_name,
        "track": track_name,
        "format": "json",
        "autocorrect": 1,
    }

    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(RATE_LIMIT_SLEEP)
            response = requests.get(LASTFM_API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.warning(
                    "Last.fm error %s for '%s' / '%s': %s",
                    data["error"], artist_name, track_name, data.get("message"),
                )
                return None

            track = data.get("track", {})
            return {
                "playcount": int(track.get("playcount", 0)),
                "listeners": int(track.get("listeners", 0)),
            }

        except requests.RequestException as exc:
            wait = 2 ** attempt
            logger.warning(
                "Last.fm attempt %d/%d failed for '%s'/'%s': %s — retry in %ds",
                attempt + 1, MAX_RETRIES, artist_name, track_name, exc, wait,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)

    logger.error(
        "Last.fm: all retries exhausted for '%s' / '%s'", artist_name, track_name
    )
    return None
```

### 8.2 Spotify (ingesta/clients/spotify.py)

**Legacy state:** 7 credential pairs for rotation (`WORKER_A1` through `E1`),
`spotipy` library, raw psycopg2. Rebuild with 1 credential pair, `requests` or
`spotipy`, Django ORM.

**Development Mode restrictions:**
- `GET /v1/artists?ids=` (batch) → BROKEN, do not use
- `GET /v1/artists/{id}/albums` → works
- `GET /v1/albums/{id}/tracks` → works
- Auth: Client Credentials flow (no user login needed)

Use only for metadata on approved artists: track name, ISRC, duration, release date,
album art. Respect 12-month filter on release dates.

### 8.3 Deezer (ingesta/clients/deezer.py) — PRIMARY METADATA SOURCE

**API:** Public, no authentication. Base URL: `https://api.deezer.com`

**Why Deezer over Spotify:** Spotify API requires active Premium subscription
for the app owner (403 since 2024). Deezer has no such restriction, provides
100% ISRC coverage, reliable release dates, and good coverage of Catalan artists.

**Functions:**

- `search_artist(nom)` → `{"id": int, "name": str}` or `None`
  - Normalizes names (lowercase, strip accents) for comparison
  - Exact match first, then containment match
  - Never returns first result without verification

- `get_artist_albums(deezer_id, min_date)` → list of album dicts
  - Handles pagination
  - Filters by `min_date` (release date cutoff)

- `get_album_tracks(album_id)` → list of track dicts with ISRC
  - Fetches full track endpoint for each track to get ISRC

**Rate limit:** 0.1s between calls. Retry 3x with exponential backoff.
Never raises — returns None/[] on error.

**ISRC validation flow (in ingestar_metadata):**
1. Search Deezer by artist name
2. Find a known Canco with ISRC for this artist
3. Fetch up to 3 albums from Deezer candidate, check if any track matches ISRC
4. If match → save `deezer_id`, proceed
5. If no match → set `deezer_no_trobat=True`, skip artist

### 8.4 Viasona (ingesta/clients/viasona.py)

**Legacy code:** `scripts/update_from_viasona.py` — BeautifulSoup scraper.
Audit, simplify, wrap cleanly. Must:
- Return a list of artist names and any available identifiers
- Handle pagination
- Never crash the discovery command — log errors and continue

### 8.5 Spotify (ingesta/clients/spotify.py) — FALLBACK

**Status:** Blocked since 2024, requires active Premium subscription for app owner.
Client implemented but returns 403. Kept as fallback if Premium is restored.

---

## 9. Management Commands

### Rules for all commands

- `self.stdout.write()` / `self.stderr.write()` — never `print()`
- `raise CommandError(...)` — never `sys.exit()`
- All DB writes inside `transaction.atomic()`
- Idempotent where possible (safe to re-run on same data)
- Log progress every 50–100 records
- End with a summary line: processed / success / errors

### 9.1 importar_legacy (one-off — Phase 1)

```
python manage.py importar_legacy [--artistes] [--cancons] [--dry-run]
```

- Reads from `LegacyArtista` and `LegacyCanco` (unmanaged models)
- Maps legacy territory strings to new codes:
  `'Catalunya'→'CAT'`, `'País Valencià'→'VAL'`, `'Balears'→'BAL'`
- Maps legacy `status='go'` → `aprovat=True`
- Deduplicates cançons (legacy has one row per territory, new has one row total)
- Sets `lastfm_nom = nom` initially (to be verified in Phase 2)
- Prints mapping report: imported / skipped / errors

### 9.2 ingestar_senyal (daily)

```
python manage.py ingestar_senyal [--data YYYY-MM-DD] [--limit N] [--dry-run]
```

- Queries `Canco` where `activa=True`, `artista__aprovat=True`,
  `data_llancament >= today - 365 days`
- Skips cancons already in `IngestaDiari` for `--data` (idempotent)
- Calls `lastfm.get_track_info(artista.lastfm_nom, canco.lastfm_lookup_nom)`
- Success → `IngestaDiari.update_or_create(canco, data, playcount, listeners)`
- Failure → `IngestaDiari.update_or_create(canco, data, error=True, error_msg=...)`
- Does NOT compute `score_entrada` — that is a separate step (Phase 3)

### 9.3 calcular_ranking (weekly — Sundays)

```
python manage.py calcular_ranking [--setmana YYYY-MM-DD] [--min-dies N]
```

- `--setmana` defaults to most recent Monday
- Pre-flight: if `score_entrada IS NULL` for > 20% of the input window,
  raise `CommandError` ("score_entrada not populated — run actualitzar_score_entrada first")
- Runs the 14-CTE SQL (extracted from legacy views) with adapted table/column names
- Wraps result upsert in `transaction.atomic()`

### 9.4 actualitzar_score_entrada (Phase 3 — backfill)

```
python manage.py actualitzar_score_entrada [--des-de YYYY-MM-DD]
```

- Reads all `IngestaDiari` rows where `score_entrada IS NULL`
- Applies `ranking/senyal.py::calcular_score_entrada()` to each
- Updates `score_entrada` in batches of 500 inside `transaction.atomic()`
- **Only implement this command after Phase 3 formula is defined**

### 9.5 ingestar_metadata (on demand)

```
python manage.py ingestar_metadata [--artista-id N] [--force] [--dry-run]
```

- Uses Deezer API (public, no auth) as primary metadata source
- For each approved artist without `deezer_id`:
  1. Searches Deezer by name (normalized matching)
  2. Validates via ISRC cross-check if known tracks exist
  3. Saves `deezer_id` or marks `deezer_no_trobat=True`
- Fetches albums released in last 12 months, creates Album + Canco
- Stores ISRC and `deezer_id` on each record
- Skips artists with `deezer_no_trobat=True` (unless `--force`)

### 9.6 matching_isrc_deezer (on demand)

```
python manage.py matching_isrc_deezer [--dry-run] [--limit N]
```

- For artists without `deezer_id` and `deezer_no_trobat=False`:
  1. Finds an ISRC from legacy `spotify_tracks` table via `spotify_id`
  2. Queries Deezer: `GET /track/isrc:{isrc}`
  3. Verifies artist name matches (main or contributor) to avoid false positives
  4. Saves `deezer_id` on match, or marks `deezer_no_trobat=True` on failure
- First run (2026-04-11): 208 matched out of 926 (713 had no ISRC in legacy)

### 9.7 descobrir_artistes (weekly — Mondays)

```
python manage.py descobrir_artistes [--font viasona|collaboradors|tots]
```

- Runs the selected discovery source(s)
- Creates `Artista(aprovat=False, auto_descobert=True, font_descoberta=...)` for new candidates
- Skips artists already in DB (match by spotify_id or normalized nom)
- Does NOT create Album or Canco records — only the Artista candidate

### 9.8 distribuir_ranking (weekly — Sundays after calcular_ranking)

```
python manage.py distribuir_ranking --setmana YYYY-MM-DD [--territori CAT] [--dry-run]
```

- `--dry-run`: saves image to `/tmp/tq_{territori}_{setmana}.png`, no Telegram send
- Validates `RankingSetmanal` exists before generating image
- One image per territory

---

## 10. Wagtail Admin: Approval Queue

In `music/admin.py`, register `Artista` with Wagtail `SnippetViewSet`:

- Default list filter: `aprovat=False` (shows pending candidates)
- Visible columns: nom, territori, font_descoberta, created_at
- Bulk actions: Approve (`aprovat=True`), Reject (`aprovat=False`)
- Search by nom

This is the human firewall against false positives (Marató artists, one-off
collabs from non-Catalan artists).

---

## 10b. Track Verification System (2026-04-12)

### HistorialRevisio model (music/models.py)

Records every approve/reject decision as a snapshot. Fields:

- **Identifiers:** `canco_deezer_id`, `canco_spotify_id`, `canco_isrc`
- **Snapshot:** `canco_nom`, `artista_nom`, `artista_territori`, `album_nom`,
  `data_llancament`, `isrc_prefix`
- **Deezer features:** `artista_deezer_id`, `artista_deezer_nb_fan`,
  `artista_deezer_nb_album`, `artista_nom_deezer`, `artista_nom_similitud`
- **Decision:** `decisio` (aprovada/rebutjada), `motiu` (ok/no_catala/
  artista_incorrecte/album_incorrecte/no_musica)

Read-only in admin. Created via `music/verificacio.py::crear_historial()`.

### Artista Deezer metadata fields

Added to `Artista`: `deezer_nb_fan`, `deezer_nb_album`, `deezer_nom`,
`deezer_nom_similitud`. Populated by `ingestar_metadata` when resolving
`deezer_id` (calls `deezer.get_artist_info()` + `difflib.SequenceMatcher`).

### Admin actions with motiu

All reject actions show an intermediate confirmation page with a required
motiu dropdown. Approvals record motiu='ok' automatically. Every action calls
`crear_historial()` before modifying/deleting records.

Actions:
- **Aprovar cançó:** `verificada=True`, records historial with motiu='ok'
- **Rebutjar (esborrar):** intermediate page, motius: no_catala,
  artista_incorrecte, album_incorrecte, no_musica
- **Rebutjar àlbum sencer:** intermediate page, motius: artista_incorrecte,
  album_incorrecte
- **Marcar sense Deezer i netejar:** intermediate page, motiu:
  artista_incorrecte

### ML pre-classification (music/ml.py)

Heuristic classifier `pre_classificar(canco)` returns class A/B/C:

| Signal | Effect |
|---|---|
| Artist in legacy Spotify | +0.3 (curated) |
| Deezer fans > 50K | -0.3 (international) |
| Deezer albums > 20 | -0.2 (international) |
| Artist name ≤ 3 chars | -0.2 (generic name risk) |
| Name similarity < 0.6 | -0.3 (bad match) |
| Name similarity > 0.9 | +0.2 (good match) |
| ISRC starts with ES | +0.2 (Spanish origin) |
| Rejection history > 70% | -0.3 |
| Rejection history < 30% | +0.2 |

Classes: A (≥0.65, green), B (0.35–0.65, orange), C (<0.35, red).
Shown as column in CancoAdmin with tooltip showing reasons.
Filterable via MLClasseFilter.

### Collaborator extraction (ingestar_metadata)

`_upsert_track` reads `track["contributors"]` from Deezer full track endpoint.
For each contributor (excluding the main artist):
- If exists in DB by `deezer_id` → add to `artistes_col`
- If not → create `Artista(aprovat=False, auto_descobert=True,
  font_descoberta='collaborador')` and add to `artistes_col`

---

## 11. Cron Schedule (production — after full migration)

File: `/etc/cron.d/topquaranta` — runs as user `topquaranta`

```cron
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin

# Hourly Deezer novelty ingestion (priority queue: P1=ISRC, P2=album tracks, P3=new albums)
0 * * * *   topquaranta   cd /home/topquaranta/app && python manage.py ingestar_novetats >> /var/log/topquaranta/novetats.log 2>&1

# Daily signal ingestion — 06:00
0 6 * * *   topquaranta   cd /home/topquaranta/app && python manage.py ingestar_senyal >> /var/log/topquaranta/ingestar.log 2>&1

# Weekly ranking — Sunday 08:00
0 8 * * 0   topquaranta   cd /home/topquaranta/app && python manage.py calcular_ranking >> /var/log/topquaranta/ranking.log 2>&1

# Weekly distribution — Sunday 09:00
0 9 * * 0   topquaranta   cd /home/topquaranta/app && python manage.py distribuir_ranking >> /var/log/topquaranta/distribucio.log 2>&1

# Artist discovery — Monday 10:00
0 10 * * 1  topquaranta   cd /home/topquaranta/app && python manage.py descobrir_artistes >> /var/log/topquaranta/descoberta.log 2>&1
```

---

## 12. Environment Variables (.env)

```dotenv
# Django
DJANGO_SECRET_KEY=
DJANGO_SETTINGS_MODULE=topquaranta.settings.production
ALLOWED_HOSTS=topquaranta.cat,www.topquaranta.cat
DEBUG=False

# Database (same DB as legacy — coexistence)
DATABASE_URL=postgres://topquaranta:PASSWORD@localhost:5432/topquaranta

# Spotify (metadata only — single credential pair, Development Mode)
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=

# Last.fm (primary signal source — obtain from https://www.last.fm/api/account/create)
LASTFM_API_KEY=
LASTFM_API_SECRET=

# Distribution
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHANNEL_ID=
```

Load with `python-decouple`. Never use `os.environ` directly in app code.
Always read via `from django.conf import settings`.

**Legacy keys NOT carried over:** 7 Spotify worker credential pairs, OpenAI,
Supabase, Buttondown, Brevo SMTP, Instagram — not needed for the new pipeline.

---

## 13. Testing

```ini
# pytest.ini
[pytest]
DJANGO_SETTINGS_MODULE = topquaranta.settings.local
python_files = tests/test_*.py
python_classes = Test*
python_functions = test_*
```

Coverage target: ≥ 70% on `ingesta/` and `ranking/`.

```
pytest --cov=ingesta --cov=ranking --cov-report=term-missing
```

Mock all external HTTP — never make real API calls in tests.
Use `@pytest.mark.django_db` for any test touching the DB.

**Critical test cases:**

```
ingesta/tests/test_lastfm_client.py:
  test_success              mocked 200 → correct playcount and listeners
  test_track_not_found      Last.fm error 6 → returns None, no exception
  test_network_error        RequestException → None after MAX_RETRIES
  test_rate_limit_sleep     time.sleep called with RATE_LIMIT_SLEEP

ranking/tests/test_algorisme.py:
  test_ranking_order        known fixture → expected top 3 order
  test_album_monopoly       4th track from same album is penalized
  test_artist_monopoly      6th track from same artist is penalized
  test_novelty_bonus        2-week-old track scores above equivalent 30-week-old track
  test_all_territory        artista with 3 territoris appears in CAT, VAL, BAL rankings

music/tests/test_models.py:
  test_get_territoris_multiple   Artista with CAT+VAL+BAL → get_territoris() == {'CAT','VAL','BAL'}
  test_get_territoris_single     Artista with VAL → get_territoris() == ['VAL']
  test_get_territoris_empty      Artista with no territories → get_territoris() == []
  test_get_territoris_with_collaborator  Canco(Zoo VAL + Txarango CAT collab) → {'VAL','CAT'}
  test_get_territoris_marala_style       Canco(Marala CAT+VAL+BAL) → all 3 territories

ingesta/tests/test_importar_legacy.py:
  test_territory_mapping    'Catalunya' → CAT M2M, 'País Valencià' → VAL M2M, 'Balears' → BAL M2M
  test_deduplication        same id_canco in 3 territories → 1 Canco
  test_status_mapping       status='go' → aprovat=True
```

---

## 14. Code Conventions

- No `print()` → `logging`
- No `sys.exit()` → `raise CommandError(...)`
- No `TRUNCATE` → Django ORM deletes inside `transaction.atomic()`
- No raw DDL outside migrations
- No raw psycopg2 — always Django ORM (except `algorisme.py` raw SQL via `connection.cursor()`)
- All DB writes in `transaction.atomic()`
- Type hints on all new functions
- f-strings preferred
- black + isort formatting
- Comments and docstrings: English only

### Development environment

Claude Code runs directly on the Hetzner production server (CX22, 188.245.60.20),
not on a local machine. There is no separate local development environment for
TopQuaranta.

- Working directory: `/home/topquaranta/app/`
- Direct access to the production PostgreSQL database (`topquaranta`)
- Can execute `manage.py` commands directly (migrations, imports, etc.)
- The virtualenv is at `/home/topquaranta/app/.venv/`

### Git workflow

The flow is: Claude Code (server) → `git push` → GitHub (source of truth).

After every session with significant changes, Claude Code must:

```bash
git add -A && git commit && git push origin main
```

- The commit message is written by Claude Code based on the actual changes
- Always pull before pushing if the remote has diverged (`git pull --rebase`)
- Never skip this step — the server deploys from `main`
- GitHub is the canonical source; the server working copy is just the active checkout

### Roadmap tracking

At the end of every work session, update `ROADMAP.md` to reflect the real state:
mark completed items with `[x]`, annotate the next pending step within the current
phase, and update the following phase summary if scope has changed.

---

## 15. Key Decisions and Rationale

| Decision | Rationale |
|---|---|
| New project, not incremental cleanup | Legacy has incompatible PKs, no tests, no migrations, monolithic scripts — cleaning incrementally would take longer and produce a worse result |
| Same database, coexistence | Zero data loss risk; legacy CMS continues running during migration; rollback is always possible |
| Last.fm as signal source | Spotify popularity deprecated Nov 2024; Last.fm has public playcount + listeners |
| `score_entrada` formula deferred | Cannot design a good normalization without real distribution data |
| Algorithm extracted, not rewritten | Well-founded 14-CTE logic; port to Python, adapt inputs, keep math identical |
| `ConfiguracioGlobal` as Django model | Version-controlled, editable via admin, testable — was raw table with no ORM |
| Territory on artist (M2M), not track | Legacy duplicated tracks per territory (PK bloat). Territory is a property of the artist. Artists can belong to multiple territories (Marala → CAT+VAL+BAL). Tracks with collaborators appear in all artists' territories (Txarango CAT + La Fumiga VAL → track in both rankings) |
| Territori model + data migration | 10 territories: CAT, VAL, BAL (always ranked), CNO, AND, FRA, ALG, CAR (ranked if ≥ threshold tracks), ALT (grouped), PPCC (global). Migrations `0002` + `0014` |
| Canco.artistes_col M2M | Tracks can have collaborating artists. `artista` FK = main artist for display; `artistes_col` M2M = all collaborators. `Canco.get_territoris()` returns union of all artists' territories |
| Territory codes (max 4 chars) | CAT, VAL, BAL, CNO, AND, FRA, ALG, CAR, ALT, PPCC. Mapped from legacy `municipis` table via comarca |
| Human approval for all auto-discovered artists | Prevents false positives (Marató, one-off collabs) |
| ISRC on every Canco | Universal cross-system key; enables future integrations |
| 12-month track cutoff | TopQuaranta tracks current music, not back-catalogue |
| No Celery | Daily/weekly cron is sufficient; avoids broker complexity |
| Single Spotify credential pair | Legacy had 7 pairs for rate-limit rotation — unnecessary with individual calls |
| Legacy code is reference only | Never import, never subclass — read, understand, reimplement cleanly |
