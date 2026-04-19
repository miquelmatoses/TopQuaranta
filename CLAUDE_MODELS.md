# CLAUDE_MODELS.md — Django Data Models

> Post-Phase-8 snapshot. All models are Django-managed. No unmanaged / legacy
> models remain. DB: 25 tables, 44 MB.

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

**On approval** (`staff.eines.proposta_aprovar`): creates `Artista`,
`ArtistaDeezer` per Deezer ID, `ArtistaLocalitat` per location, copies social
link fields — all inside one `transaction.atomic()`. Links the new Artista back
via `artista_creat`.

---

## Migrations

- `music/` 0001–0026. Latest: `0026_add_indexes_audit` (adds `db_index=True` on
  Canco.{verificada, activa, data_llancament}, Artista.aprovat,
  Album.{cancons_obtingudes, descartat}).
- `ranking/` 0001–0004. Latest: `0004_rankingprovisional`.
- `comptes/` 0001–0004. Latest: `0004_proposta_artista_estat`.
- `music/0025_populate_municipis_and_localitats` is tolerant to the dropped
  legacy `municipis` table — it no-ops on fresh installs.
