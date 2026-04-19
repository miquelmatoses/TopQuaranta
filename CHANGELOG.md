# Changelog

All notable changes to TopQuaranta are recorded here. Based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Dates are UTC.

---

## [Unreleased]

Phase 9 wrap-up + groundwork for ML feature extraction + Whisper LID
integration (Sessió 16).

### Added

- **Model-comparison harness** at `scripts/model_comparison/` — ground-
  truth manifest of 48 clips (21 Catalan vocals + 15 foreign-language
  hits + 11 instrumentals + 1 mislabelled), regenerable via
  `fetch_clips.py`, one runner per candidate model in its own venv. The
  harness paid for itself: surfaced two real catalogue errors (Martina
  Burón *In The Rain* = actually English; Marc Parrot *Visions Tàctils*
  = actually instrumental), both rebutjat with `motiu="no_catala"`.
  `resultats.md` records per-model numbers (Silero, Spleeter, Demucs,
  MusicNN, inaSpeechSegmenter, Whisper large-v3, VoxLingua107 ECAPA).
  Commits `9c83908`, `04db69e`, `4ba4bb5`, `ee58e8c`.
- **Whisper LID** (`ingesta/clients/whisper.py`,
  `ingesta/management/commands/analitzar_whisper.py`, migration `0040`)
  — `faster-whisper large-v3` via `detect_language()` on the 30-second
  Deezer preview. New fields on `Canco`: `whisper_lang`, `whisper_p`,
  `whisper_processat_at`. Evaluated on the 48-clip harness after human
  correction of 2 ground-truth labels: **precision(ca) = 100 %**,
  recall(ca) = 81 %, specificity = 100 %. Zero false positives on the
  dangerous class — no foreign-language or instrumental clip got
  `p(ca) > 0.05`. Deliberately a staff **signal, not a hard gate**:
  a new badge + dropdown on `/staff/cancons/` flags tracks where
  `whisper_lang != ca`, making catalogue audit work the routine case
  rather than the exception. Runs nightly at 02:30 via cron, limit
  500 tracks/night (≈3h45m at ~27 s/track CPU).
- **Staff template tag** `whisper_badge` + filter dropdown "Idioma" +
  table column on `/staff/cancons/`.

### Added (before Whisper)

- **Φ6 data retention** (`977beef`) — `docs/RETENTION.md` + new management
  command `arxivar_senyal_vell` that runs quarterly and archives
  `SenyalDiari` rows older than 2 years to gzipped CSV, then deletes from
  the live DB. Writes are atomic (fsync + rename before DB delete).
- **C4 deprecation policy** (`b8e2de5`) — `docs/DEPRECATION.md` establishing
  a 4-step process (announce in CHANGELOG, emit in-code warning, wait
  90/180 days, remove). Motivated by the R10b regression.
- **D6 composite indexes** (`cf52345`) — `RankingSetmanal(territori,
  setmana, posicio)` and `Canco(verificada, artista)` for the hot ranking
  and pipeline queries. Future-proofing for when the tables grow.
- **Artista.lastfm_te_scrobbles** (`116505a`) — new boolean that
  distinguishes "real Last.fm errors" (artist indexed, specific track
  not) from "silent tracks" (artist has no Last.fm data at all).
  Maintained by `obtenir_senyal`; migration 0037 backfills from
  `SenyalDiari` history.

### Changed

- **Φ7 manifest** (`694303a`) — "No monetization" section rewritten.
  Distinguishes mission-aligned revenue (cultural ads in Catalan,
  institutional support with placement-not-position) from revenue that
  would corrupt the measurement (selling data, selling the user list,
  anything tied to ranking outcomes).
- **Φ1 definition** (`a7b04fe`) — instrumental tracks no longer treated as
  a separate rule; they fail the "delivery is in Catalan" test and are
  rejected with `motiu="no_catala"`. No new motiu needed.
- **titlecase_catala** (`ee4652b`, `43a000b`) — orphan accents (` / ´ /
  curly quotes) normalised to ASCII apostrophe before tokenising;
  single-letter "I"/"A"/"O" stop being treated as acronyms mid-sentence;
  words after opening punctuation `([{«"¿¡` now capitalise the first
  alphabetic character. Applied in production via new `retitlecase`
  command over Canco.nom (2038 rows updated) and Album.nom (2881 rows).
  Upstream `_create_album` also titlecases now.
- **Last.fm signal ingest** (`116505a`) — `_normalize_track` now strips
  alternate titles after `|`; `get_track_info` gains a last-resort
  fallback via `artist.getTopTracks` (fuzzy match ratio ≥ 0.95) that
  recovers case-only variants like "+ Arcade" vs "+ ARCADE".

### Fixed

- **R10c** (`f41d40a`) — `obtenir_novetats._create_track`,
  `_process_track_data`, and `obtenir_metadata._upsert_track` now wrap
  the collaborator-resolution loop in `try/finally` with
  `classificar_i_guardar(canco)` in the finally. A brief regression
  window on 2026-04-16 left 1 track unclassified because the collab
  loop raised before the classifier ran; the fix guarantees a track is
  never persisted without an ML class set, even if collab fails.

### Docs

- **Sessió 13** (`fb2bd50`) — documentation for the D6/C4/Φ6 landing.

### Added / Reverted (Silero VAD experiment, Sessió 15)

Silero VAD was integrated end-to-end (commits `19a8904`, `abda422`,
`85756fa`, `cdc01e2`, `7fc2eba`, `49188cc`) — new Canco fields, RF
feature, staff badge, nightly cron, logrotate, deps, a partial
backfill of 410 tracks.

**Reverted at the end of the same session** because the model is
structurally inadequate for music:

  - Silero VAD is trained on speech (podcasts, phone calls, clean
    voice), not singing.
  - Against ground truth (47 staff-verified Catalan vocal tracks),
    Silero classified **51% as <10% voice** — i.e., a false-positive
    rate for "instrumental" of one in two.
  - Flagrantly wrong on rock bands with instrumentation (Sopa de
    Cabra concerts at 0-7%), hardcore (Katarrama 1.7%), typical
    vocal tracks (Aquarella "Aire Pur" 0%, ALTATXU 3.5%).
  - As an ML feature this would inject systematic noise, hurting
    the 97.7% CV accuracy of the current classifier.

Schema reverted via migration `0039_revert_silero_fields`. Code
deleted. Deps removed from requirements.txt. Cron + tq-health +
logrotate cleaned. The `torch` and `silero-vad` install stays in
the venv (~850 MB), harmless; a fresh install from requirements.txt
won't pull them.

Lesson recorded: speech-VAD ≠ voice-in-music detector. If we revisit
instrumental detection, the right model family is music-specific:
Spleeter (source separation), MusicNN (music tags), Demucs,
inaSpeechSegmenter. A standalone comparison harness is the next
step, NOT another integration-first attempt.

---

## [0.9.0] — 2026-04-17

Closes **Phase 9 session 1–11**: 41 of 62 audit findings resolved across
security, reliability, performance, operations, data model, frontend,
architecture and process. The system graduated from "functioning but
fragile" to "functioning and defensible."

### Security (Tier 1 complete)

- **S1** PostgreSQL password rotated to 40-char random.
- **S2** GitHub access migrated from PAT to ed25519 SSH deploy key; cleanup
  verified.
- **S3** Daily backups (already in place from Phase 7) now covered by R14
  monthly restore test.
- **S4** `django-axes` brute-force login protection enabled.
- **S5** Registration no longer reveals whether an email is registered
  (anti-enumeration).
- **S6** Strict `Content-Security-Policy`, `X-Frame-Options`, `X-Content-
  Type-Options` headers.
- **S7** `/mapa/` now uses `json_script` — no `|safe` on user-derived data.
- **S8** URL scheme allowlist on `PropostaArtista` social links.
- **S9** DRF throttling: 60/min anon, 300/min user on `/api/v1/*`.
- **S10** Argon2 password hashing.
- **S11** TOTP 2FA for staff (django-otp) with backup codes + reset
  management command.
- **S13** Branded 403/404/500 templates.

### Reliability (Tier 2 complete)

- **R1** `algorithm_version` + `config_snapshot` on `RankingSetmanal` so
  weekly rankings are reproducible.
- **R2** Foreign-key cascades that would rewrite ranking history changed
  to `SET_NULL` with name snapshots.
- **R5** Last.fm autocorrect drift detection + staff review flow.
- **R7** Cron retry — `tq-run` in-process (3 attempts, backoff 60/300s)
  + `tq-recover` sweep every 30 min.
- **R8** Min/max validators on `ConfiguracioGlobal` numeric fields.
- **R9** `StaffAuditLog` model + helper + cross-view integration +
  read-only UI at `/staff/auditlog/`.
- **R10, R11** Dual sources of truth eliminated: `Artista.deezer_id`
  and `Artista.{localitat,comarca,provincia}` dropped;
  `ArtistaDeezer` and `ArtistaLocalitat` are the sole sources.
- **R12** `sync_territoris_from_localitats` signal deferred to
  `transaction.on_commit`.
- **R13** Defensive `{% if canco.album %}` guards on staff templates;
  5 latent R10/R11 template regressions cleaned up along the way.
- **R14** Monthly `tq-restore-test` validates the latest daily backup
  can be restored and row counts are within 5% of live.

### Performance

- **P2** RF classifier + TF-IDF vectorizer cached with mtime invalidation.
- **P3** Composite indexes `(artista_nom, decisio)` + `(isrc_prefix,
  decisio)` on `HistorialRevisio`.
- **P4** `obtenir_senyal` switched from per-row `update_or_create` to
  batched `bulk_create(ignore_conflicts=True)`.
- **P6** `CONN_MAX_AGE=600` + `CONN_HEALTH_CHECKS=True` in production.
- **P8** `@last_modified` + `@etag` on homepage and `/ranking/` — 304
  Not Modified on revalidation.

### Data model

- **D1** Partial unique constraint on `Canco.isrc` (when non-empty).
- **D2** Dead Last.fm fields (`Canco.lastfm_mbid`,
  `Canco.lastfm_verificat`, `Artista.lastfm_mbid`) dropped.
- **D5** Self-collaboration guard: `m2m_changed` receiver rejects
  `canco.artistes_col.add(canco.artista)`; pre-existing rows cleaned up.

### Operations

- **O3** GitHub Actions CI on every push / PR: pytest +
  `manage.py check` + black + isort + missing-migration detection.
- **O5** SSH key policy documented (`deploy/SSH_KEY_POLICY.md`).
- **O8** `RUNBOOK.md` covering 8 operational incidents.
- **O9** `logrotate` weekly rotation for `/var/log/topquaranta/*.log`.

### Architecture

- **A8** API versioning policy (`web/api/VERSIONING.md`) +
  `X-API-Version` middleware.
- **A10** `mm-design` vendored into the repo at `vendor/mm-design/`;
  `npm install` no longer required for deploys.

### Frontend / UX

- **F3** SEO surface: `<meta name="description">`, Open Graph, Twitter
  Cards, `sitemap.xml`, `robots.txt`, default OG image.
- **F5** "Actualitzat el …" timestamp on ranking pages.

### Process

- **C1** pre-commit hooks mirroring CI (black + isort + missing-
  migration check).

### Cultural transparency

- **Φ4** `/com-funciona/` editorial + live coefficients + algorithm
  transparency history page.

### Infrastructure

- Ops layer from prior work: `tq-run` / `tq-health` / `tq-backup` /
  `tq-recover` / `tq-restore-test` ops scripts;
  `/etc/cron.d/topquaranta`; `/var/log/topquaranta/status/*.status`;
  systemd `topquaranta-web.service`.

---

## [0.8.0] — 2026-04-16

Phase 8 legacy cleanup:

- Dropped all pre-2026 legacy database tables (Wagtail CMS, old image
  generation, legacy Telegram distribution).
- Removed legacy Wagtail admin service.
- Caddy config simplified.
- Ops monitoring (`tq-health`) + daily backups (`tq-backup`) + settings
  split completed.

---

## Earlier phases

See `ROADMAP.md` for a summary of Phases 0–7 (project scaffold,
Last.fm ingestion, ranking algorithm port, metadata pipeline,
staff panel, legacy cleanup). No formal release tags for those
phases — the codebase lived as a rolling main branch until 0.8.0.
