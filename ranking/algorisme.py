"""
Ranking algorithm — 14-CTE SQL extracted from legacy PostgreSQL views.

Ported from vw_top40_weekly_cat (and identical siblings for other territories).
The SQL logic is identical; only table/column references are adapted to the
new Django models. See CLAUDE.md section 6 for the full CTE chain.
"""

import logging
from datetime import date, timedelta

from django.db import connection

from music.constants import DIES_CADUCITAT
from music.models import Canco, Territori
from ranking.models import ConfiguracioGlobal

logger = logging.getLogger(__name__)

# Territories that always get their own ranking regardless of track count
TERRITORIS_FIXOS = {"CAT", "VAL", "BAL"}

# Aggregate territories (always generated)
TERRITORIS_AGREGATS = {"ALT", "PPCC"}

# Territories that need a minimum track count for their own ranking
TERRITORIS_OPCIONALS = {"CNO", "AND", "FRA", "ALG", "CAR"}


def territoris_amb_ranking_propi() -> list[str]:
    """
    Returns territory codes that have enough active verified tracks
    to generate their own Top 40.

    Always includes: CAT, VAL, BAL, ALT, PPCC.
    For CNO, AND, FRA, ALG, CAR: only if they have
    >= min_cancons_ranking_propi active verified tracks.
    """
    config = ConfiguracioGlobal.load()
    threshold = config.min_cancons_ranking_propi
    cutoff = date.today() - timedelta(days=DIES_CADUCITAT)

    result = sorted(TERRITORIS_FIXOS | TERRITORIS_AGREGATS)

    for codi in sorted(TERRITORIS_OPCIONALS):
        count = Canco.objects.filter(
            verificada=True,
            activa=True,
            data_llancament__gte=cutoff,
            artista__territoris__codi=codi,
        ).count()
        if count >= threshold:
            result.append(codi)

    return result


# The full 14-CTE SQL, adapted from vw_top40_weekly_cat.
# Parameters: %(territori)s
#
# CTE chain overview:
#   cancons_territori  — Bridge: join signal to territory via artist M2M + collaborators
#   configuracio       — Read algorithm coefficients from ConfiguracioGlobal
#   base               — Aggregate 7-day window: avg popularity, trend, age, history
#   Phase A (calculs_a → amb_score_a → posicions_a):
#       Individual track penalties: age, descent, stability, top-position accumulation
#   Phase B (calculs_b → amb_score_b → posicions_b):
#       Monopoly penalties: album monopoly (0.25/track), artist monopoly (0.2/track)
#   Phase C (calculs_c → calcul_factor_final → amb_score_final):
#       New-entry adjustment + smoothing factor based on position change
#   posicions_final    — Final ranking ordered by score_setmanal DESC
RANKING_SQL = """
WITH cancons_territori AS (
    -- Bridge CTE: join signal to territory via artist M2M + collaborators (LEFT JOIN).
    -- A track appears in territory T if its main artist OR any collaborator belongs to T.
    SELECT DISTINCT ON (sd.canco_id, sd.data)
        sd.canco_id AS id_canco,
        sd.data,
        sd.score_entrada AS popularitat,
        c.album_id,
        c.artista_id,
        a.data_llancament AS album_data
    FROM ranking_senyaldiari sd
    JOIN music_canco c ON c.id = sd.canco_id
    JOIN music_album a ON a.id = c.album_id
    LEFT JOIN music_canco_artistes_col col ON col.canco_id = c.id
    JOIN music_artista_territoris mt ON (
        mt.artista_id = c.artista_id
        OR mt.artista_id = col.artista_id
    )
    WHERE mt.territori_id = %(territori)s
      AND sd.data >= CURRENT_DATE - INTERVAL '7 days'
      AND sd.error = FALSE
      AND sd.score_entrada IS NOT NULL
      AND c.verificada = TRUE
      AND c.activa = TRUE
),
configuracio AS (
    SELECT
        %(territori)s::text AS territori,
        penalitzacio_descens,
        exponent_penalitzacio_antiguitat,
        max_factor_a,
        max_factor_b,
        max_factor_c,
        max_factor_final,
        penalitzacio_album_per_canco,
        penalitzacio_artista_per_canco,
        coeficient_penalitzacio_top,
        penalitzacio_setmana_0,
        penalitzacio_setmana_1,
        penalitzacio_setmana_2,
        suavitat
    FROM ranking_configuracioglobal
    WHERE id = 1
),
base AS (
    SELECT
        r.id_canco,
        r.album_id,
        r.album_data,
        r.artista_id,
        COUNT(DISTINCT r.data) AS dies_en_top,
        (SELECT COUNT(*)
         FROM ranking_rankingsetmanal rs
         WHERE rs.canco_id = r.id_canco
           AND rs.territori = (SELECT territori FROM configuracio)
           AND rs.posicio <= 40
        ) AS setmanes_top,
        AVG(r.popularitat) AS popularitat_mitjana,
        (SELECT AVG(r1.popularitat)
         FROM cancons_territori r1
         WHERE r1.id_canco = r.id_canco
           AND r1.data >= CURRENT_DATE - INTERVAL '7 days'
           AND r1.data <= CURRENT_DATE - INTERVAL '5 days'
        ) AS popularitat_inici,
        (SELECT AVG(r2.popularitat)
         FROM cancons_territori r2
         WHERE r2.id_canco = r.id_canco
           AND r2.data >= CURRENT_DATE - INTERVAL '2 days'
           AND r2.data <= CURRENT_DATE
        ) AS popularitat_final,
        CURRENT_DATE - r.album_data AS antiguitat_dies,
        ROW_NUMBER() OVER (PARTITION BY r.id_canco ORDER BY AVG(r.popularitat) DESC) AS rn_id,
        (SELECT r_ant.posicio
         FROM ranking_rankingsetmanal r_ant
         WHERE r_ant.canco_id = r.id_canco
           AND r_ant.territori = (SELECT territori FROM configuracio)
           AND r_ant.setmana = (
               SELECT MAX(setmana) FROM ranking_rankingsetmanal
               WHERE territori = (SELECT territori FROM configuracio)
           )
        ) AS posicio_anterior
    FROM cancons_territori r
    GROUP BY r.id_canco, r.album_id, r.album_data, r.artista_id
),
calculs_a AS (
    SELECT
        b.id_canco, b.album_id, b.album_data, b.artista_id,
        b.dies_en_top, b.setmanes_top,
        b.popularitat_mitjana, b.popularitat_inici, b.popularitat_final,
        b.antiguitat_dies,
        COALESCE(b.popularitat_final, 0) - COALESCE(b.popularitat_inici, 0) AS popularitat_delta,
        LEAST(1.0, POWER(b.antiguitat_dies::numeric / 365.0,
            (SELECT exponent_penalitzacio_antiguitat FROM configuracio))
        ) AS penalitzacio_antiguitat,
        CASE
            WHEN COALESCE(b.popularitat_final, 0) < COALESCE(b.popularitat_inici, 0)
            THEN (SELECT penalitzacio_descens FROM configuracio)
            ELSE 0.0
        END AS penalitzacio_descens,
        LEAST(b.dies_en_top::numeric / 7.0, 1.0) AS pes_estabilitat,
        ROUND((
            LEAST(10.0, COALESCE(
                (SELECT SUM(1.0 / POWER(2.0, (rs.posicio - 1)::numeric))
                 FROM ranking_rankingsetmanal rs
                 WHERE rs.canco_id = b.id_canco
                   AND rs.territori = (SELECT territori FROM configuracio)
                   AND rs.posicio <= 40
                ), 0.0)
            ) * (SELECT coeficient_penalitzacio_top FROM configuracio)
        )::numeric, 2) AS penalitzacio_top,
        b.posicio_anterior
    FROM base b
    WHERE b.rn_id = 1
),
calcul_factor_a AS (
    SELECT c.*,
        LEAST(
            GREATEST(1.0 - c.penalitzacio_antiguitat - c.penalitzacio_descens - c.penalitzacio_top, -1.0),
            (SELECT max_factor_a FROM configuracio)
        ) AS factor_score_a
    FROM calculs_a c
),
amb_score_a AS (
    SELECT c.*,
        ROUND((c.popularitat_mitjana * c.pes_estabilitat * c.factor_score_a)::numeric, 2) AS score_a
    FROM calcul_factor_a c
),
posicions_a AS (
    SELECT c.*,
        ROW_NUMBER() OVER (ORDER BY c.score_a DESC) AS posicio_a
    FROM amb_score_a c
),
calculs_b AS (
    SELECT c.*,
        (SELECT COUNT(*)::numeric * (SELECT penalitzacio_album_per_canco FROM configuracio)
         FROM posicions_a x
         WHERE x.album_id = c.album_id AND x.posicio_a < c.posicio_a
        ) AS penalitzacio_album,
        (SELECT COUNT(*)::numeric * (SELECT penalitzacio_artista_per_canco FROM configuracio)
         FROM posicions_a x
         WHERE x.id_canco <> c.id_canco AND x.artista_id = c.artista_id AND x.posicio_a < c.posicio_a
        ) AS penalitzacio_artista
    FROM posicions_a c
),
calcul_factor_b AS (
    SELECT b.*,
        LEAST(
            GREATEST(b.factor_score_a - b.penalitzacio_album - b.penalitzacio_artista, -1.0),
            (SELECT max_factor_b FROM configuracio)
        ) AS factor_score_b
    FROM calculs_b b
),
amb_score_b AS (
    SELECT p.*,
        ROUND((p.popularitat_mitjana * p.pes_estabilitat * p.factor_score_b)::numeric) AS score_b
    FROM calcul_factor_b p
),
posicions_b AS (
    SELECT f.*,
        ROW_NUMBER() OVER (ORDER BY f.score_b DESC) AS posicio_b
    FROM amb_score_b f
),
calculs_c AS (
    SELECT b.*,
        CASE
            WHEN b.setmanes_top = 0 AND b.posicio_b <= 20
                THEN (SELECT penalitzacio_setmana_0 FROM configuracio)
            WHEN b.setmanes_top = 1 AND b.posicio_b <= 10
                THEN (SELECT penalitzacio_setmana_1 FROM configuracio)
            WHEN b.setmanes_top = 2 AND b.posicio_b <= 5
                THEN (SELECT penalitzacio_setmana_2 FROM configuracio)
            ELSE 0.0
        END AS penalitzacio_entrada,
        COALESCE(b.posicio_anterior, 41) - LEAST(b.posicio_b, 41) AS canvi_posicio_b
    FROM posicions_b b
),
calcul_factor_final AS (
    SELECT e.*,
        ROUND(COALESCE(e.canvi_posicio_b::numeric / (100.0 *
            (SELECT suavitat FROM configuracio)), 0.0)::numeric, 2) AS factor_suavitat
    FROM calculs_c e
),
amb_score_final AS (
    SELECT s.*,
        LEAST(
            GREATEST(s.factor_score_b - s.penalitzacio_entrada - s.factor_suavitat, 0.0),
            (SELECT max_factor_final FROM configuracio)
        ) AS factor_score,
        ROUND((
            s.popularitat_mitjana * s.pes_estabilitat *
            LEAST(
                GREATEST(s.factor_score_b - s.penalitzacio_entrada - s.factor_suavitat, 0.0),
                (SELECT max_factor_final FROM configuracio)
            ))::numeric, 2
        ) AS score_setmanal
    FROM calcul_factor_final s
),
posicions_final AS (
    SELECT f.*,
        ROW_NUMBER() OVER (ORDER BY f.score_setmanal DESC) AS posicio
    FROM amb_score_final f
)
SELECT
    o.id_canco AS canco_id,
    o.score_setmanal,
    o.posicio,
    o.posicio_anterior,
    o.posicio_anterior - o.posicio AS canvi_posicio,
    o.dies_en_top
FROM posicions_final o
WHERE o.posicio <= 100
ORDER BY o.score_setmanal DESC
"""


def calcular_ranking_territori(territori: str) -> list[dict]:
    """
    Run the 14-CTE ranking algorithm for a given territory.
    Returns list of dicts with posicio, canco_id, score_setmanal, canvi_posicio.
    """
    with connection.cursor() as cursor:
        cursor.execute(RANKING_SQL, {"territori": territori})
        col_names = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(col_names, row)))
    return results
