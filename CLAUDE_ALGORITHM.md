# CLAUDE_ALGORITHM.md — Ranking Algorithm

> Extracted from legacy PostgreSQL views, now in `ranking/algorisme.py`.
> The algorithm logic is identical to legacy — only table/column names changed.

---

## 1. The ranking algorithm — 14-CTE SQL

The algorithm was originally 5 PostgreSQL views (one per territory):
`vw_top40_weekly_cat`, `vw_top40_weekly_pv`, `vw_top40_weekly_ib`,
`vw_top40_weekly_ppcc`, `vw_top40_weekly_altres`.

Now parameterized in `ranking/algorisme.py` as a single SQL with territory as parameter.

### CTE chain

```
cancons_territori → configuracio → base → calculs_a → calcul_factor_a → amb_score_a
→ posicions_a → calculs_b → calcul_factor_b → amb_score_b → posicions_b
→ calculs_c → calcul_factor_final → amb_score_final → posicions_final
```

### How it works

1. **cancons_territori**: bridge CTE — joins `ranking_senyaldiari` to territory via
   `music_artista_territoris` M2M. Includes collaborators via LEFT JOIN `music_canco_artistes_col`.
2. **configuracio**: reads coefficients from `ranking_configuracioglobal` table
3. **base**: aggregates last 7 days of signal per track — computes
   `popularitat_mitjana`, `popularitat_inici` (days -7 to -5), `popularitat_final`
   (days -2 to 0), `dies_en_top`, `setmanes_top`, `antiguitat_dies`
4. **Phase A** (`calculs_a` → `amb_score_a`): individual track penalties
   - Age penalty (antiguitat): exponent 2.5, max 1.0
   - Descent penalty: 0.025 per score_entrada drop
   - Stability weight: dies_en_top / 7 (capped at 1.0)
   - Top-position penalty: sum of 1/2^(posicio-1), capped 10.0
5. **Phase B** (`calculs_b` → `amb_score_b`): monopoly penalties
   - Album monopoly: 0.25 per earlier track from same album
   - Artist monopoly: 0.2 per earlier track from same artist
6. **Phase C** (`calculs_c` → `calcul_factor_final`): new-entry adjustment + smoothing
   - Novelty bonus: -0.1 / -0.05 / 0.0 for weeks 0-2 if pos <= top thresholds
   - Smoothing: factor_suavitat = canvi_posicio / (100 * suavitat)
7. **posicions_final**: ranks by `score_setmanal` DESC, limits to top 100

### Adaptations from legacy

| Legacy | New |
|---|---|
| `ranking_diari.popularitat` | `ranking_senyaldiari.score_entrada` |
| `configuracio_global` | `ranking_configuracioglobal` |
| Territory filter on `cançons.territori` | Territory via `music_artista_territoris` M2M |
| Single artist per track | Main artist + collaborators (LEFT JOIN `music_canco_artistes_col`) |
| Territory codes: `cat`/`pv`/`ib` | `CAT`/`VAL`/`BAL`/`CNO`/`AND`/etc. |

### `configuracio_global` current values

```
dia_setmana_ranking              = 6      (Saturday)
penalitzacio_descens             = 0.025
exponent_penalitzacio_antiguitat = 2.5
max_factor_a                     = 1.0
max_factor_b                     = 1.0
max_factor_c                     = 1.0
max_factor_final                 = 1.5
penalitzacio_album_per_canco     = 0.25
penalitzacio_artista_per_canco   = 0.2
coeficient_penalitzacio_top      = 0.075
penalitzacio_setmana_0           = 0.1
penalitzacio_setmana_1           = 0.05
penalitzacio_setmana_2           = 0.0
suavitat                         = 5
```

---

## 2. Signal formula (Phase 3 — implemented)

**Formula B chosen:** `score_entrada = percentileofscore(day_playcounts, playcount, kind='rank')`

- playcount=0 → score_entrada=0.0
- Computed per-day over all successful tracks
- Average ~50, std ~29, full 0-100 range
- Implemented inline in `obtenir_senyal` (normalization step at end of ingestion)
- Safety net: `actualitzar_score_entrada` at 06:30 as backfill

---

## 3. Territory support

- **Fixed** (always ranked): CAT, VAL, BAL
- **Aggregated** (always computed): ALT, PPCC
- **Optional** (ranked if >= `min_cancons_ranking_propi` verified tracks): CNO, AND, FRA, ALG, CAR
- Threshold configured in `ConfiguracioGlobal.min_cancons_ranking_propi` (default=20)
- `algorisme.py::territoris_amb_ranking_propi()` determines eligible territories
