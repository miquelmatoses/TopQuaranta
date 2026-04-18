"""Run Silero VAD on tracks' Deezer previews.

Processes tracks in this order:
  1. Never processed (silero_processat_at IS NULL), with a preview URL.
  2. Optionally, tracks processed >90 days ago if --refresh.

Updates two fields:
  Canco.silero_veu_probabilitat  — fraction of clip with detected voice
  Canco.silero_processat_at      — timestamp of the analysis

Designed for nightly cron via `tq-run analitzar_silero`. Heavy:
loads torch (~500 MB RAM, one-time) and takes ~0.5 s per track. Don't
invoke from the web process.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ingesta.clients.silero import analyze_preview
from music.models import Canco

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Compute Silero VAD voice probability for tracks with a preview URL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum tracks to process in this run.",
        )
        parser.add_argument(
            "--refresh-older-than",
            type=int,
            default=None,
            help="Also re-process tracks analyzed more than N days ago.",
        )
        parser.add_argument(
            "--canco-id",
            type=int,
            default=None,
            help="Single-track mode (for debugging).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be processed without downloading or writing.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        dry_run: bool = options["dry_run"]
        canco_id = options["canco_id"]
        refresh_days = options["refresh_older_than"]

        if canco_id is not None:
            qs = Canco.objects.filter(pk=canco_id)
        else:
            qs = Canco.objects.filter(
                preview_url__isnull=False,
                silero_processat_at__isnull=True,
            ).exclude(preview_url="")
            if refresh_days is not None:
                cutoff = timezone.now() - timedelta(days=refresh_days)
                refresh_qs = Canco.objects.filter(
                    preview_url__isnull=False,
                    silero_processat_at__lt=cutoff,
                ).exclude(preview_url="")
                qs = qs.union(refresh_qs)
            qs = qs.order_by("-created_at")

        if limit is not None:
            qs = qs[:limit]

        total = qs.count() if hasattr(qs, "count") else len(list(qs))
        self.stdout.write(f"Tracks to process: {total}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no downloads, no writes."))
            for c in list(qs)[:20]:
                self.stdout.write(f"  [{c.pk}] {c.nom!r} preview={c.preview_url[:60]}…")
            return

        ok = 0
        fail = 0
        instrumental = 0  # voice fraction < 0.10
        vocal = 0  # voice fraction ≥ 0.50
        for i, canco in enumerate(qs, 1):
            vf = analyze_preview(canco.preview_url, canco.deezer_id)
            if vf is None:
                fail += 1
                # Leave silero_processat_at NULL → will retry next run.
                continue
            canco.silero_veu_probabilitat = vf
            canco.silero_processat_at = timezone.now()
            canco.save(update_fields=["silero_veu_probabilitat", "silero_processat_at"])
            ok += 1
            if vf < 0.10:
                instrumental += 1
            elif vf >= 0.50:
                vocal += 1
            if i % 50 == 0:
                self.stdout.write(
                    f"  Processed {i}/{total}  ok={ok} fail={fail} "
                    f"instrum={instrumental} vocal={vocal}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n  Done. ok={ok} fail={fail} "
                f"instrumental={instrumental} vocal={vocal} total={total}"
            )
        )
