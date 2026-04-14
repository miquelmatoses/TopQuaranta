"""
Score normalization for the ranking algorithm.

Formula B (Phase 3): score_entrada = percentileofscore(day_playcounts, playcount, kind='rank')
- playcount=0 → score_entrada=0.0
- Computed per-day over all successful tracks
"""

import logging
from datetime import date

from django.db import transaction
from scipy.stats import percentileofscore

from music.constants import SCORE_BATCH_SIZE
from ranking.models import SenyalDiari

logger = logging.getLogger(__name__)


def normalize_score_entrada(target_date: date) -> int:
    """
    Compute percent_rank(playcount) for all SenyalDiari of a given day.
    playcount=0 or NULL → score_entrada=0.0.
    Returns number of rows updated.
    """
    rows = list(
        SenyalDiari.objects.filter(
            data=target_date,
            error=False,
            lastfm_playcount__isnull=False,
        ).values_list("pk", "lastfm_playcount")
    )
    if not rows:
        return 0

    sorted_plays = sorted(pc for _, pc in rows if pc > 0)

    updates = []
    for pk, playcount in rows:
        if playcount > 0 and sorted_plays:
            score = percentileofscore(sorted_plays, playcount, kind="rank")
        else:
            score = 0.0
        updates.append((pk, score))

    updated = 0
    for i in range(0, len(updates), SCORE_BATCH_SIZE):
        batch = updates[i : i + SCORE_BATCH_SIZE]
        with transaction.atomic():
            for pk, score in batch:
                SenyalDiari.objects.filter(pk=pk).update(score_entrada=score)
                updated += 1

    return updated
