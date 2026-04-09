import random

FRASES_NOVETAT = [
    "entra fort a la llista! 🆕",
    "fa el seu debut al top! 💥",
    "acaba d’arribar i ja destaca! 🔥",
    "s’incorpora esta setmana 👀",
    "nova al top 40, i amb força! 🚀",
]


def frase_novetat():
    return random.choice(FRASES_NOVETAT)


def format_canço(titol, artistes):
    if len(artistes) == 1:
        return f"{artistes[0]} - {titol}"
    elif len(artistes) == 2:
        return f"{artistes[0]} i {artistes[1]} amb {titol}"
    elif len(artistes) == 3:
        return f"{artistes[0]}, {artistes[1]} i {artistes[2]} amb {titol}"
    else:
        return f"{titol}, de la mà de {artistes[0]}"
