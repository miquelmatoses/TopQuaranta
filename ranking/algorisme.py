# Ranking algorithm — to be extracted from legacy PostgreSQL views in Phase 4.
#
# The algorithm is a 14-CTE SQL query currently living as PostgreSQL views
# (vw_top40_weekly_cat, etc.). It will be ported here as a parameterized
# Python function that executes the SQL via Django's connection.cursor().
#
# See CLAUDE.md section 6 for the full CTE chain and adaptation checklist.

from datetime import date, timedelta

from django.db.models import Count

from music.models import Canco, Territori
from ranking.models import ConfiguracioGlobal

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
    cutoff = date.today() - timedelta(days=365)

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
