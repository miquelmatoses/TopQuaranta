import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from music.constants import DIES_CADUCITAT
from music.models import Canco

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete unverified tracks older than 12 months."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        cutoff = date.today() - timedelta(days=DIES_CADUCITAT)

        qs = Canco.objects.filter(verificada=False, data_llancament__lt=cutoff)
        count = qs.count()

        if count == 0:
            self.stdout.write("Cap cançó caducada per esborrar.")
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN — s'esborrarien {count} cançons (data_llancament < {cutoff})"
                )
            )
            return

        with transaction.atomic():
            deleted, _ = qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Esborrades {deleted} cançons caducades (data_llancament < {cutoff})"
            )
        )
