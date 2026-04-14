import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from music.models import Canco
from ranking.algorisme import TERRITORIS_FIXOS, calcular_ranking_territori
from ranking.models import RankingSetmanal, SenyalDiari

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Calculate weekly ranking for one or all territories."

    def add_arguments(self, parser):
        parser.add_argument(
            "--setmana",
            type=str,
            default=None,
            help="Ranking week date (YYYY-MM-DD, must be Monday). Default: current week's Monday.",
        )
        parser.add_argument(
            "--territori",
            type=str,
            default=None,
            help="Single territory code (e.g. CAT). Default: CAT, VAL, BAL.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print results without writing to DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Parse setmana (must be Monday)
        if options["setmana"]:
            try:
                setmana = date.fromisoformat(options["setmana"])
            except ValueError:
                raise CommandError(f"Invalid date: {options['setmana']}. Use YYYY-MM-DD.")
            if setmana.weekday() != 0:
                raise CommandError(f"{setmana} is not a Monday (weekday={setmana.weekday()}).")
        else:
            today = date.today()
            setmana = today - timedelta(days=today.weekday())

        # Territories to process
        if options["territori"]:
            territoris = [options["territori"].upper()]
        else:
            territoris = sorted(TERRITORIS_FIXOS)

        self.stdout.write(f"Ranking week: {setmana}")
        self.stdout.write(f"Territories: {', '.join(territoris)}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no DB writes.\n"))

        # Pre-flight: check data availability
        total_verified = Canco.objects.filter(
            verificada=True, activa=True,
            data_llancament__gte=date.today() - timedelta(days=365),
        ).count()
        with_score = SenyalDiari.objects.filter(
            data__gte=date.today() - timedelta(days=7),
            error=False,
            score_entrada__isnull=False,
        ).values("canco_id").distinct().count()

        coverage = (with_score / total_verified * 100) if total_verified > 0 else 0
        self.stdout.write(
            f"Pre-flight: {with_score}/{total_verified} verified tracks "
            f"have score_entrada in last 7 days ({coverage:.0f}%)"
        )
        if coverage < 50:
            self.stdout.write(self.style.WARNING(
                "  WARNING: coverage below 50%. Results may be incomplete."
            ))

        # Distinct dates with data
        distinct_dates = (
            SenyalDiari.objects.filter(
                data__gte=date.today() - timedelta(days=7),
                error=False,
                score_entrada__isnull=False,
            ).values_list("data", flat=True).distinct().count()
        )
        self.stdout.write(f"  Days with data in window: {distinct_dates}")

        # Run ranking per territory
        summary = []
        for territori in territoris:
            self.stdout.write(f"\nCalculating {territori}...")
            results = calcular_ranking_territori(territori)

            top40 = [r for r in results if r["posicio"] <= 40]
            summary.append((territori, len(top40)))

            if not results:
                self.stdout.write(self.style.WARNING(f"  No results for {territori}"))
                continue

            if dry_run:
                self._print_top(territori, top40[:20])
            else:
                self._save_ranking(territori, setmana, top40)
                self.stdout.write(f"  Saved {len(top40)} positions for {territori}")

        # Summary
        self.stdout.write(self.style.SUCCESS(
            "\n" + " | ".join(f"{t}: {n} posicions" for t, n in summary)
        ))

    def _print_top(self, territori: str, rows: list[dict]) -> None:
        """Print ranking table for dry-run."""
        # Load canco names for display
        canco_ids = [r["canco_id"] for r in rows]
        cancons = {
            c.id: c for c in
            Canco.objects.filter(id__in=canco_ids).select_related("artista")
        }

        self.stdout.write(f"\n  TOP {len(rows)} {territori}:")
        self.stdout.write(f"  {'#':>3s}  {'Score':>7s}  {'Canvi':>5s}  Artista — Cançó")
        self.stdout.write(f"  {'---':>3s}  {'------':>7s}  {'-----':>5s}  {'─'*50}")

        for r in rows:
            c = cancons.get(r["canco_id"])
            nom = f"{c.artista.nom} — {c.nom}" if c else f"(id={r['canco_id']})"
            canvi = r["canvi_posicio"]
            canvi_str = f"{canvi:+d}" if canvi is not None else "NEW"
            score = r["score_setmanal"] if r["score_setmanal"] is not None else 0.0
            self.stdout.write(
                f"  {r['posicio']:3d}  {score:7.2f}  {canvi_str:>5s}  {nom}"
            )

    def _save_ranking(self, territori: str, setmana: date, rows: list[dict]) -> None:
        """Upsert ranking results to RankingSetmanal."""
        with transaction.atomic():
            for r in rows:
                RankingSetmanal.objects.update_or_create(
                    canco_id=r["canco_id"],
                    territori=territori,
                    setmana=setmana,
                    defaults={
                        "posicio": r["posicio"],
                        "score_setmanal": r["score_setmanal"] or 0.0,
                    },
                )
