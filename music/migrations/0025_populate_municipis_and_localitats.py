"""Populate Municipi from legacy municipis table, then create ArtistaLocalitat
entries from existing Artista.localitat/comarca fields."""

from django.db import connection, migrations

# Same mapping used in pendents.py and artistes.py
TERRITORI_NOM_TO_CODI = {
    "Catalunya": "CAT",
    "País Valencià": "VAL",
    "Illes": "BAL",
    "Catalunya del Nord": "CNO",
    "Andorra": "AND",
    "Franja de Ponent": "FRA",
    "L'Alguer": "ALG",
    "El Carxe": "CAR",
}


def populate_municipis(apps, schema_editor):
    """Read legacy municipis table and create Municipi model entries.

    The legacy `municipis` table was dropped in Phase 8 cleanup. This data
    migration is now a no-op on fresh installs (test DBs, new deployments);
    the actual data was already moved on the original production run.
    """
    Municipi = apps.get_model("music", "Municipi")
    Territori = apps.get_model("music", "Territori")

    # Build codi lookup
    territori_objs = {t.codi: t for t in Territori.objects.all()}

    with connection.cursor() as cursor:
        try:
            cursor.execute('SELECT "Municipi", "Comarca", "Territori" FROM municipis')
            rows = cursor.fetchall()
        except Exception:
            # Legacy table no longer exists (Phase 8). Skip — data already
            # populated on the original migration run.
            print("  Municipi: legacy 'municipis' table absent, skipping")
            return

    created = 0
    skipped = 0
    for nom, comarca, territori_nom in rows:
        codi = TERRITORI_NOM_TO_CODI.get(territori_nom)
        if not codi or codi not in territori_objs:
            skipped += 1
            continue
        if not nom or not comarca:
            skipped += 1
            continue
        # Avoid duplicates
        if Municipi.objects.filter(nom=nom.strip(), comarca=comarca.strip()).exists():
            continue
        Municipi.objects.create(
            nom=nom.strip(),
            comarca=comarca.strip(),
            territori=territori_objs[codi],
        )
        created += 1

    print(f"  Municipi: {created} created, {skipped} skipped")


def create_artista_localitats(apps, schema_editor):
    """Create ArtistaLocalitat entries from existing Artista.localitat/comarca."""
    Artista = apps.get_model("music", "Artista")
    Municipi = apps.get_model("music", "Municipi")
    ArtistaLocalitat = apps.get_model("music", "ArtistaLocalitat")

    # Build lookup: (nom_lower, comarca_lower) → Municipi
    municipi_lookup = {}
    for m in Municipi.objects.all():
        key = (m.nom.lower().strip(), m.comarca.lower().strip())
        municipi_lookup[key] = m

    matched = 0
    manual = 0
    no_loc = 0

    for artista in Artista.objects.exclude(localitat="").exclude(comarca="").iterator(chunk_size=500):
        loc = artista.localitat.strip()
        com = artista.comarca.strip()

        if not loc or not com:
            no_loc += 1
            continue

        key = (loc.lower(), com.lower())
        municipi = municipi_lookup.get(key)

        if municipi:
            ArtistaLocalitat.objects.create(
                artista=artista,
                municipi=municipi,
            )
            matched += 1
        else:
            # No match in municipis table — store as manual entry
            ArtistaLocalitat.objects.create(
                artista=artista,
                municipi=None,
                localitat_manual=f"{loc}, {com}",
            )
            manual += 1

    print(f"  ArtistaLocalitat: {matched} matched to Municipi, {manual} manual entries, {no_loc} artists without location")


def verify_territory_sync(apps, schema_editor):
    """Verify that derived territories match existing M2M for all artists with localitats."""
    Artista = apps.get_model("music", "Artista")
    ArtistaLocalitat = apps.get_model("music", "ArtistaLocalitat")

    mismatches = 0
    total = 0

    for artista in Artista.objects.prefetch_related("territoris", "localitats", "localitats__municipi").iterator(chunk_size=500):
        localitats = list(artista.localitats.all())
        if not localitats:
            continue
        total += 1

        # Derive territories from localitats
        derived = set()
        has_municipi = False
        for al in localitats:
            if al.municipi_id:
                derived.add(al.municipi.territori_id)
                has_municipi = True
        if not has_municipi:
            derived.add("ALT")

        existing = set(artista.territoris.values_list("codi", flat=True))

        if derived != existing:
            mismatches += 1
            # Auto-fix: sync territories
            artista.territoris.set(list(derived))

    print(f"  Territory verification: {total} artists checked, {mismatches} corrected")


class Migration(migrations.Migration):
    dependencies = [
        ("music", "0024_alter_artista_territoris_municipi_artistalocalitat"),
    ]

    operations = [
        migrations.RunPython(populate_municipis, migrations.RunPython.noop),
        migrations.RunPython(create_artista_localitats, migrations.RunPython.noop),
        migrations.RunPython(verify_territory_sync, migrations.RunPython.noop),
    ]
