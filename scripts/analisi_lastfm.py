"""
One-off analysis of Last.fm ingestion data from SenyalDiari.

Usage:
    DJANGO_SETTINGS_MODULE=topquaranta.settings.production \
        .venv/bin/python scripts/analisi_lastfm.py
"""

import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "topquaranta.settings.production")
django.setup()

from django.db.models import Avg, Count, Min, Max, Q
from django.db.models.functions import Coalesce

from ranking.models import SenyalDiari


def percentile(values, p):
    """Return the p-th percentile of a sorted list."""
    if not values:
        return None
    k = (len(values) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(values):
        return values[f]
    return values[f] + (k - f) * (values[c] - values[f])


def main():
    # --- 1. Rows per date ---
    print("=" * 70)
    print("1. FILES PER DATA")
    print("=" * 70)
    dates = (
        SenyalDiari.objects.values("data")
        .annotate(
            total=Count("id"),
            ok=Count("id", filter=Q(error=False)),
            errors=Count("id", filter=Q(error=True)),
        )
        .order_by("data")
    )
    if not dates:
        print("  Cap dada a SenyalDiari!")
        return

    for d in dates:
        print(f"  {d['data']}:  total={d['total']}  ok={d['ok']}  errors={d['errors']}")

    all_dates = [d["data"] for d in dates]
    latest = all_dates[-1]

    # --- 2. Stats for latest date ---
    print(f"\n{'=' * 70}")
    print(f"2. ESTADÍSTIQUES PER A {latest}")
    print("=" * 70)

    qs_day = SenyalDiari.objects.filter(data=latest, error=False)
    with_play = qs_day.filter(lastfm_playcount__gt=0).count()
    zero_play = qs_day.filter(lastfm_playcount=0).count()
    null_play = qs_day.filter(lastfm_playcount__isnull=True).count()
    err_count = SenyalDiari.objects.filter(data=latest, error=True).count()

    print(f"  playcount > 0:   {with_play}")
    print(f"  playcount = 0:   {zero_play}")
    print(f"  playcount NULL:  {null_play}")
    print(f"  error = True:    {err_count}")

    playcounts = sorted(
        qs_day.exclude(lastfm_playcount__isnull=True)
        .values_list("lastfm_playcount", flat=True)
    )
    listeners = sorted(
        qs_day.exclude(lastfm_listeners__isnull=True)
        .values_list("lastfm_listeners", flat=True)
    )

    if playcounts:
        print(f"\n  Playcount (n={len(playcounts)}):")
        print(f"    min={playcounts[0]:,}  max={playcounts[-1]:,}  "
              f"mitjana={sum(playcounts)/len(playcounts):,.0f}")
        print(f"    p10={percentile(playcounts, 10):,.0f}  "
              f"p50={percentile(playcounts, 50):,.0f}  "
              f"p90={percentile(playcounts, 90):,.0f}")

    if listeners:
        print(f"\n  Listeners (n={len(listeners)}):")
        print(f"    min={listeners[0]:,}  max={listeners[-1]:,}  "
              f"mitjana={sum(listeners)/len(listeners):,.0f}")
        print(f"    p10={percentile(listeners, 10):,.0f}  "
              f"p50={percentile(listeners, 50):,.0f}  "
              f"p90={percentile(listeners, 90):,.0f}")

    # --- 3. Examples ---
    print(f"\n{'=' * 70}")
    print("3. EXEMPLES CONCRETS")
    print("=" * 70)

    print("\n  Top 5 playcount:")
    top = (
        qs_day.filter(lastfm_playcount__gt=0)
        .select_related("canco", "canco__artista")
        .order_by("-lastfm_playcount")[:5]
    )
    for r in top:
        print(f"    {r.lastfm_playcount:>12,} plays | {r.lastfm_listeners:>8,} listeners | "
              f"{r.canco.artista.nom} — {r.canco.nom}")

    print("\n  Bottom 5 playcount (> 0):")
    bottom = (
        qs_day.filter(lastfm_playcount__gt=0)
        .select_related("canco", "canco__artista")
        .order_by("lastfm_playcount")[:5]
    )
    for r in bottom:
        print(f"    {r.lastfm_playcount:>12,} plays | {r.lastfm_listeners:>8,} listeners | "
              f"{r.canco.artista.nom} — {r.canco.nom}")

    print("\n  5 amb error:")
    errs = (
        SenyalDiari.objects.filter(data=latest, error=True)
        .select_related("canco", "canco__artista")[:5]
    )
    for r in errs:
        msg = r.error_msg[:80] if r.error_msg else "(sense missatge)"
        print(f"    {r.canco.artista.nom} — {r.canco.nom}")
        print(f"      Error: {msg}")

    # --- 4. Delta between days ---
    if len(all_dates) >= 2:
        print(f"\n{'=' * 70}")
        print(f"4. COMPARACIÓ ENTRE DIES ({all_dates[0]} → {all_dates[-1]})")
        print("=" * 70)

        day1 = all_dates[0]
        day2 = all_dates[-1]

        # Get tracks present in both days without error
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    i1.lastfm_playcount AS pc1,
                    i2.lastfm_playcount AS pc2,
                    i2.lastfm_playcount - i1.lastfm_playcount AS delta,
                    c.nom AS canco_nom,
                    a.nom AS artista_nom
                FROM ranking_ingestadiari i1
                JOIN ranking_ingestadiari i2
                    ON i1.canco_id = i2.canco_id
                JOIN music_canco c ON c.id = i1.canco_id
                JOIN music_artista a ON a.id = c.artista_id
                WHERE i1.data = %s AND i2.data = %s
                    AND i1.error = FALSE AND i2.error = FALSE
                    AND i1.lastfm_playcount IS NOT NULL
                    AND i2.lastfm_playcount IS NOT NULL
                ORDER BY delta DESC
            """, [day1, day2])
            rows = cursor.fetchall()

        if not rows:
            print("  Cap cançó comuna entre els dos dies.")
        else:
            deltas = [r[2] for r in rows]
            pos_deltas = [d for d in deltas if d > 0]
            zero_deltas = [d for d in deltas if d == 0]
            neg_deltas = [d for d in deltas if d < 0]

            print(f"  Cançons comparades: {len(rows)}")
            print(f"  Delta > 0 (creixement):  {len(pos_deltas)}")
            print(f"  Delta = 0 (sense canvi): {len(zero_deltas)}")
            print(f"  Delta < 0 (descens):     {len(neg_deltas)}")

            if deltas:
                deltas_sorted = sorted(deltas)
                print(f"\n  Delta playcount:")
                print(f"    min={deltas_sorted[0]:,}  max={deltas_sorted[-1]:,}  "
                      f"mitjana={sum(deltas)/len(deltas):,.0f}")
                print(f"    p10={percentile(deltas_sorted, 10):,.0f}  "
                      f"p50={percentile(deltas_sorted, 50):,.0f}  "
                      f"p90={percentile(deltas_sorted, 90):,.0f}")

            print(f"\n  Top 5 creixement:")
            for r in rows[:5]:
                print(f"    +{r[2]:>8,} plays ({r[0]:,} → {r[1]:,}) | "
                      f"{r[4]} — {r[3]}")

            print(f"\n  Top 5 descens:")
            for r in rows[-5:]:
                sign = "+" if r[2] >= 0 else ""
                print(f"    {sign}{r[2]:>8,} plays ({r[0]:,} → {r[1]:,}) | "
                      f"{r[4]} — {r[3]}")
    else:
        print(f"\n{'=' * 70}")
        print("4. COMPARACIÓ ENTRE DIES")
        print("=" * 70)
        print("  Només 1 dia disponible — no es pot comparar.")


if __name__ == "__main__":
    main()
