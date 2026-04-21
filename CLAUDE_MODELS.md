# CLAUDE_MODELS.md — Django Data Models

> Post-Sprint-4 snapshot (2026-04-21). All models are Django-managed. No
> unmanaged / legacy models remain. DB: 37 tables total (18 domain + Django
> internals: auth_*, django_session, axes_*, otp_totp_*, otp_static_*,
> django_migrations, django_content_type).

---

## music/

### `Territori` — `music_territori`
Reference data. 10 rows, managed via data migration.
- `codi` CharField(4, pk) — `CAT, VAL, BAL, PPCC, ALT, CNO, AND, FRA, ALG, CAR`
- `nom` CharField(50)

### `Municipi` — `music_municipi`
1,825 municipalities, populated from legacy in migration `0025`.
- `nom` CharField(255)
- `comarca` CharField(255)
- `territori` FK → Territori (PROTECT, related_name="municipis")
- `unique_together = [("nom", "comarca")]`

### `Artista` — `music_artista`
Core model. Territories are auto-synced from `ArtistaLocalitat` via signals;
**do not edit the `territoris` M2M directly**.

Identity: `spotify_id` (legacy), `deezer_id` (nullable BigInteger), `slug`.
`lastfm_nom` holds the exact Last.fm name for track.getInfo calls.

| Group | Fields |
|---|---|
| Core | `nom`, `slug`, `lastfm_nom` |
| Approval state | `aprovat` ✦, `pendent_review` ✦ |
| Discovery provenance (immutable) | `auto_descobert`, `font_descoberta` |
| Discovery cache | `deezer_no_trobat`, `last_checked_deezer` |
| Deezer meta | `deezer_nb_fan`, `deezer_nb_album`, `deezer_nom`, `deezer_nom_similitud` |
| Last.fm | `lastfm_te_scrobbles` ✦ |
| Territories | `territoris` M2M (auto-synced) |
| Social links | 10 URLFields, listed in `SOCIAL_LINK_FIELDS` |
| Genre | `genere` (free text), `percentatge_femeni` (choices) |
| `created_at` | auto_now_add |

✦ = `db_index=True`.

### Approval state machine (since migration 0042)

`aprovat` and `pendent_review` are orthogonal and ENFORCED by
`CheckConstraint("artista_no_aprovat_pendent_review")`:

| `aprovat` | `pendent_review` | Meaning |
|---|---|---|
| ✅ True  | ❌ False | **Live.** Tracks can enter the ranking. |
| ❌ False | ✅ True  | **In the pendents queue** (`/staff/artistes/pendents/`). |
| ❌ False | ❌ False | **Descartat.** Row kept for FK integrity; not in any queue. |
| ✅ True  | ✅ True  | **FORBIDDEN** by the DB constraint. |

`auto_descobert` is a separate immutable record of *how* the artist
got into the system (True for feat.-resolution / Viasona / auto
sources, False for manual creation and legacy imports). It is NEVER
flipped by the approval flow — historical code used it as a
queue-membership flag, a conflation the 0042 migration resolved.

`deezer_no_trobat` is a cache: "Deezer search failed for this
artist, don't re-query immediately". The pendents filter no longer
reads it (uses `deezer_ids__isnull` directly); it remains a write-path
hint for `obtenir_novetats` / `obtenir_metadata`. A `post_save`
receiver on `ArtistaDeezer` clears the flag whenever a real Deezer
link appears.

**Relations (related_name):**
- `localitats` — reverse of `ArtistaLocalitat.artista`
- `cancons` — reverse of `Canco.artista` (main artist)
- `participacions` — reverse of `Canco.artistes_col` (collaborator M2M)
- `albums` — reverse of `Album.artista`
- `deezer_ids` — reverse of `ArtistaDeezer.artista`

**Methods:**
- `get_territoris()` → list of codes
- `sync_territoris_from_localitats()` — recomputes M2M from ArtistaLocalitat → Municipi
- `deezer_id_principal` (property) — primary Deezer ID from ArtistaDeezer
- `all_deezer_ids` (property) — list of all Deezer IDs
- `clean()` — requires a location when `aprovat=True`

### `ArtistaDeezer` — `music_artistadeezer`
1:N — one artist may have multiple Deezer IDs (name collisions across releases).
- `artista` FK → Artista (CASCADE, related_name="deezer_ids")
- `deezer_id` BigInteger(unique)
- `principal` BooleanField — the canonical one, used by `deezer_id_principal`

### `ArtistaLocalitat` — `music_artistalocalitat`
N:M between Artista and Municipi, with optional free-text override.
- `artista` FK → Artista (CASCADE, related_name="localitats")
- `municipi` FK → Municipi (PROTECT, nullable) — NULL for non-PPCC locations
- `localitat_manual` CharField — used when `municipi` is NULL
- `descripcio` CharField — e.g. "nascut a"

Signals (`music/signals.py`): post_save + post_delete call
`artista.sync_territoris_from_localitats()` to keep the Artista.territoris M2M
current. This is what makes `algorisme.py`'s raw SQL territory join work.

### `Album` — `music_album`
- `spotify_id`, `deezer_id`, `slug`
- `artista` FK → Artista (CASCADE, related_name="albums")
- `nom`, `data_llancament`, `tipus` ("album" / "single" / "ep")
- `imatge_url`
- `cancons_obtingudes` ✦ — True when tracks have been pulled from Deezer
- `descartat` ✦ — True if all tracks were rejected; skipped by obtenir_novetats
- `created_at`

### `Canco` — `music_canco`
A single track. Each track exists once (not duplicated per territory).
Territory derived via `artista.territoris ∪ artistes_col.territoris`.

| Group | Fields |
|---|---|
| Identity | `spotify_id`, `deezer_id`, `isrc`, `slug`? (no — only album) |
| Relations | `album` FK, `artista` FK, `artistes_col` M2M |
| Names | `nom`, `lastfm_nom` |
| Flags | `verificada` ✦, `activa` ✦, `lastfm_confirmed` |
| Dates | `data_llancament` ✦, `created_at` |
| Metadata | `durada_ms`, `preview_url` |
| ML | `ml_classe` ✦ (A/B/C), `ml_confianca` (float) |
| Whisper LID | `whisper_lang` ✦, `whisper_p`, `whisper_all_probs` (JSON), `whisper_processat_at` ✦ |

- `lastfm_lookup_nom` (property) — falls back to `nom` if `lastfm_nom` is empty
- `get_territoris()` — returns union of main + collaborator territories

**Whisper fields** (populated nightly by `analitzar_whisper` at 01:30
UTC). `whisper_all_probs` is the full 99-language distribution —
richer than the top-1 shortcut (`whisper_lang` + `whisper_p`) and fed
into the RF classifier as 4 features (`whisper_p_ca`, `whisper_p_es`,
`whisper_p_en`, `whisper_margin_ca`). Eval on a 48-clip ground-truth
set (`scripts/model_comparison/resultats.md`): precision(ca) = 100 %,
recall(ca) = 81 %, specificity = 100 %.

### `ArtistaDeezer` invariant (2026-04-21)
Signal `unapprove_on_last_deezer_removed` (post_delete on ArtistaDeezer)
enforces: `aprovat=True ⇒ ≥ 1 ArtistaDeezer`. When the last Deezer ID
of an approved artist is removed — either via `rebutjar_artista` mass
delete or a staff PATCH that empties the deezer_ids list — the signal
flips `aprovat=False, pendent_review=False` in one UPDATE.

### `StaffAuditLog` — `music_staffauditlog`
R9. Append-only log of every destructive staff action. Written via
`music/audit.py::log_staff_action(request, action, target=obj,
**metadata)`. `target_type`, `target_id` and `target_label` are snapshots
so rows stay meaningful after the target is deleted. `metadata` is a
JSONField for action-specific context (motiu, diff, counts).

### `SpotifyAuth` — `music_spotifyauth` (singleton, 2026-04)
Holds the admin's Spotify OAuth refresh token after the one-time
`autoritzar_spotify` dance. Fields: `id=1` forced in save(),
`refresh_token`, `scope`, `spotify_user_id`, `updated_at`.

### `SpotifyPlaylist` — `music_spotifyplaylist`
One row per managed Spotify playlist. Fields: `codi` (slug, unique),
`kind` (`top` | `novetats`), `territori` (when kind=top), plus last-sync
metadata: `spotify_playlist_id`, `last_sync_at`, `last_sync_ok`,
`last_sync_msg`, `last_n_tracks`, `last_n_matched`. Populated by
`seed_spotify_playlists` (archived) + `configurar_spotify_playlists`
once per deployment.

### `HistorialRevisio` — `music_historialrevisio`
Immutable audit trail of every approval / rejection. Read-only by convention;
written by `music/services.py` via `verificacio.crear_historial()`.

Records a snapshot of the track and artist at decision time plus the ML class
and confidence — this allows the ML model to be retrained from its own history
(`music/ml.py::entrenar_model`).

- **Identifiers:** `canco_deezer_id`, `canco_spotify_id`, `canco_isrc`
- **Track snapshot:** `canco_nom`, `album_nom`, `data_llancament`, `isrc_prefix`
- **Artist snapshot:** `artista_nom`, `artista_territori`, `artista_deezer_id`,
  `artista_deezer_nb_fan`, `artista_deezer_nb_album`, `artista_nom_deezer`,
  `artista_nom_similitud`
- **ML snapshot:** `ml_classe_decisio`, `ml_confianca_decisio`
- **Decision:** `decisio` (aprovada/rebutjada), `motiu` (see `Canco.MOTIUS`)
- `created_at`

---

## ranking/

### `ConfiguracioGlobal` — `ranking_configuracioglobal`
Singleton. `save()` forces `pk=1`, `load()` classmethod uses get_or_create.
Holds the 14 ranking coefficients + `min_cancons_ranking_propi` (threshold for
optional territories to get their own ranking). See `CLAUDE_ALGORITHM.md`.

### `SenyalDiari` — `ranking_senyaldiari`
Daily Last.fm signal per track. One row per `(canco, data)`.
- `canco` FK, `data` DateField
- `lastfm_playcount` BigInt (cumulative total plays), `lastfm_listeners` Int
- `score_entrada` FloatField — percent_rank normalization (0-100)
- `error` Bool, `error_msg` Text
- Indexes: `(canco, data)` unique, `(data, error)`

### `RankingSetmanal` — `ranking_rankingsetmanal`
Weekly official ranking. `setmana` = Monday of the ranking ISO week.
- `canco` FK, `territori` CharField(4), `setmana` DateField
- `posicio` PositiveSmallInt, `score_setmanal` Float
- Unique: `(canco, territori, setmana)`. Index: `(setmana, territori)`

### `RankingProvisional` — `ranking_rankingprovisional`
Rolling daily ranking. Truncated and rebuilt on each run.
- `canco` FK, `territori` CharField(4)
- `posicio`, `score_setmanal` (same semantics as setmanal despite the name)
- `lastfm_playcount`, `dies_en_top`
- `data_calcul` DateField(auto_now)
- Unique: `(canco, territori)`. Index: `(territori, posicio)`

---

## comptes/

### `Usuari` — `auth_user`
Custom user model extending `AbstractUser`. Reuses the `auth_user` table name
because `AUTH_USER_MODEL = "comptes.Usuari"` is the only user in the project.

### `UserArtista` — `comptes_userartista`
Request from a user to manage an **existing** artist.
- `usuari` FK (CASCADE)
- `artista` FK (CASCADE) — **non-nullable**
- `sollicitud_text` TextField (≥20 chars on form)
- `verificat` BooleanField (legacy flag, maps to `estat=="aprovat"`)
- `estat` CharField: `pendent` / `aprovat` / `rebutjat`
- `created_at`
- Unique: `(usuari, artista)` — one request per user per artist

### `PropostaArtista` — `comptes_propostaartista`
Proposal for a **new** artist not yet in the system.
- `usuari` FK
- `nom`, `justificacio`
- Social links (9 URLFields)
- `deezer_ids` CharField — comma-separated list
- `localitzacions_json` TextField — JSON array of `{"municipi_id": n}` or `{"manual": "..."}`
- `estat` (same values as UserArtista)
- `artista_creat` FK → Artista (SET_NULL) — set on approval
- `created_at`

**On approval** (`/api/v1/staff/propostes/<pk>/aprovar/` in React): creates
`Artista`, `ArtistaDeezer` per Deezer ID, `ArtistaLocalitat` per location,
copies social link fields — all inside one `transaction.atomic()`. Links the
new Artista back via `artista_creat`.

### `PerfilUsuari` — `comptes_perfilusuari` (Grup C, 2026-04)
1:1 extension of `Usuari`. Created automatically on user creation via
`comptes/signals.py::create_perfil_usuari` (post_save on AUTH_USER_MODEL),
so every account row always has a paired profile — downstream code can
assume `usuari.perfil` exists.

- `usuari` OneToOne → Usuari (CASCADE, related_name="perfil")
- `nom_public` CharField(120)
- `localitat` FK → Municipi (SET_NULL, nullable)
- `imatge_url`, `bio` (≤2000)
- Social URLs (10 fields, listed in `SOCIAL_FIELDS` — same shape as
  `Artista.SOCIAL_LINK_FIELDS` plus `instagram_url`)
- `rol_musical` CharField(choices=escoltador/music/productor/altre)
- `instruments` CharField(255, free text)
- `visible_directori` Bool (db_index=True) — gates `/comunitat/directori`
  listing; default False (opt-in)
- `obert_colaboracions` Bool
- `onboarding_complet` Bool — set after the user either fills the
  onboarding form or explicitly skips it. Surfaced on `/auth/me/` so
  the SPA can auto-route first-time users to `/onboarding`.

### `Publicacio` — `comptes_publicacio` (Grup C)
User-authored content at `/comunitat`. Staff bypasses the pending queue
(posts auto-land in `publicat` regardless of visibilitat). Non-staff
with `visibilitat=interna` posts directly; with `visibilitat=publica`
the post goes `pendent` until staff approves.

- `autor` FK → Usuari (CASCADE, related_name="publicacions")
- `titol` (≤200), `cos` (≤20 000 chars, markdown)
- `visibilitat` choices: `interna` (registered users only) / `publica` (public)
- `estat` choices: `esborrany` / `pendent` / `publicat` / `rebutjat`
- `notes_staff` TextField — reject reason shown to author
- `publicat_at` — set on transition into `publicat`
- `created_at` / `updated_at`
- Indexes: `(estat, -created_at)`, `(visibilitat, estat, -publicat_at)`

### `Feedback` — `comptes_feedback` (2026-04)
User-submitted correction reports filed from public artist/album/canço
pages via the "Corregir" button.

- `usuari` FK → Usuari (CASCADE). Non-null: anonymous visitors are
  bounced to `/compte/accedir` before they can file.
- `url` CharField — the page the reporter was on.
- `target_type` CharField (artista/album/canco/altres), `target_pk`
  (nullable), `target_slug`, `target_label` — snapshot so the row
  stays meaningful after rename/delete.
- `missatge` TextField.
- `resolt` Bool, `notes_staff` TextField, `resolt_at`, `resolt_per`
  FK → Usuari (SET_NULL).
- Indexes: `(resolt, -created_at)`, `(target_type, target_pk)`.

---

## Migrations

- `music/` 0001–0046. Latest: `0046_spotifyauth_spotifyplaylist`.
  Notable recent: `0042_artista_pendent_review_constraint` (CheckConstraint
  on `aprovat` / `pendent_review`), `0045_canco_slug` (unique slug on Canco),
  `0044_drop_deezer_no_trobat` (dropped the stale cache flag).
- `ranking/` 0001–0004. Latest: `0004_rankingprovisional`.
- `comptes/` 0001–0008. Latest: `0008_perfilusuari_publicacio`.
