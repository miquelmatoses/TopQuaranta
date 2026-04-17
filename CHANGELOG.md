# Changelog

All notable changes to TopQuaranta are recorded here. Based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Dates are UTC.

---

## [Unreleased]

Phase 9 — Excellence continues. Ongoing work beyond 0.9.0: remaining
Tier 3 (Architecture), Tier 5 (Exquisitesa).

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
