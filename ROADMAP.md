# ROADMAP.md — TopQuaranta

> Current state and next steps. Historical iteration detail lives in git log.
> Last updated: 2026-04-22.

### Recent deliveries (past week)

- **MusicBrainz integration** — continuous 15-min cron
  (`obtenir_metadata_musicbrainz`) pulls MBID + area + begin/end dates +
  URL relationships + full discography; reconciles Albums/Cançons by
  ISRC and normalised title. Staff panel exposes MBID field + on-demand
  sync button on every edit page. Invariant now `aprovat ⇒ Deezer OR MBID`,
  so Crim-style collisions can keep both artists live. Estat dashboard
  gains an MB coverage block. ML features grow 76 → **79** with
  `mbrainz_confirmed`, `mb_lyrics_cat`, `artista_te_mbid`.
- **Grup C community** — `PerfilUsuari`, `Publicacio`, `Comentari`,
  `Missatge`. Directori, feed moderat, DM 1-to-1, comentaris. Email
  notifications with per-user opt-outs. Unread-message badge on the
  account icon.
- **Mapa drill-down** — `/mapa` SVG of the PPCC with three zoom levels
  (territori → comarca → municipi) + sticky side panel with KPIs and a
  top-artist grid per region, sorted by cumulative Last.fm plays.
  GeoJSON preprocessed with Douglas-Peucker at 0.002° (5 MB → 2 MB
  across 17 files). L'Alguer renders as a Canaries-style inset.
- **Email pipeline** — real SMTP via cdmon (smtp.topquaranta.cat:587
  STARTTLS). HTML-styled emails matching site aesthetic. Password-reset
  + resend-verification + self-delete + DM/comment notifications all
  send via this channel now.
- **Staff UX fixes** — visible Tornar/action buttons on dark headers
  (new `outline` tone), semantic colour tokens in design system
  (`--color-tq-success/warning/danger/neutral/accent`), markdown
  rendering in publications (with heading-level shift + image support),
  staff usuaris merged with directori-usuaris into one page.
- **Pipeline reliability** — Deezer P2 no longer permanently marks an
  album as "no tracks" after a single empty response (retries while
  the album is <30 days old); NFD-encoded track names now hit Last.fm
  correctly; ALT ranking aggregates below-threshold territoris; stale
  RankingSetmanal rows cleared when a territori's feeders vanish.
- **Design system** — `--color-tq-*` semantic tokens used throughout
  `EstatPage` (dropped hardcoded hex). Intake-per-week bars switched to
  pixel heights to fix a flex percentage-height rendering bug.

---

## Current state (2026-04-22)

**Public site**: `https://www.topquaranta.cat/` — React SPA at the root.
Routes: `/` (home), `/top` (current weekly ranking per territori), `/artistes`
(directory + filters), `/artista/<slug>`, `/album/<slug>`,
`/canco/<slug>` (with multi-line ranking history chart), `/mapa` (territorial
browse), `/compte` (user dashboard), `/compte/artista/{proposta,gestio}`.
Every content page has **"Escolta-ho a"** buttons to Spotify / Deezer /
YouTube Music / Apple Music plus a **"Corregir"** feedback button.

**Staff panel**: `/staff/*` — React pages backed by DRF. 17 pages:
dashboard, estat (visual health), pendents, artistes (+ crear + editar),
cançons (+ editar), albums (+ editar), ranking provisional, propostes
(+ detall), sol·licituds, senyal, historial, configuració, auditoria,
usuaris (+ detall), feedback. Full collab editing on track edit, artista
reassignment with cascade-canço toggle.

**Authentication**: Django session cookies + CSRF. Staff uses TOTP 2FA
enforced at the API layer (`IsStaff` requires `user.is_verified()`). The
2FA pages still render via Django templates under the Caddy allow-list.

**Pipeline** (deploy/cron.topquaranta):
- Hourly: `obtenir_novetats` (Deezer incremental).
- **01:30 UTC**: `analitzar_whisper --limit 700` (LID, ~5h15m window).
- 04:00: `netejar_caducades` (drop unverified > 12 months).
- 06:00: `obtenir_senyal` (Last.fm) + `actualitzar_score_entrada` (06:30).
- **07:00**: `calcular_ranking --provisional`.
- **07:15**: `actualitzar_playlists_spotify` (top-CAT/VAL/BAL/ALT + novetats).
- Saturday 08:00: `calcular_ranking` (official weekly).
- Quarterly: `arxivar_senyal_vell`.
- Daily 03:00: pg_dump via `tq-backup`.

**Database**: PostgreSQL 14. 37 tables (18 domain + Django/axes/otp internals).
Post-purge 2026-04-20: 1,920 aprovats + 2,323 pendents = 4,244 Artistes;
3,563 Albums; 8,144 Cançons (100% with Deezer ID + ISRC); 1,770 verified
(21.8%); 17,408 SenyalDiari rows; 4,371 HistorialRevisio decisions.

**ML classifier** (`music/ml.py`) — RandomForestClassifier + TF-IDF.
**79 features** post-slim + MB (12 structured + 4 Whisper + 3 MusicBrainz + 60 TF-IDF).
5-fold CV: ROC-AUC 0.9994, F1 0.9522, accuracy 0.9675. Top features:
`ratio_rebuig_artista` (22.2%), `ratio_rebuig_registrant` (14.9%),
`ratio_rebuig_isrc_prefix` (13.6%), all Bayesian-smoothed (k=5, p=0.5).
Auto-retrain when ≥5 new decisions.

**Infrastructure**: Caddy 2.x (TLS + SPA fallback), single gunicorn
with `ExecReload=HUP` for graceful deploys. SPA bundle at
`web-react/dist/`. Legacy Wagtail code preserved at `/root/TopQuaranta/`
but the service is disabled.

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
| 9 | Excellence — security, reliability, architecture, cultural transparency | ✅ done (landed incrementally across sessions) |
| **10** | **React SPA migration + cleanup** (April 2026) | ✅ **done** |
| **11** | **Community platform** (Grup C, 2026-04-21) | ✅ **done** |

### Phase 10 · React SPA migration (completed 2026-04-21)

- **Sprint 1**: Fork of cercol's React scaffold (JS + Vite 8 + Tailwind v4
  + React Router v7), adapted to TopQuaranta palette. Auth + ranking API +
  `/beta/top` live.
- **Sprint 2**: Public pages (artistes directory, artist/album/canço
  profiles, mapa stub). `Canco.slug` + nested SEO URLs.
- **Sprint 2D**: `/compte` card-grid dashboard + Perfil edit.
- **Sprint 3**: Full staff panel in React — 17 pages, shared chrome,
  sidebar navigation, ~30 DRF endpoints (`web/api/staff_views.py`).
- **Sprint 4**: Caddy flip — React served from `/`, Django kept for
  `/api/*`, `/compte/{2fa/*, login, logout, registre, activar}/*`,
  `/sitemap.xml`, `/robots.txt`. Legacy `/beta/*` redirects to root.
- **Feedback feature**: `Feedback` model + "Corregir" button on every
  content page (staff → edit link, user → modal, anonymous → login).
- **Spotify playlist sync**: one-time OAuth + daily cron.
- **ML slim**: 223 → 76 → 79 features (2026-04-22 added MB signals), Bayesian smoothing on rejection
  ratios, ROC-AUC 0.9994.
- **Visual `/staff/estat` dashboard**: live BD inventory, cron health,
  weekly flux, ML feature-importance chart.
- **Cleanup** (2026-04-21): removed ~7 900 LOC of dead Django-templates
  UI (39 templates + 10 view modules + legacy URLs); archived 6 one-shot
  management commands to `scripts/archived_commands/`.

### Phase 11 · Community platform — Grup C (completed 2026-04-21)

- New models `PerfilUsuari` (1:1 with Usuari, auto-created via signal)
  and `Publicacio` (markdown posts with visibilitat=interna/publica +
  estat pipeline). Migration `comptes/0008_perfilusuari_publicacio`.
- Post-registration guided onboarding at `/onboarding` with a single
  "Saltar" escape; accessible later from `/compte/perfil-usuari`.
- Community routes: `/comunitat` (mixed feed), `/comunitat/directori`
  (opt-in list of users), `/comunitat/publicar`, `/comunitat/public`
  (unauthenticated), `/comunitat/:pk` (detail).
- Staff moderation surfaces: `/staff/publicacions` (with
  publicar/rebutjar/despublicar + staff notes), `/staff/directori-usuaris`
  (toggle visibility flag on any profile).
- `PropostaArtista`: Deezer IDs now required (≥ 1) — without them no
  track can be verified. Localitzacions now required too and use the
  LocationCascade (territori → comarca → municipi, with ALT falling
  back to free-text manual entry).
- Public nav gains "Comunitat" link. Staff dashboard gains two tiles
  and sidebar gains two entries. `/api/v1/auth/me/` exposes
  `onboarding_complet` so first-time logins auto-route to the form.

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

### Sessió 17 follow-ups (from the cleanup sweep)

- [ ] **Remove `Artista.deezer_no_trobat` column**. The pendents and
      staff filters no longer read it; a signal keeps it in sync. The
      only remaining writers are in `obtenir_metadata.py`
      (lines 199-203, 230-231, 253-256). Once those lines are pruned
      a migration can drop the column. Blocked on a confident test
      run: the write side still marks artists Deezer-rejected so an
      audit trail survives on failure.
- [ ] **Migrate `pendents.html` + `artista_edit.html` to a shared
      `locality-cascade.js` module** (the deferred finding). The JS
      pattern is now duplicated across both templates; extract when
      either gets real work next time.
- [ ] **Drop `Album.lastfm_mbid`, `Canco.lastfm_mbid` references
      from CLAUDE_MODELS.md** — they were removed in D2 (2026-04-17)
      but the doc still mentions them in the Canco fields table. The
      wider sweep above already fixed the Artista row.

### Sessió 16 follow-ups

- [ ] When the Whisper backfill finishes (~27-28 April) re-evaluate the
      feature importances of the 4 Whisper features. If they climb into
      top-5, consider trimming the 200 TF-IDF features — they may have
      been carrying load Whisper now covers more cheaply.
- [ ] **Demucs → Whisper pipeline** as a recall booster for the 3-4 false
      negatives where Whisper hears `es` on Catalan tracks (Jonatan
      Penalba × 2, Adrien Broadway). Source-separate vocals first, then
      LID on `vocals.wav`. Cost ~55 s + 27 s per track (3× slower). Only
      worth it if the backfill surfaces a significant cluster of FN
      tracks that share the pattern. Deferred until we have data.
- [ ] Audit the 39 `ja` (Japanese) Whisper predictions in the current
      slice — suspicious cluster, likely Whisper hallucinating on
      vocalises / long sustained vowels / certain instrumentals. If
      the pattern is an indicator of *something* specific
      (instrumentals? scat? hardcore screaming?) it could be a cheap
      extra ML feature.
- [ ] Record a snapshot of the pre-Whisper RF baseline before the next
      retrain (`cp music/ml_model.joblib music/ml_model.baseline.joblib`)
      so we can A/B the classifier's precision on the same 48-clip set
      in a week and measure the real contribution of the Whisper
      features in isolation.

### Post-Excellence (apuntat durant la fase 9)
- [ ] **Naming consolidation**: unificar "ranking / rànquing / ranquing /
      top40" a **"top"** al llarg del codi, templates i URLs. El projecte
      es diu TopQuaranta; l'UX actual barreja cinc variants del mateix
      concepte. Caldrà una pantalla de naming + migració d'URLs amb 301.
- [ ] **Correu @topquaranta.cat**: configurar hosting de correu propi
      (Hetzner Hosted Mail, Fastmail o servidor propi). Aboliria el
      pseudofailback FileEmailBackend actual i permetria enviar correus
      de verificació, recuperacions, notificacions admin reals.
- [ ] **Redisseny estètic**: revisió visual completa del projecte. Les
      pàgines s'han anat afegint iterativament i barregen patrons
      diferents (staff-tool-card, ranking-entry, historial-entry,
      chart-bar...). Cal decidir un sistema visual coherent per a
      tot el projecte (public + staff), probablement basat en
      components nous de mm-design, i aplicar-lo transversalment.
      Inclou: tipografia jeràrquica, consistència d'espais, dark
      mode, accessibilitat (a11y WCAG AA), mobile polish real
      testing cross-device.

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
