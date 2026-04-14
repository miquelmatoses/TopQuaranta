"""
One-off exploration script: Last.fm signal distribution analysis.
Read-only — no DB writes. Run with: .venv/bin/python scripts/explorar_senyal.py
"""

import os
import sys
from math import log10

import numpy as np

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "topquaranta.settings.production")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
django.setup()

from django.db.models import Count
from ranking.models import SenyalDiari


def percentile(arr, p):
    """Compute percentile p (0-100) of a numpy array."""
    if len(arr) == 0:
        return 0
    return float(np.percentile(arr, p))


def percent_rank(values):
    """Return percent ranks (0-1) for an array of values. Ties get mean rank."""
    arr = np.array(values, dtype=float)
    n = len(arr)
    if n <= 1:
        return np.array([0.5] * n)
    # argsort-based ranking with tie averaging
    order = arr.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(n, dtype=float)
    # Average ranks for ties
    unique_vals = np.unique(arr)
    for v in unique_vals:
        mask = arr == v
        ranks[mask] = ranks[mask].mean()
    # Normalize to 0-1
    return ranks / (n - 1)


def print_header(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_stats(label, arr):
    """Print percentile stats for a numpy array."""
    print(f"\n  {label} (n={len(arr)}):")
    if len(arr) == 0:
        print("    (no data)")
        return
    print(f"    min={arr.min():,.0f}  max={arr.max():,.0f}  "
          f"median={percentile(arr, 50):,.0f}")
    print(f"    p10={percentile(arr, 10):,.0f}  p25={percentile(arr, 25):,.0f}  "
          f"p75={percentile(arr, 75):,.0f}  p90={percentile(arr, 90):,.0f}")
    print(f"    p95={percentile(arr, 95):,.0f}  p99={percentile(arr, 99):,.0f}")


def main():
    # ── 1. Find the latest available date ──
    latest_date = (
        SenyalDiari.objects
        .filter(error=False, lastfm_playcount__isnull=False)
        .order_by("-data")
        .values_list("data", flat=True)
        .first()
    )
    if not latest_date:
        print("No SenyalDiari data found!")
        return

    earliest_date = (
        SenyalDiari.objects
        .filter(error=False, lastfm_playcount__isnull=False)
        .order_by("data")
        .values_list("data", flat=True)
        .first()
    )

    print(f"Data range: {earliest_date} → {latest_date}")
    print(f"Days span: {(latest_date - earliest_date).days}")

    total_rows = SenyalDiari.objects.filter(error=False, lastfm_playcount__isnull=False).count()
    total_errors = SenyalDiari.objects.filter(error=True).count()
    distinct_dates = (
        SenyalDiari.objects
        .filter(error=False, lastfm_playcount__isnull=False)
        .values_list("data", flat=True)
        .distinct()
        .count()
    )
    print(f"Total rows (success): {total_rows:,}")
    print(f"Total errors: {total_errors:,}")
    print(f"Distinct dates: {distinct_dates}")

    # ── 2. Load latest day's data ──
    qs = SenyalDiari.objects.filter(
        data=latest_date, error=False, lastfm_playcount__isnull=False
    ).select_related("canco__artista")

    rows = list(qs.values_list(
        "canco_id", "canco__nom", "canco__artista__nom",
        "lastfm_playcount", "lastfm_listeners",
    ))

    print(f"\nTracks on {latest_date}: {len(rows)}")

    playcounts = np.array([r[3] for r in rows], dtype=np.int64)
    listeners = np.array([r[4] for r in rows], dtype=np.int64)

    # ── 3. Basic statistics ──
    print_header("3. BASIC STATISTICS")
    print_stats("Playcount", playcounts)
    print_stats("Listeners", listeners)

    zero_pc = int((playcounts == 0).sum())
    zero_ls = int((listeners == 0).sum())
    print(f"\n  Playcount = 0: {zero_pc} ({zero_pc/len(rows)*100:.1f}%)")
    print(f"  Listeners = 0: {zero_ls} ({zero_ls/len(rows)*100:.1f}%)")

    # Distribution buckets
    buckets = [
        ("0", playcounts == 0),
        ("1-100", (playcounts >= 1) & (playcounts <= 100)),
        ("101-1,000", (playcounts >= 101) & (playcounts <= 1000)),
        ("1,001-10,000", (playcounts >= 1001) & (playcounts <= 10000)),
        ("10,001-100,000", (playcounts >= 10001) & (playcounts <= 100000)),
        ("100,001-1,000,000", (playcounts >= 100001) & (playcounts <= 1000000)),
        ("1,000,001+", playcounts >= 1000001),
    ]
    print("\n  Playcount distribution:")
    for label, mask in buckets:
        cnt = int(mask.sum())
        print(f"    {label:>20s}: {cnt:5d} ({cnt/len(rows)*100:5.1f}%)")

    # ── 4. Weekly deltas ──
    print_header("4. WEEKLY DELTAS")

    # Get earliest day data for delta calculation
    earliest_qs = SenyalDiari.objects.filter(
        data=earliest_date, error=False, lastfm_playcount__isnull=False
    )
    earliest_map = {
        row["canco_id"]: row["lastfm_playcount"]
        for row in earliest_qs.values("canco_id", "lastfm_playcount")
    }

    deltas = []
    delta_rows = []  # (canco_id, nom, artista, playcount_now, playcount_then, delta)
    for canco_id, nom, artista, pc_now, ls_now in rows:
        pc_then = earliest_map.get(canco_id)
        if pc_then is not None:
            delta = pc_now - pc_then
            deltas.append(delta)
            delta_rows.append((canco_id, nom, artista, pc_now, pc_then, delta, ls_now))

    deltas = np.array(deltas, dtype=np.int64)
    print(f"  Tracks with both endpoints: {len(deltas)}")

    if len(deltas) > 0:
        positive = deltas[deltas > 0]
        print(f"  Delta > 0 (growing): {len(positive)}")
        print(f"  Delta = 0 (flat):    {int((deltas == 0).sum())}")
        print(f"  Delta < 0 (shrink?): {int((deltas < 0).sum())}")
        print_stats("Positive deltas", positive)
        print_stats("All deltas", deltas)

    # ── 5. Simulate three formulas ──
    print_header("5. FORMULA SIMULATIONS")

    # Build lookup for deltas
    delta_map = {r[0]: (r[5], r[6]) for r in delta_rows}  # canco_id -> (delta, listeners)

    max_pc = playcounts.max() if len(playcounts) > 0 else 1

    # --- Formula A: log scale ---
    print("\n  ── Formula A: log10(playcount+1) / log10(max+1) * 100 ──")
    scores_a = []
    for canco_id, nom, artista, pc, ls in rows:
        score = log10(pc + 1) / log10(max_pc + 1) * 100 if max_pc > 0 else 0
        scores_a.append((score, pc, ls, artista, nom))
    scores_a.sort(reverse=True)

    print(f"  {'#':>3s}  {'Score':>7s}  {'Playcount':>12s}  {'Listeners':>10s}  Artist — Track")
    for i, (score, pc, ls, art, nom) in enumerate(scores_a[:20]):
        print(f"  {i+1:3d}  {score:7.2f}  {pc:12,d}  {ls:10,d}  {art} — {nom}")
    print("  ...")
    for i, (score, pc, ls, art, nom) in enumerate(scores_a[-5:]):
        idx = len(scores_a) - 5 + i + 1
        print(f"  {idx:3d}  {score:7.2f}  {pc:12,d}  {ls:10,d}  {art} — {nom}")

    arr_a = np.array([s[0] for s in scores_a])
    print(f"\n  Std dev: {arr_a.std():.2f}")
    print(f"  Mean: {arr_a.mean():.2f}")
    print_stats("Score A distribution", arr_a)

    # --- Formula B: percent rank on playcount ---
    print("\n\n  ── Formula B: percent_rank(playcount) * 100 ──")
    pc_ranks = percent_rank(playcounts) * 100
    scores_b = []
    for i, (canco_id, nom, artista, pc, ls) in enumerate(rows):
        scores_b.append((pc_ranks[i], pc, ls, artista, nom))
    scores_b.sort(reverse=True)

    print(f"  {'#':>3s}  {'Score':>7s}  {'Playcount':>12s}  {'Listeners':>10s}  Artist — Track")
    for i, (score, pc, ls, art, nom) in enumerate(scores_b[:20]):
        print(f"  {i+1:3d}  {score:7.2f}  {pc:12,d}  {ls:10,d}  {art} — {nom}")
    print("  ...")
    for i, (score, pc, ls, art, nom) in enumerate(scores_b[-5:]):
        idx = len(scores_b) - 5 + i + 1
        print(f"  {idx:3d}  {score:7.2f}  {pc:12,d}  {ls:10,d}  {art} — {nom}")

    arr_b = np.array([s[0] for s in scores_b])
    print(f"\n  Std dev: {arr_b.std():.2f}")
    print(f"  Mean: {arr_b.mean():.2f}")
    print_stats("Score B distribution", arr_b)

    # --- Formula C: 0.6 * delta_rank + 0.4 * listener_rank ---
    print("\n\n  ── Formula C: 0.6 * percent_rank(delta_7d) + 0.4 * percent_rank(listeners) ──")

    # Only tracks with delta data
    c_data = []
    for canco_id, nom, artista, pc, ls in rows:
        if canco_id in delta_map:
            delta, _ = delta_map[canco_id]
            c_data.append((canco_id, nom, artista, pc, ls, delta))

    if len(c_data) > 0:
        c_deltas = np.array([r[5] for r in c_data], dtype=np.int64)
        c_listeners = np.array([r[4] for r in c_data], dtype=np.int64)
        delta_ranks = percent_rank(c_deltas) * 100
        listener_ranks = percent_rank(c_listeners) * 100

        scores_c = []
        for i, (cid, nom, artista, pc, ls, delta) in enumerate(c_data):
            score = 0.6 * delta_ranks[i] + 0.4 * listener_ranks[i]
            scores_c.append((score, pc, ls, delta, artista, nom))
        scores_c.sort(reverse=True)

        print(f"  Tracks with delta data: {len(scores_c)}")
        print(f"  {'#':>3s}  {'Score':>7s}  {'Delta7d':>10s}  {'Playcount':>12s}  {'Listeners':>10s}  Artist — Track")
        for i, (score, pc, ls, delta, art, nom) in enumerate(scores_c[:20]):
            print(f"  {i+1:3d}  {score:7.2f}  {delta:10,d}  {pc:12,d}  {ls:10,d}  {art} — {nom}")
        print("  ...")
        for i, (score, pc, ls, delta, art, nom) in enumerate(scores_c[-5:]):
            idx = len(scores_c) - 5 + i + 1
            print(f"  {idx:3d}  {score:7.2f}  {delta:10,d}  {pc:12,d}  {ls:10,d}  {art} — {nom}")

        arr_c = np.array([s[0] for s in scores_c])
        print(f"\n  Std dev: {arr_c.std():.2f}")
        print(f"  Mean: {arr_c.mean():.2f}")
        print_stats("Score C distribution", arr_c)
    else:
        print("  No delta data available (need >= 2 days of data).")

    # ── 6. ISRC duplicate check in SenyalDiari ──
    print_header("7. ISRC DUPLICATE CHECK IN SENYALDIARI")

    # Find cancons sharing the same ISRC that both have SenyalDiari on the same day
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT mc.isrc, sd.data, COUNT(DISTINCT sd.canco_id) as cnt
            FROM ranking_senyaldiari sd
            JOIN music_canco mc ON mc.id = sd.canco_id
            WHERE mc.isrc != '' AND mc.isrc IS NOT NULL
            GROUP BY mc.isrc, sd.data
            HAVING COUNT(DISTINCT sd.canco_id) > 1
            ORDER BY cnt DESC
            LIMIT 20
        """)
        dupes = cursor.fetchall()

    if dupes:
        print(f"  ISRC/date pairs with multiple SenyalDiari entries: {len(dupes)}")
        for isrc, data, cnt in dupes[:10]:
            print(f"    ISRC {isrc} on {data}: {cnt} cançons")
    else:
        print("  No ISRC duplicates in SenyalDiari. Clean!")

    print(f"\n{'='*70}")
    print("  Done.")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
