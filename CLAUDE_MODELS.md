# CLAUDE_MODELS.md — Django Data Models

> All models under Django migrations. Never use raw DDL outside migrations.

---

## music/models.py

### Territori
Territory for Catalan-language music rankings. 10 territories managed via data migrations.

- `codi` — CharField(max_length=4, primary_key=True): CAT, VAL, BAL, CNO, AND, FRA, ALG, CAR, ALT, PPCC
- `nom` — CharField(max_length=50)

### Artista
A music artist tracked by TopQuaranta. Territory is M2M (e.g. Marala → CAT+VAL+BAL).

- `spotify_id` — CharField(unique, null): Spotify artist ID (legacy)
- `deezer_id` — BigIntegerField(unique, null): Deezer artist ID
- `lastfm_nom` — CharField: exact name for Last.fm API calls
- `lastfm_mbid` — CharField(null): MusicBrainz ID
- `nom` — CharField
- `territoris` — M2M to Territori
- `deezer_no_trobat` — BooleanField: True if Deezer search failed ISRC validation
- `deezer_nb_fan` — IntegerField(null): Deezer fans count
- `deezer_nb_album` — IntegerField(null): Deezer album count
- `deezer_nom` — CharField: name as returned by Deezer
- `deezer_nom_similitud` — FloatField(null): SequenceMatcher ratio vs `nom`
- `auto_descobert` — BooleanField: auto-discovered by pipeline
- `font_descoberta` — CharField: 'viasona', 'collaborador', 'manual'
- `aprovat` — BooleanField(default=True): False = pending human review
- `localitat`, `comarca`, `provincia` — CharField: geographic location
- `last_checked_deezer` — DateTimeField(null): last Deezer metadata check
- `created_at` — DateTimeField(auto_now_add)

Methods:
- `get_territoris()` → list of territory codes
- `clean()` — validates localitat/comarca required when aprovat=True

### Album
- `spotify_id` — CharField(unique, null)
- `deezer_id` — BigIntegerField(unique, null)
- `artista` — FK to Artista
- `nom` — CharField
- `data_llancament` — DateField(null)
- `tipus` — CharField: album/single/ep
- `imatge_url` — URLField
- `cancons_obtingudes` — BooleanField: tracks fetched from Deezer
- `descartat` — BooleanField: rejected album, skipped by obtenir_novetats
- `created_at` — DateTimeField(auto_now_add)

### Canco
A single track. Exists ONCE (not duplicated per territory like legacy).

- `spotify_id` — CharField(unique, null)
- `deezer_id` — BigIntegerField(unique, null)
- `isrc` — CharField: International Standard Recording Code
- `album` — FK to Album
- `artista` — FK to Artista (main artist for display)
- `artistes_col` — M2M to Artista (collaborators — track appears in their territories too)
- `nom` — CharField
- `lastfm_nom` — CharField: track name as returned by Last.fm
- `lastfm_mbid` — CharField: MusicBrainz track ID
- `lastfm_verificat` — BooleanField
- `verificada` — BooleanField(default=False): approved for ranking pipeline
- `durada_ms` — IntegerField(null)
- `data_llancament` — DateField(null): tracks older than 12 months excluded
- `preview_url` — URLField(null): Deezer preview
- `activa` — BooleanField(default=True)
- `ml_classe` — CharField(null): A/B/C classification
- `ml_confianca` — FloatField(null): ML confidence score
- `created_at` — DateTimeField(auto_now_add)

Methods:
- `lastfm_lookup_nom` (property) → best name for Last.fm API
- `get_territoris()` → set of territory codes (union of main + collaborators)

### HistorialRevisio
Audit trail of every approve/reject decision. Read-only, immutable.

- **Identifiers:** `canco_deezer_id`, `canco_spotify_id`, `canco_isrc`
- **Snapshot:** `canco_nom`, `artista_nom`, `artista_territori`, `album_nom`,
  `data_llancament`, `isrc_prefix`
- **Deezer:** `artista_deezer_id`, `artista_deezer_nb_fan`, `artista_deezer_nb_album`,
  `artista_nom_deezer`, `artista_nom_similitud`
- **ML snapshot:** `ml_classe_decisio`, `ml_confianca_decisio`
- **Decision:** `decisio` (aprovada/rebutjada), `motiu` (ok/no_catala/artista_incorrecte/album_incorrecte/no_musica)
- `created_at` — DateTimeField(auto_now_add)

---

## ranking/models.py

### ConfiguracioGlobal
Ranking algorithm coefficients. Single-row table (PK always 1).

14 coefficients — see CLAUDE_ALGORITHM.md for values.

Methods:
- `save()` — forces pk=1
- `load()` (classmethod) → get_or_create(pk=1)

### SenyalDiari
Daily Last.fm snapshot per track. One row per (canco, data).

- `canco` — FK to Canco
- `data` — DateField
- `lastfm_playcount` — BigIntegerField(null): cumulative total plays
- `lastfm_listeners` — IntegerField(null): unique listeners
- `score_entrada` — FloatField(null): normalized 0-100, computed via percent_rank
- `error` — BooleanField
- `error_msg` — TextField
- `created_at` — DateTimeField(auto_now_add)

Indexes: (canco, data), (data, error). Unique: (canco, data).

### RankingSetmanal
Weekly ranking result. `setmana` = Monday of the ranking week (ISO).

- `canco` — FK to Canco
- `territori` — CharField(max_length=4)
- `setmana` — DateField
- `posicio` — PositiveSmallIntegerField
- `score_setmanal` — FloatField
- `created_at` — DateTimeField(auto_now_add)

Unique: (canco, territori, setmana). Index: (setmana, territori).

### RankingProvisional
Rolling daily ranking. Truncated and rebuilt on each run (daily 07:00).

- `canco` — FK to Canco
- `territori` — CharField(max_length=4)
- `posicio` — PositiveSmallIntegerField
- `score_setmanal` — FloatField
- `lastfm_playcount` — IntegerField(null)
- `dies_en_top` — IntegerField(null)
- `data_calcul` — DateField(auto_now)

Unique: (canco, territori). Index: (territori, posicio).

---

## legacy/models.py (read-only, unmanaged)

### LegacyArtista
Read-only access to legacy `artistes` table. `managed = False`.

### LegacyCanco
Read-only access to legacy `cançons` table. `managed = False`.
Composite PK: `(id_canco, territori)`.
