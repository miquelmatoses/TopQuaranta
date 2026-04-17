"""Smart Catalan TitleCase.

Capitalises words in track titles while respecting Catalan conventions:

- Particles (de, la, el, i, …) stay lowercase mid-sentence.
- Apostrophe-prefixed articles (l', d', n', m', t', s') keep the
  apostrophe lowercase and capitalise the word after.
- Acronyms of 2+ uppercase letters (DJ, EP, ADN) are preserved as-is.
- Single uppercase letters (I, A, O) are NEVER acronyms — in Catalan
  they are always either particles (lowercase) or the first word
  (capital). English titles with pronoun "I" mid-sentence lose to
  this rule; that's the correct trade-off for a Catalan music ranking.
- Orphan grave / acute accents and fancy quotation marks standing in
  for apostrophes are normalised to the plain ASCII apostrophe BEFORE
  tokenising, so "L´home" and "L'home" both land as "L'Home".
"""

from typing import Optional

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

# Catalan articles that glue to the next word via an apostrophe.
# Mid-sentence the apostrophe stays lowercase and the word that
# follows gets capitalised.
#
# Intentionally NOT including the weak-pronoun clitics n', m', t', s'.
# Those attach to a verb, not a noun, and the semantic head is the
# verb — writing "M'en Vull Anar" as "m'En Vull Anar" reads wrong.
# We keep the token unsplit and only capitalise the first letter
# (i.e. "M'en Vull Anar" as in the classic carol).
APOSTROPHE_PARTICLES = frozenset({"l'", "d'"})

# Characters sometimes used in place of a proper apostrophe in track
# titles coming from external sources (keyboard mishaps, OCR artefacts,
# "smart" quote substitution). Not to be confused with combining
# diacritics (U+0300–U+036F) which ARE valid — those compose with the
# preceding letter (é, è, ü) and we leave them alone.
_APOSTROPHE_SUBSTITUTES = {
    "\u0060": "'",  # ` GRAVE ACCENT (ASCII backtick)
    "\u00b4": "'",  # ´ ACUTE ACCENT (spacing form)
    "\u2018": "'",  # ' LEFT SINGLE QUOTATION MARK
    "\u2019": "'",  # ' RIGHT SINGLE QUOTATION MARK
    "\u02bc": "'",  # ʼ MODIFIER LETTER APOSTROPHE
}

# Opening punctuation that introduces a new "sentence" inside a title.
# The first alphabetic character AFTER these is capitalised (so
# "(original Mix)" becomes "(Original Mix)"). Digits and apostrophes
# are intentionally NOT here — "3rd" must stay "3rd" and "'s" stays
# "'s".
_OPENING_PUNCT = set("([{«\u201c\u00bf\u00a1")  #  ( [ { «  "  ¿  ¡


def normalize_apostrophes(text: str) -> str:
    """Replace orphan accents and fancy quotation marks with ASCII '."""
    for src, dst in _APOSTROPHE_SUBSTITUTES.items():
        if src in text:
            text = text.replace(src, dst)
    return text


def _capitalize_word(word: str) -> str:
    """Capitalize the first alphabetic character, after any opening punctuation.

    Examples:
        "original"       -> "Original"
        "(original"      -> "(Original"
        "«paraula"       -> "«Paraula"
        "3rd"            -> "3rd"   (digit, not alpha → unchanged)
        "'s"             -> "'s"    (apostrophe is not in _OPENING_PUNCT)
        "L'"             -> "L'"    (first char is already alpha)
    """
    if not word:
        return word
    i = 0
    while i < len(word) and word[i] in _OPENING_PUNCT:
        i += 1
    if i < len(word) and word[i].isalpha():
        return word[:i] + word[i].upper() + word[i + 1 :]
    return word


def _is_acronym(word: str) -> bool:
    """Return True if the word looks like an acronym.

    Must be 2–3 characters, all uppercase, all alphabetic. Single-letter
    uppercase tokens (I, A, O) are never acronyms in Catalan — they are
    particles or first-word capitals.

    Uppercase particles (e.g. "LA", "EL") that happen to be short are
    still treated as particles, not acronyms.
    """
    clean = word.rstrip("'")
    if not (2 <= len(clean) <= 3 and clean.isupper() and clean.isalpha()):
        return False
    return clean.lower() not in PARTICLES


def titlecase_catala(text: Optional[str]) -> str:
    """Apply Catalan-aware title casing to a string.

    Args:
        text: The input string to transform.

    Returns:
        The title-cased string, or empty string if input is None or empty.
    """
    if not text:
        return ""

    text = normalize_apostrophes(text)

    words = text.split()
    if not words:
        return ""

    # If the entire text is uppercase, don't preserve any "acronyms".
    all_upper = text == text.upper()

    result = []
    for idx, word in enumerate(words):
        is_first = idx == 0

        if not all_upper and _is_acronym(word):
            result.append(word)
            continue

        lower = word.lower()

        # Check for apostrophe particles: l', d', n', m', t', s'.
        apostrophe_match = None
        for ap in APOSTROPHE_PARTICLES:
            if lower.startswith(ap) and len(lower) > len(ap):
                apostrophe_match = ap
                break

        if apostrophe_match is not None:
            prefix = apostrophe_match
            # Lowercase `rest` before capitalising so an upstream
            # "L'HOME" ends up "L'Home" (not "L'HOME") — matching the
            # behaviour of the non-apostrophe path below.
            rest = word[len(prefix) :].lower()
            if is_first:
                result.append(_capitalize_word(prefix) + _capitalize_word(rest))
            else:
                result.append(prefix + _capitalize_word(rest))
            continue

        # Regular particles (de, la, i, a, o, …).
        if lower in PARTICLES:
            if is_first:
                result.append(_capitalize_word(lower))
            else:
                result.append(lower)
            continue

        # Normal word: capitalize first letter of the lowercased form.
        result.append(_capitalize_word(lower))

    return " ".join(result)


if __name__ == "__main__":
    cases = [
        # Existing coverage.
        ("l'home de la lluna", "L'Home de la Lluna"),
        ("el noi de la mare", "El Noi de la Mare"),
        ("cançons per a un DJ", "Cançons per a un DJ"),
        ("de la terra al cel", "De la Terra al Cel"),
        ("", ""),
        (None, ""),
        ("d'ací i d'allà", "D'Ací i d'Allà"),
        ("EP de la banda", "EP de la Banda"),
        ("una nit amb els amics", "Una Nit amb els Amics"),
        # Orphan accents → apostrophes.
        ("l´home de la lluna", "L'Home de la Lluna"),
        ("l`home de la lluna", "L'Home de la Lluna"),
        ("d\u2019ací i d\u2019allà", "D'Ací i d'Allà"),
        ("2001´s 99", "2001's 99"),
        # Single-letter tokens that used to be mistaken for acronyms.
        ("abans I ara", "Abans i Ara"),
        ("3 I 3", "3 i 3"),
        ("A Beautiful Beast", "A Beautiful Beast"),  # first word "A" stays capital
        (
            "dir A o B",
            "Dir a o B",
        ),  # "A" and "O" are particles mid-sentence; "B" is acronym
        # Weak-pronoun clitics stay a single token.
        ("n'hi ha prou", "N'hi Ha Prou"),
        ("no s'acaba mai", "No S'acaba Mai"),
        # All-uppercase input.
        ("L'HOME DE LA LLUNA", "L'Home de la Lluna"),
    ]
    for input_text, expected in cases:
        got = titlecase_catala(input_text)
        status = "OK" if got == expected else "FAIL"
        print(f"[{status}] titlecase_catala({input_text!r})")
        if got != expected:
            print(f"  expected: {expected!r}")
            print(f"  got:      {got!r}")
