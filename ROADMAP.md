# ROADMAP.md — TopQuaranta

> Current state and next steps. Historical iteration detail lives in git log.
> Last updated: 2026-04-16 — Phase 9: 16 findings landed across 4 sessions
> (Tier 1 security complete except IP allowlist; Tier 2 reliability partial).
> See CLAUDE_EXCELLENCE.md for progress.

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
| **9** | **Excellence — security, reliability, architecture, cultural transparency** | 🟠 **in progress** (16 findings landed: Tier 1 security + staff 2FA + key Tier 2 reliability) |
| 10 | Polish & backlog (tactical cleanups not covered by Phase 9) | ⏳ after 9 |

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

## Phase 9 — Excellence (next)

**Goal**: close the gap between "the system works" and "the system is an
artifact worth preserving". Full diagnosis in **`CLAUDE_EXCELLENCE.md`**.

**Scope**: 62 findings across 9 areas (Security, Reliability, Performance,
Architecture, Data model, Operations, Frontend/UX, Process, Philosophy).

**Severity distribution**:
- 🔴 7 CRITICAL — real exposure or guaranteed data loss under normal conditions
- 🟠 15 HIGH — concrete risk under plausible conditions
- 🟡 22 MEDIUM — defense-in-depth, structural debt
- 🟢 18 LOW / PHILOSOPHICAL — polish, transparency, cultural fidelity

**Execution tiers** (mirror the ones listed at the end of `CLAUDE_EXCELLENCE.md`):

### Tier 1 — Foundations (weeks)
Rotate secrets (DB password, GitHub PAT, SECRET_KEY). Encrypted off-site
backups. `django-axes` + Argon2 + staff 2FA. Real CSP. Input validation on
user-generated fields (`PropostaArtista.nom`, social URLs).

### Tier 2 — Reliability (weeks)
`algorithm_version` + `config_snapshot` on `RankingSetmanal` for forever-
reproducible rankings. Immutable staff audit log. `@cache_page` + `ETag` on
public pages. CI/CD (pytest + ruff + mypy on every push). Monthly backup
restore drill.

### Tier 3 — Architecture (months)
Extract a domain layer from `music.models`. Proper job queue (Celery / RQ)
for ML retraining and notifications. Versioned REST API with resource-per-
resource design. Event bus to decouple approvals from downstream actions.
Port the 14-CTE to testable Python (at least a SQLite-runnable variant).

### Tier 4 — Culture (months)
`CULTURAL.md` manifesto: what is Catalan music according to TopQuaranta,
why the coefficients weigh what they weigh. Algorithmic transparency (per-
song "why here?" button). Artist agency — verified artists can propose
corrections. Data licensed CC-BY-SA. Multilingual (at least CA + EN).

### Tier 5 — Exquisiteness (years)
Native mobile app on the v1 API. Personalised recommendations for logged-in
users. Federation with sister Catalan-culture projects. Open editorial
governance for coefficient changes. Physical / digital magazine edition.

**Ground rule for Phase 9**: every fix lands with a test that would have
caught the defect, and every architectural change is reversible or
documented with an ADR.

---

## Phase 10 — Polish & backlog (after 9)

Tactical items not tied to specific CLAUDE_EXCELLENCE findings:

### High-value polish
- [ ] Investigate Last.fm ~18% error rate for genuinely un-scrobbled tracks.
      Normalization already recovers ~3/4 of fixable cases; document the
      remaining set as "expected misses" or flag them for manual review.
- [ ] Mobile responsive polish (site works but device testing would help).

### Tech debt / nice-to-haves
- [ ] Test coverage 52% → 70%. Main 0% gaps: `music/services.py`,
      `music/verificacio.py`, `ranking/senyal.py`,
      `ranking/management/commands/calcular_ranking.py`.
      (Partially covered by Phase 9 Tier 2 "CI/CD".)
- [ ] Decide whether to archive `/root/TopQuaranta/` (1.4 GB legacy Wagtail
      code). tar.gz to offsite storage or `rm -rf`.
- [ ] Move `PPCC_PENALITZACIO_PER_POSICIO = 0.04` into `ConfiguracioGlobal`
      alongside the other algorithm coefficients.
- [ ] Extract heuristic-classifier magic numbers in `music/ml.py` to
      `music/constants.py`.
- [ ] Consolidate reject-action handling; some inline styles in staff
      templates could become CSS classes.

---

## Shelved indefinitely

- Image generation (PIL) for ranking posters.
- Telegram / Instagram distribution.

Original assets (TTF fonts, SVG territory logos) were on a local machine
that is no longer accessible. The public website is the distribution
channel instead.

---

## Ground rules for future work

- Never commit without explicit request.
- Update this file at the end of each session.
- Follow the conventions in `CLAUDE.md` §9.
- No new parallel design systems — tokens come from mm-design.
- No raw SQL outside `ranking/algorisme.py` and migrations.
- When in doubt about a decision, check §5 of `CLAUDE.md`.
- While Phase 9 is active: tag each commit's subject with the finding ID
  (e.g. `fix(S1): rotate DB password and update .env template`) so progress
  against `CLAUDE_EXCELLENCE.md` is traceable.
