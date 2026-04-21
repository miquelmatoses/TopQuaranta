# CLAUDE_STAFF.md — Staff panel

> React SPA admin interface living at `/staff/*` in `web-react/src/pages/staff/`,
> backed by the `/api/v1/staff/*` DRF endpoints in `web/api/staff_views.py`.
> Replaced the Django-template staff panel in Sprint 4 (April 2026).

---

## 1. Architecture at a glance

```
Browser                   Caddy                    gunicorn :8083
  │                         │                           │
  │  GET /staff/pendents    │                           │
  │ ───────────────────────▶│                           │
  │                         │  (no path match in        │
  │                         │   Django allow-list)      │
  │                         │                           │
  │                         │  ▶ serve web-react/dist/  │
  │  React SPA              │                           │
  │                         │                           │
  │  fetch /api/v1/staff/…  │                           │
  │ ───────────────────────▶│ ────────────────────────▶ │
  │                         │                           │ IsStaff check
  │                         │                           │ → DRF JSON
  │                ◀──────────────────────────── JSON ──┤
  │  render table           │                           │
```

The SPA owns the visual layer + routing. The API owns the data + permission
gating. No Django templates are rendered for staff anymore.

## 2. Access control

- **Route gate (client)**: `components/AdminRoute.jsx` wraps every `/staff/*`
  route. It bounces non-staff users to `/compte/accedir` and staff users
  whose session hasn't been OTP-verified to `/compte/2fa/verificar/` (a full-
  page redirect — the Django 2FA form lives in the Caddy allow-list).

- **Permission gate (server)**: `IsStaff` DRF permission (`staff_views.py`)
  requires `user.is_authenticated AND user.is_staff AND user.is_verified()`.
  Every `/api/v1/staff/*` endpoint declares `@permission_classes([IsStaff])`.

- **Session**: same `sessionid` cookie as the public SPA. CSRF token comes
  from the `csrftoken` cookie and is echoed back as `X-CSRFToken` on writes
  by `web-react/src/lib/api.js`.

- **Self-elevation prevention**: toggling `is_staff` is intentionally not
  exposed from the UI. Admins must flip that via `manage.py` + SSH.

## 3. API surface (`web/api/staff_views.py`)

All endpoints are under `/api/v1/staff/` and return JSON. Shared helpers:
`_paginate(qs, request)` returns `(page, meta)` where `meta` is
`{page, num_pages, total, per_page, has_next, has_previous}`.

### Dashboard & estat
| Method | Path | Purpose |
|---|---|---|
| GET | `/staff/dashboard/` | Landing counters (artistes pendents, cançons no verificades, propostes, sol·licituds, feedback, usuaris). |
| GET | `/staff/estat/` | Full system health: BD inventory, Whisper coverage, ranking, cron status, ML model stats + feature importances, weekly flux + target. |

### Pendents (auto-discovered artists)
| Method | Path | Purpose |
|---|---|---|
| GET | `/staff/pendents/?q=&page=` | Pending artists with `nb_verif` annotation. |
| POST | `/staff/pendents/<pk>/aprovar/` | Body: `{deezer_id?, municipi_id? \| manual?}`. Approves, clears `pendent_review`. |
| POST | `/staff/pendents/<pk>/descartar/` | Deletes if no verified tracks; else only clears `pendent_review`. |

### Artistes
| Method | Path | Purpose |
|---|---|---|
| GET | `/staff/artistes/` | Filters: `q`, `aprovat`, `deezer`, `territori`. |
| GET | `/staff/artistes/search/?q=` | Typeahead for pickers. Returns up to 10 results. |
| POST | `/staff/artistes/crear/` | Body: `nom`, `lastfm_nom?`, `deezer_id?`. |
| GET/PATCH | `/staff/artistes/<pk>/` | Detail + replace-semantics PATCH over `nom`, `lastfm_nom`, `genere`, `percentatge_femeni`, `aprovat`, social URLs, `localitats[]`, `deezer_ids[]`. |

### Cançons
| Method | Path | Purpose |
|---|---|---|
| GET | `/staff/cancons/` | Filters: `q`, `verificada`, `ml_classe`, `whisper`, `deezer`, `sort`, `artista_pk`. |
| POST | `/staff/cancons/accio/` | Bulk `aprovar` / `rebutjar` with `motiu`. `artista_incorrecte` → cascades to `rebutjar_artista`; `album_incorrecte` → `rebutjar_album`. |
| GET/PATCH | `/staff/cancons/<pk>/` | Detail + PATCH incl. `artista_pk` reassignment + `artistes_col_pks` replace. |

### Albums
| Method | Path | Purpose |
|---|---|---|
| GET | `/staff/albums/` | List with `n_cancons` / `n_verificades` annotations, filter by `tipus`, `descartat`, `artista_pk`. |
| GET/PATCH | `/staff/albums/<pk>/` | Detail incl. track list with per-track collab map. PATCH accepts `artista_pk` + `cascade_cancons` to also re-point tracks. |

### Ranking (provisional)
| Method | Path | Purpose |
|---|---|---|
| GET | `/staff/ranking/?territori=CAT` | Top-40 provisional + territori list + motius. |
| POST | `/staff/ranking/accio/` | Bulk `rebutjar_canco` / `rebutjar_artista` with `motiu`. |

### Propostes (user proposals) & Sol·licituds (management requests)
| Method | Path | Purpose |
|---|---|---|
| GET | `/staff/propostes/` | Filter by `estat`. |
| GET | `/staff/propostes/<pk>/` | Detail (justificació, localitzacions, Deezer IDs, social). |
| POST | `/staff/propostes/<pk>/aprovar/` | Creates the Artista in one transaction. |
| POST | `/staff/propostes/<pk>/rebutjar/` | Marks rejected. |
| GET | `/staff/solicituds/` | UserArtista list. |
| POST | `/staff/solicituds/<pk>/toggle/` | Toggle verificat. |
| POST | `/staff/solicituds/<pk>/rebutjar/` | Mark rejected. |

### Feedback, senyal, historial, configuració, auditlog, usuaris
| Method | Path | Purpose |
|---|---|---|
| GET | `/staff/feedback/` | User correction reports with filter + search. |
| POST | `/staff/feedback/<pk>/resolve/` | Toggle resolved + attach staff notes. |
| GET | `/staff/senyal/` | Daily Last.fm signal inspector. |
| POST | `/staff/senyal/<canco_pk>/acceptar-correccio/` | R5: accept Last.fm's autocorrect for a track. |
| GET | `/staff/historial/` | Read-only HistorialRevisio. |
| GET/PATCH | `/staff/configuracio/` | ConfiguracioGlobal coeffs; PATCH logs field-level diff to audit. |
| GET | `/staff/auditlog/` | Read-only StaffAuditLog (R9). |
| GET | `/staff/usuaris/` | User list with filters. |
| GET | `/staff/usuaris/<pk>/` | Detail with propostes + sol·licituds + audit. |
| POST | `/staff/usuaris/<pk>/toggle-actiu/` | Deactivate / reactivate (never self, never staff). |
| POST | `/staff/usuaris/<pk>/reset-2fa/` | Wipe TOTP + static devices. |

## 4. React surface (`web-react/src/pages/staff/`)

- **Layout** — `components/StaffLayout.jsx` renders a dark vertical sidebar
  nested inside the public yellow header. The nav lists: Panel · Estat ·
  Pendents · Artistes · Cançons · Albums · Ranking prov. · Propostes ·
  Sol·licituds · Feedback · Senyal · Historial · Configuració · Auditoria ·
  Usuaris.
- **Shared chrome** — `components/staff/StaffTable.jsx` exports `TableCard`,
  `Table`, `THead/Th/Td/Tr`, `Btn`, `Pill`, `Input`, `Select`, `Pagination`,
  `PageHeader`, `EmptyState`. Keeps every page under ~150 LOC.
- **Typeahead pickers** — `staff/ArtistaPicker.jsx` (single) and
  `staff/ArtistesColPicker.jsx` (multi), both backed by
  `/staff/artistes/search/`. Used on edit pages for reassignment +
  collaborator editing.
- **Location cascade** — `staff/LocationCascade.jsx` pairs
  territori→comarca→municipi selects. Special case: when `territori=ALT`
  the comarca/municipi selects collapse into a single free-text input
  (saved to `ArtistaLocalitat.localitat_manual`).

### Pages (17 total)

`StaffDashboardPage` · `EstatPage` (visual health dashboard) · `PendentsPage` ·
`StaffArtistesPage` · `ArtistaCrearPage` · `ArtistaEditPage` ·
`StaffCanconsPage` · `CancoEditPage` · `StaffAlbumsPage` · `AlbumEditPage` ·
`StaffRankingPage` · `PropostesPage` · `PropostaDetailPage` ·
`SolicitudsPage` · `SenyalPage` · `HistorialPage` · `ConfiguracioPage` ·
`AuditlogPage` · `UsuarisPage` · `UsuariDetailPage` · `FeedbackPage`.

## 5. Motius de rebuig — semantics

`music.constants.MOTIUS_VALIDS` = `{no_catala, artista_incorrecte,
album_incorrecte, no_musica}`. The motiu decides which service function
gets called by the bulk-action endpoint:

| Motiu | Escalation | Side effects | Safe for |
|---|---|---|---|
| `no_catala` | per-Canço `rebutjar_canco` | deletes + writes HistorialRevisio with this motiu | track-level corrections |
| `no_musica` | per-Canço `rebutjar_canco` | same as above | interviews, samplers, empty tracks |
| `album_incorrecte` | per-Album `rebutjar_album` | deletes all unverified tracks of the album + marks `album.descartat=True` | **Deezer-blurred homonym albums (e.g. wrong-Aion's album)** — blast radius contained |
| `artista_incorrecte` | per-Artista `rebutjar_artista` | deletes all unverified tracks + clears all Deezer IDs + marks all albums descartat | an artist whose Deezer profile is entirely wrong; **destructive of real artists with the same name** |

All four write `HistorialRevisio` with `artista_nom` = canço's main artist.
Collaborators (`artistes_col`) are NOT persisted in the decision log, so
rejecting a track with Juan Magan as collab does not taint Juan Magan's
future classification.

## 6. Invariants enforced by signals

- **`aprovat=True ⇒ ≥ 1 ArtistaDeezer`** — `music/signals.py` post_delete
  on `ArtistaDeezer`. When the last Deezer ID of an approved artist is
  removed, `aprovat` is flipped to False (and `pendent_review` to False)
  in one UPDATE. Prevents phantom approved artists invisible to
  `obtenir_novetats`.
- **D5: main artist ≠ collaborator on same canço** — `m2m_changed` on
  `Canco.artistes_col`. Raises `ValidationError` on pre_add / pre_set.
- **`artista_no_aprovat_pendent_review`** — DB CheckConstraint (migration
  0042). `aprovat=True AND pendent_review=True` is impossible.

## 7. Adding a new staff page

1. Add the view in `web/api/staff_views.py` using `@api_view` +
   `@permission_classes([IsStaff])`. Use `_paginate()` for lists.
2. Register the route in `web/api/urls.py` under the `staff/` prefix.
3. Create the React page in `web-react/src/pages/staff/`. Use the
   `StaffTable.jsx` primitives. Seed filters from `useSearchParams` if the
   URL should be shareable.
4. Wire the route in `App.jsx` inside the `/staff/*` switch.
5. Add the sidebar link in `components/StaffLayout.jsx` if it's user-facing.
6. Drop a tile in `StaffDashboardPage.jsx` if it should surface on the
   landing grid.
7. If the action is destructive, call `log_staff_action(request, "<verb>",
   target=obj, **metadata)` from the backend. The `StaffAuditLog.ACTION_CHOICES`
   tuple accepts new values without a schema migration (only the UI filter
   needs to be updated).
