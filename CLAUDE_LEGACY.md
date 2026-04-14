# CLAUDE_LEGACY.md — Audit del sistema legacy

> Reference only. Do not import, subclass, or modify legacy code.
> Source: `/root/TopQuaranta/` (git repo, 1 commit)

---

## 1. Legacy codebase location

Two copies exist on the server:
- `/root/TopQuaranta/` — git repo (1 commit: "Initial commit"), `.git` present
- `/root/TopQuaranta_dev/` — dev copy with venv at `/root/TopQuaranta_dev/venv`
- Symlink: `/root/TopQuaranta/venv -> /root/TopQuaranta_dev/venv`
- Everything runs as `root` — no `topquaranta` OS user exists yet
- No `/home/topquaranta/` directory exists

## 2. Legacy Django structure

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

## 3. Legacy scripts (not Django)

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

## 4. Legacy database schema (actual state)

**Core tables:**

| Table | PK | Rows | Notes |
|---|---|---|---|
| `artistes` | `id_spotify` (varchar 50) | 6,477 (2,313 with status='go') | Main artist table |
| `cançons` | `(id_canco, territori)` composite | 11,555 active | Same track duplicated per territory! |
| `ranking_diari` | `(data, territori, posicio)` | 312,132 (2025-04-13 to 2026-03-09) | Daily snapshots — 126 MB |
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
status ('go'/'stop'/etc.), territori, catala (boolean), localitat, comarca,
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

## 5. Legacy SQL views (15 total)

```
vw_top40_cat, vw_top40_pv, vw_top40_ib, vw_top40_altres     (daily top 40)
vw_top40_weekly_cat, vw_top40_weekly_pv, vw_top40_weekly_ib,
vw_top40_weekly_ppcc, vw_top40_weekly_altres                  (weekly ranking — the algorithm)
vw_albums_recents, vw_cancons_caigudes, vw_novetats           (CMS helper views)
vw_geodata_artistes, artistes_discrepants, pending_update     (admin/maintenance views)
```

## 6. Legacy cron

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

## 7. Legacy .env keys (relevant subset)

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
