# ROADMAP.md — TopQuaranta

> Current state and next steps. Historical iteration detail lives in git log.
> Last updated: 2026-04-16 — Ops hardening: monitoring (tq-health), tiered backups, settings audit.

---

## Current state (2026-04-16)

**Public site**: `https://www.topquaranta.cat/` — homepage (PPCC ranking),
per-territory rankings, artist directory, artist + album + song profiles,
interactive territorial map (D3.js), user accounts, verified-artist portal.

**Staff panel**: `/staff/` — tracks, albums, artists, pending artists,
provisional ranking, historial, senyal, management requests, new-artist
proposals, configuration. All behind `@staff_required`.

**Pipeline** (daily/hourly cron, `/etc/cron.d/topquaranta`):
- Hourly: `obtenir_novetats` (Deezer incremental).
- 04:00: `netejar_caducades` (drop unverified tracks > 12 months old).
- 06:00 + 06:30: `obtenir_senyal` (Last.fm) + `actualitzar_score_entrada`.
- 07:00: `calcular_ranking --provisional` (all eligible territories).
- Saturday 08:00: `calcular_ranking` (official weekly).

**Database**: PostgreSQL. 25 tables, 44 MB. All legacy tables + views dropped
in Phase 8. 10 Territoris, 1,825 Municipis, 2,288 approved Artistes, 19,937
Cançons (10,842 verified), 10,082 SenyalDiari rows, 1,448 HistorialRevisio
decisions feeding the ML model (97.2% CV accuracy).

**Infrastructure**: single gunicorn on port 8083, Caddy TLS. Legacy Wagtail
code is preserved at `/root/TopQuaranta/` but the service is disabled. No
Django admin, no Wagtail admin.

---

## Phase status

| Phase | Summary | Status |
|---|---|---|
| 0 | Project skeleton, user, DB, settings split | ✅ done |
| 1 | Legacy data imported into new models | ✅ done (legacy tables dropped in 8) |
| 2 | Last.fm ingestion running | ✅ done |
| 3 | Formula B (percent_rank) signal normalization | ✅ done |
| 4 | Ranking algorithm ported from SQL views to Python | ✅ done |
| 5 | Provisional ranking + admin review | ✅ done (image/Telegram distribution shelved) |
| 6 | Metadata pipeline (Deezer) + public website | ✅ done |
| 7 | Custom `/staff/` panel replaces Wagtail/Django admin | ✅ done |
| 8 | Legacy cleanup (tables, code, services) | ✅ done (2026-04-16) |
| Audit | Consolidation + doc rewrite | ✅ done (2026-04-16) |
| Ops | Monitoring (tq-health) + daily backups + settings cleanup | ✅ done (2026-04-16) |

---

## Ops layer (2026-04-16)

- **`/home/topquaranta/bin/tq-run`** wraps every cron command. Captures exit
  codes and last output to `/var/log/topquaranta/status/<tag>.status`.
- **`/home/topquaranta/bin/tq-health`** prints a summary and exits non-zero
  if any command is FAIL / STALE or if today's Django `errors.log` has any
  entries. Intended for manual SSH inspection; can be wired to any external
  notifier later.
- **`/home/topquaranta/bin/tq-backup`** runs as `postgres` at 03:00, tiered
  retention (7 daily / 4 weekly / 12 monthly).
- **`settings/base.py::LOGGING`** adds a file handler for ERROR+ to
  `/var/log/topquaranta/errors.log`. Tests are isolated via NullHandler.
- Root crontab cleaned (8 stale legacy entries removed).

---

## Pending / deferred

### High-value polish
- [ ] Investigate Last.fm 18% error rate ("Track not found" for tracks Last.fm
      genuinely does not index). Normalization already recovers ~3/4 of fixable
      cases; the rest may be genuine (unscrobbled tracks).
- [ ] SEO: meta tags, Open Graph, sitemap.xml.
- [ ] Mobile responsive polish.

### Tech debt / nice-to-haves
- [ ] Test coverage at 52%, target 70%. Main gaps with 0% coverage:
      `music/services.py`, `music/verificacio.py`, `ranking/senyal.py`,
      `ranking/management/commands/calcular_ranking.py`.
- [ ] Decide whether to archive `/root/TopQuaranta/` (1.4 GB legacy Wagtail
      code). tar.gz or `rm -rf`.
- [ ] Optional: pipe `tq-health` to a push-based notifier (healthchecks.io,
      Uptime Kuma) if on-call becomes a thing.
- [ ] Bigger refactors still deferred:
      - Extract heuristic-classifier magic numbers to `music/constants.py`.
      - Move `PPCC_PENALITZACIO_PER_POSICIO = 0.04` into `ConfiguracioGlobal`.
      - Consolidate reject-action handling; some inline styles in staff
        templates could become CSS classes.

### Shelved indefinitely
- Image generation (PIL) for ranking posters.
- Telegram / Instagram distribution.
  Original assets (TTF fonts, SVG territory logos) were on a local machine
  that is no longer accessible. The public website is the distribution channel
  instead.

---

## Ground rules for future work

- Never commit without explicit request.
- Update this file at the end of each session.
- Follow the conventions in `CLAUDE.md` §9.
- No new parallel design systems — tokens come from mm-design.
- No raw SQL outside `ranking/algorisme.py` and migrations.
- When in doubt about a decision, check §5 of `CLAUDE.md`.
