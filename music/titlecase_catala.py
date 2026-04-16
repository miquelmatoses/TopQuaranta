"""Smart Catalan TitleCase: capitalizes words while respecting Catalan particles."""

from typing import Optional

PARTICLES = frozenset({
    "de", "la", "el", "els", "i", "o", "un", "una", "per", "a", "amb",
    "en", "del", "al", "als", "les", "dels", "pels",
})

APOSTROPHE_PARTICLES = frozenset({"l'", "d'"})


def _capitalize_word(word: str) -> str:
    """Capitalize the first letter of a word, leaving the rest unchanged."""
    if not word:
        return word
    return word[0].upper() + word[1:]


def _is_acronym(word: str) -> bool:
    """Return True if the word looks like an acronym (<=3 chars, all uppercase).

    Excludes known Catalan particles that happen to be short uppercase words.
    """
    clean = word.rstrip("'")
    if not (len(clean) <= 3 and clean.isupper() and clean.isalpha()):
        return False
    # Don't treat uppercase particles as acronyms
    return clean.lower() not in PARTICLES


def titlecase_catala(text: Optional[str]) -> str:
    """Apply Catalan-aware title casing to a string.

    Capitalizes all words except Catalan particles (de, la, el, l', d', i, etc.)
    which are lowercased unless they appear as the first word. Preserves short
    all-uppercase words as acronyms (e.g. DJ, EP).

    Args:
        text: The input string to transform.

    Returns:
        The title-cased string, or empty string if input is None or empty.
    """
    if not text:
        return ""

    words = text.split()
    if not words:
        return ""

    # If the entire text is uppercase, don't preserve any "acronyms"
    all_upper = text == text.upper()

    result = []
    for idx, word in enumerate(words):
        is_first = idx == 0

        # Preserve acronyms (<=3 chars, all uppercase) — but not if entire text is uppercase
        if not all_upper and _is_acronym(word):
            result.append(word)
            continue

        lower = word.lower()

        # Check for apostrophe particles: l' and d' prefixed words
        apostrophe_match = None
        for ap in APOSTROPHE_PARTICLES:
            if lower.startswith(ap) and len(lower) > len(ap):
                apostrophe_match = ap
                break

        if apostrophe_match is not None:
            prefix = apostrophe_match
            rest = word[len(prefix):]
            if is_first:
                # Capitalize the prefix and the rest
                result.append(_capitalize_word(prefix) + _capitalize_word(rest))
            else:
                # Lowercase prefix, capitalize the rest
                result.append(prefix + _capitalize_word(rest))
            continue

        # Regular particles
        if lower in PARTICLES:
            if is_first:
                result.append(_capitalize_word(lower))
            else:
                result.append(lower)
            continue

        # Normal word: capitalize first letter of the lowercased form
        result.append(_capitalize_word(lower))

    return " ".join(result)


if __name__ == "__main__":
    cases = [
        ("l'home de la lluna", "L'Home de la Lluna"),
        ("el noi de la mare", "El Noi de la Mare"),
        ("cançons per a un DJ", "Cançons per a un DJ"),
        ("de la terra al cel", "De la Terra al Cel"),
        ("", ""),
        (None, ""),
        ("d'ací i d'allà", "D'Ací i d'Allà"),
        ("EP de la banda", "EP de la Banda"),
        ("una nit amb els amics", "Una Nit amb els Amics"),
    ]
    for input_text, expected in cases:
        got = titlecase_catala(input_text)
        status = "OK" if got == expected else "FAIL"
        print(f"[{status}] titlecase_catala({input_text!r})")
        if got != expected:
            print(f"  expected: {expected!r}")
            print(f"  got:      {got!r}")
