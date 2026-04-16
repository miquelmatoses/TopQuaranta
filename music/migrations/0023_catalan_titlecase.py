"""Apply Catalan-aware TitleCase to all song titles, replacing the naive .title()."""

from django.db import migrations

PARTICLES = frozenset(
    {
        "de",
        "la",
        "el",
        "els",
        "i",
        "o",
        "un",
        "una",
        "per",
        "a",
        "amb",
        "en",
        "del",
        "al",
        "als",
        "les",
        "dels",
        "pels",
    }
)
APOSTROPHE_PARTICLES = frozenset({"l'", "d'"})


def _capitalize_word(word):
    if not word:
        return word
    return word[0].upper() + word[1:]


def _is_acronym(word):
    clean = word.rstrip("'")
    return len(clean) <= 3 and clean.isupper() and clean.isalpha()


def titlecase_catala(text):
    if not text:
        return ""
    words = text.split()
    if not words:
        return ""
    result = []
    for idx, word in enumerate(words):
        is_first = idx == 0
        if _is_acronym(word):
            result.append(word)
            continue
        lower = word.lower()
        apostrophe_match = None
        for ap in APOSTROPHE_PARTICLES:
            if lower.startswith(ap) and len(lower) > len(ap):
                apostrophe_match = ap
                break
        if apostrophe_match is not None:
            prefix = apostrophe_match
            rest = word[len(prefix) :]
            if is_first:
                result.append(_capitalize_word(prefix) + _capitalize_word(rest))
            else:
                result.append(prefix + _capitalize_word(rest))
            continue
        if lower in PARTICLES:
            if is_first:
                result.append(_capitalize_word(lower))
            else:
                result.append(lower)
            continue
        result.append(
            _capitalize_word(lower) if lower == word.lower() else _capitalize_word(word)
        )
    return " ".join(result)


def apply_catalan_titlecase(apps, schema_editor):
    Canco = apps.get_model("music", "Canco")
    total = 0
    batch = []
    for canco in Canco.objects.all().iterator(chunk_size=500):
        new_nom = titlecase_catala(canco.nom)
        if new_nom != canco.nom:
            canco.nom = new_nom
            batch.append(canco)
            total += 1
        if len(batch) >= 500:
            Canco.objects.bulk_update(batch, ["nom"])
            batch = []
    if batch:
        Canco.objects.bulk_update(batch, ["nom"])
    print(f"  Catalan TitleCase applied to {total} songs")


class Migration(migrations.Migration):
    dependencies = [
        ("music", "0022_unapprove_without_location_titlecase"),
    ]

    operations = [
        migrations.RunPython(apply_catalan_titlecase, migrations.RunPython.noop),
    ]
