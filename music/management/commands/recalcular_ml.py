from django.core.management.base import BaseCommand

from music.ml import recalcular_ml


class Command(BaseCommand):
    help = "Recalculate ml_classe and ml_confianca for all unverified cancons."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        limit = options["limit"]
        updated = recalcular_ml(limit=limit)
        self.stdout.write(self.style.SUCCESS(f"ML recalculated for {updated} cancons."))
