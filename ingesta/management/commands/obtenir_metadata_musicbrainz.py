"""Continuously enrich our Artista/Album/Canço rows with MusicBrainz data.

Usage:
    ./manage.py obtenir_metadata_musicbrainz
    ./manage.py obtenir_metadata_musicbrainz --refresh-days 7 --limit 300
    ./manage.py obtenir_metadata_musicbrainz --artista-id 3663

Behaviour:
  * A single-instance lock (fcntl) keeps concurrent crons from stepping
    on each other. If locked, the second invocation exits cleanly.
  * Processes one artist per iteration: lookup MBID by name if missing,
    otherwise pull + reconcile discography.
  * MusicBrainz is rate-limited globally to 1 req/s; expect ~5 reqs
    per artist synced (core + paginated RGs + 1-2 recordings fetches).
  * Stops when no artist needs attention (queue empty: `mb_last_sync`
    is NULL for none, or all sync timestamps are within `--refresh-days`).
"""

from __future__ import annotations

import fcntl
import logging
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from music.mb_sync import resolve_mbid, sync_from_mbid
from music.models import Artista

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Pull MusicBrainz metadata (artist + discography) into our DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh-days",
            type=int,
            default=7,
            help="Skip artists synced more recently than N days ago.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max artists to process this invocation (default: run until "
            "the queue is empty).",
        )
        parser.add_argument(
            "--artista-id",
            type=int,
            default=None,
            help="Process only this Artista pk (ignores --refresh-days).",
        )

    def handle(self, *args, **opts):
        lock_file = "/tmp/mb_sync.lock"
        try:
            lock = open(lock_file, "w")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            self.stdout.write("Ja hi ha una instància corrent. Sortint.")
            return

        try:
            self._run(**opts)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()

    def _run(self, **opts):
        refresh_days = opts["refresh_days"]
        limit = opts["limit"]
        artista_id = opts["artista_id"]

        if artista_id:
            try:
                a = Artista.objects.get(pk=artista_id)
            except Artista.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"No Artista pk={artista_id}"))
                return
            self._process(a)
            return

        processed = 0
        cutoff = timezone.now() - timedelta(days=refresh_days)

        while True:
            qs = (
                Artista.objects
                # Approved artists get first dibs, then pendents, then descartats.
                .annotate(
                    prio=Case(
                        When(aprovat=True, then=Value(0)),
                        When(pendent_review=True, then=Value(1)),
                        default=Value(2),
                        output_field=IntegerField(),
                    )
                )
                .filter(Q(mb_last_sync__isnull=True) | Q(mb_last_sync__lt=cutoff))
                .order_by("prio", "mb_last_sync", "pk")
            )
            a = qs.first()
            if not a:
                self.stdout.write(self.style.SUCCESS("Cua buida — tot fresc. Sortint."))
                break
            self._process(a)
            processed += 1
            if limit and processed >= limit:
                self.stdout.write(f"Límit de {limit} artistes aconseguit. Sortint.")
                break

    def _process(self, artista: Artista) -> None:
        try:
            if not artista.musicbrainz_id:
                mbid = resolve_mbid(artista)
                if mbid:
                    artista.musicbrainz_id = mbid
                    artista.save(update_fields=["musicbrainz_id"])
                    self.stdout.write(f"  [name] {artista.nom} → MBID {mbid}")
                else:
                    # No MBID found: still mark as synced so we don't thrash.
                    artista.mb_last_sync = timezone.now()
                    artista.save(update_fields=["mb_last_sync"])
                    self.stdout.write(f"  [no-match] {artista.nom} (pk={artista.pk})")
                    return
            counters = sync_from_mbid(artista)
            self.stdout.write(
                "  [sync] {nom} → urls={u} albums={am}/{rgs} "
                "cançons={cm}/{rec} isrcs={i} cat_work={cat}".format(
                    nom=artista.nom,
                    u=counters["urls_filled"],
                    am=counters["albums_matched"],
                    rgs=counters["rgs"],
                    cm=counters["cancons_matched"],
                    rec=counters["recordings"],
                    i=counters["isrcs"],
                    cat=counters["cat_work"],
                )
            )
        except Exception:
            logger.exception("MB sync failed for %s (pk=%s)", artista.nom, artista.pk)
            artista.mb_last_sync = timezone.now()
            artista.save(update_fields=["mb_last_sync"])
        # Small extra pause between artistes to stay polite.
        time.sleep(0.2)
