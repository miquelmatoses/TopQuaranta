# CLAUDE_STAFF.md — Staff panel

> Custom `/staff/` admin interface. Replaced Django admin + Wagtail admin in
> Phase 7. Served by the same gunicorn as the public site (port 8083).

---

## 1. Access control

- URL prefix: `/staff/` (wired in `topquaranta/urls.py`).
- Every view is wrapped in `@staff_required` (`web/views/staff/__init__.py`).
  The decorator returns HTTP 403 for anonymous users and for authenticated users
  without `is_staff=True`. No role hierarchy beyond the flag.
- Login is shared with the public site (`/compte/login/`). After a successful
  login, staff users see an "Admin" shortcut in the header (via the
  `user_header_info` context processor).
- The two location API endpoints re-exported from `web/api/views.py`
  (`api_territoris`, `api_comarques`, `api_municipis`, `api_municipi_lookup`)
  are **not** wrapped in `@staff_required` — they expose public reference data
  (list of municipalities) and are shared with the public proposal form.

## 2. Shared helpers (`web/views/staff/__init__.py`)

```python
@staff_required                # permissions gate
def paginate(request, qs, per_page=50)    # Paginator helper
def apply_ordering(request, qs, allowed_fields, default)
    # Reads ?order= and ?dir= GET params, returns (ordered_qs, order, dir).
    # allowed_fields maps a URL key to an ORM path:
    #   {"nom": "nom", "artista": "artista__nom"}
    # Paired with the {% sort_header %} template tag in staff templates.
```

Every staff list view follows this pattern:

```python
@staff_required
def llista(request):
    qs = Model.objects.filter(...).select_related(...)
    qs, order, dir_ = apply_ordering(request, qs, ORDER_FIELDS, default="-created_at")
    page = paginate(request, qs)
    return render(request, "web/staff/<name>.html", {
        "staff_section": "<name>", "page": page,
        "current_order": order, "current_dir": dir_,
        # plus filter values for form repopulation
    })
```

## 3. URL map (`web/views/staff/urls.py`, prefix `/staff/`)

| Path | Name | View | Purpose |
|---|---|---|---|
| `/` | `dashboard` | `dashboard.dashboard` | Tool grid landing page |
| `cancons/` | `cancons` | `cancons.llista` | Track list + filters + bulk actions |
| `cancons/accio/` | `cancons_accio` | `cancons.accio` | POST handler for bulk actions |
| `cancons/<pk>/editar/` | `canco_editar` | `cancons.editar` | Single track edit |
| `albums/<pk>/editar/` | `album_editar` | `albums.editar` | Single album edit |
| `ranking/` | `ranking` | `ranking.llista` | Provisional ranking by territory |
| `ranking/accio/` | `ranking_accio` | `ranking.accio` | POST: reject track / artist |
| `artistes/` | `artistes` | `artistes.llista` | Artist list + filters + merge/approve |
| `artistes/accio/` | `artistes_accio` | `artistes.accio` | POST bulk actions |
| `artistes/<pk>/editar/` | `artista_editar` | `artistes.editar` | Artist edit (social, Deezer IDs, locations) |
| `artistes/pendents/` | `artistes_pendents` | `pendents.llista` | Auto-discovered artists (paginated 50/page) |
| `artistes/pendents/api/territoris/` | `api_territoris` | `pendents.api_territoris` | Cascading selects |
| `artistes/pendents/api/comarques/` | `api_comarques` | `pendents.api_comarques` | |
| `artistes/pendents/api/municipis/` | `api_municipis` | `pendents.api_municipis` | |
| `artistes/pendents/api/municipi-lookup/` | `api_municipi_lookup` | `pendents.api_municipi_lookup` | name+comarca → pk |
| `artistes/pendents/<pk>/aprovar/` | `api_aprovar` | `pendents.api_aprovar` | AJAX POST |
| `artistes/pendents/<pk>/descartar/` | `api_descartar` | `pendents.api_descartar` | AJAX POST |
| `historial/` | `historial` | `eines.historial` | Read-only decision log |
| `senyal/` | `senyal` | `eines.senyal` | Daily Last.fm signal inspector |
| `verificacio/` | `verificacio_artistes` | `eines.verificacio_artistes` | UserArtista (management requests) |
| `verificacio/<pk>/toggle/` | `verificacio_toggle` | | approve/unapprove |
| `verificacio/<pk>/rebutjar/` | `verificacio_rebutjar` | | reject (estat=rebutjat) |
| `propostes/` | `propostes_artistes` | `eines.propostes_artistes` | PropostaArtista list |
| `propostes/<pk>/` | `proposta_detall` | `eines.proposta_detall` | Full proposal detail |
| `propostes/<pk>/aprovar/` | `proposta_aprovar` | | Create Artista + links in atomic tx |
| `propostes/<pk>/rebutjar/` | `proposta_rebutjar` | | estat=rebutjat |
| `configuracio/` | `configuracio` | `eines.configuracio` | ConfiguracioGlobal edit form |
| `auditlog/` | `auditlog` | `eines.auditlog` | Read-only StaffAuditLog — append-only trail of destructive actions (R9) |
| `usuaris/` | `usuaris` | `usuaris.llista` | List + filters + search of registered users |
| `usuaris/<pk>/` | `usuari_detall` | `usuaris.detall` | Full user profile with propostes, sol·licituds, audit |
| `usuaris/<pk>/toggle-actiu/` | `usuari_toggle_actiu` | `usuaris.toggle_actiu` | POST — (de)activate account (not self / not staff) |
| `usuaris/<pk>/reset-2fa/` | `usuari_reset_2fa` | `usuaris.reset_2fa` | POST — wipe TOTP + static devices |

## 4. Views by module

- **`dashboard.py`** — single view, renders a grid of tool cards.
- **`cancons.py`** — `llista` (filters: verificada, ml_classe, date range,
  search), `accio` (bulk aprovar / rebutjar / rebutjar_album, requires motiu
  for rejects — enforced client-side + server-side), `editar`.
- **`albums.py`** — `editar` (nom, data, tipus, deezer_id, imatge_url,
  descartat + read-only artista + track list).
- **`ranking.py`** — `llista` (per-territory provisional ranking with bulk
  reject), `accio` (rebutjar_canco / rebutjar_artista with motiu).
- **`artistes.py`** — `llista` (filters: aprovat, deezer, territori; search by
  nom), `accio` (aprovar, marcar_sense_deezer, fusionar), `editar`
  (cascading selects for multiple locations, 10 social links, multiple
  Deezer IDs with +/− buttons).
- **`pendents.py`** — `llista` (queue of auto-discovered artists, sortable
  by nom or nb_verif). Also hosts the `api_aprovar` / `api_descartar` AJAX
  endpoints and re-exports the 4 location lookup endpoints from
  `web/api/views.py` (staff URL names point to the shared functions).
- **`eines.py`** — "tools" grab-bag: historial, senyal, verificacio,
  propostes, configuracio.

## 5. Two solicitud flows

The system has two parallel flows, deliberately separated:

1. **`UserArtista` (management request)** — a user wants to manage an artist
   **already in the system**. Staff decides via `/staff/verificacio/`:
   - toggle button: flips `verificat` + sets `estat` to aprovat/pendent
   - reject button: sets `estat=rebutjat` (record kept for audit)

2. **`PropostaArtista` (new artist proposal)** — a user wants an artist that
   **does not yet exist**. The form captures a full profile: nom, 9 social
   links, comma-separated Deezer IDs, and a JSON array of locations. Staff
   decides via `/staff/propostes/<pk>/`:
   - approve: `proposta_aprovar` runs a `transaction.atomic()` that creates
     the `Artista`, its `ArtistaDeezer` entries (first one marked principal),
     the `ArtistaLocalitat` entries (municipi FK for PPCC locations, manual
     text for others), and copies all 9 social URL fields. Sets
     `proposta.estat=aprovat` and `proposta.artista_creat=<new artista>`.
   - reject: `estat=rebutjat`, record preserved.

Pending queue (`/staff/artistes/pendents/`) is separate from both flows — it
holds artists auto-discovered by the Deezer pipeline, which also need approval
before entering the ranking.

## 6. Templates (`web/templates/web/staff/`)

### Layout
- **`base_staff.html`** — extends `web/base.html`, renders the staff nav
  (Inici, Cançons, Ranking, Artistes, Pendents, Historial, Sol·licituds,
  Propostes, Configuració) and flashes `messages`.
- **`_pagination.html`** — reused by every list view. Expects a `page` object
  from `paginate()`.
- **`_select_all.html`** — reusable `<script>` for the master "Tot" checkbox.
  Include once after a table that has an `#select-all` input and `.row-check`
  row checkboxes.
- **`confirmar_accio.html`** — intermediate confirmation page for dangerous
  actions; shows the motiu select.

### Custom template tags (`web/templatetags/staff_tags.py`)
- **`{% sort_header "param" "Label" %}`** — renders a `<th>` with an anchor
  toggling the `?order=` / `?dir=` GET params. Pairs with `apply_ordering`.
- **`{% ml_badge canco %}`** — colored A/B/C badge with confidence tooltip.
- **`{% territori_list artista %}`** — comma-separated territory codes.
- **`{% query_string ... %}`** — URL-encode helper for pagination + filters.
- **`{% lastfm_encode ... %}`** — URL-encode a name for Last.fm deep links.

## 7. CSS conventions

Staff-specific styles live in `web/static/web/css/style.css` under the section
`/* === STAFF PANEL === */`. Prefixed `.staff-*`: `.staff-layout`,
`.staff-nav`, `.staff-content`, `.staff-table`, `.staff-table-wrap`,
`.staff-filters`, `.staff-actions-bar`, `.staff-action-select`, `.staff-edit-link`,
`.staff-badge-ok` / `.staff-badge-no`, `.staff-msg--{success,error,warning,info}`.
All use `var(--mm-*)` tokens.

## 8. Adding a new staff page

1. Create the view in the appropriate module under `web/views/staff/` using
   the `@staff_required` + `apply_ordering` + `paginate` pattern.
2. Add a URL entry in `web/views/staff/urls.py`.
3. Create the template in `web/templates/web/staff/` extending
   `base_staff.html`. Reuse `_pagination.html` and `_select_all.html`.
4. If it has filter/sort columns, declare the `ORDER_FIELDS` dict in the view
   module and use `{% sort_header %}` in the template `<th>`.
5. If it needs a link from the main dashboard, add a tool card in
   `templates/web/staff/dashboard.html` pointing to the new URL.
