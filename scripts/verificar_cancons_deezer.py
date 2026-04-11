"""
One-off script: mark as verificada=True all Canco records that have a
validated Deezer artist (deezer_id is set, deezer_no_trobat=False)
but are currently unverified.

Usage:
    DJANGO_SETTINGS_MODULE=topquaranta.settings.production \
        .venv/bin/python scripts/verificar_cancons_deezer.py

    # Skip interactive confirmation:
    DJANGO_SETTINGS_MODULE=topquaranta.settings.production \
        .venv/bin/python scripts/verificar_cancons_deezer.py --confirm
"""

import os
import sys

import django

# Bootstrap Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "topquaranta.settings.production")
django.setup()

from django.db import transaction

from music.models import Canco

FILTRE = dict(
    verificada=False,
    artista__deezer_no_trobat=False,
    artista__deezer_id__isnull=False,
)


def main():
    qs = Canco.objects.filter(**FILTRE)
    count = qs.count()

    print(f"Cançons que compleixen els criteris: {count}")
    print(f"  - verificada=False")
    print(f"  - artista.deezer_no_trobat=False")
    print(f"  - artista.deezer_id IS NOT NULL")

    if count == 0:
        print("Cap cançó per actualitzar. Sortint.")
        return

    if "--confirm" in sys.argv:
        print(f"\n--confirm flag present. Procedint amb l'actualització.")
    else:
        resposta = input(f"\nVols marcar {count} cançons com a verificada=True? (sí/no): ")
        if resposta.strip().lower() not in ("sí", "si", "s", "yes", "y"):
            print("Cancel·lat.")
            return

    with transaction.atomic():
        updated = qs.update(verificada=True)

    print(f"\nFet! {updated} cançons actualitzades a verificada=True.")


if __name__ == "__main__":
    main()
