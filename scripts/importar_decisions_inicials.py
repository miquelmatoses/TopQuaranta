#!/usr/bin/env python
"""
Import initial HistorialRevisio records from hardcoded data.
Run: python manage.py shell < scripts/importar_decisions_inicials.py
"""
import django
django.setup()

from music.models import HistorialRevisio

DECISIONS = [
    ("Voltaryn Pulseforge", "Scorpio", "Drip Driftcore", "US39N2682283", "CAT", "rebutjada", "artista_incorrecte"),
    ("Quantar Driftforge", "Scorpio", "Drip Driftcore", "US39N2682282", "CAT", "rebutjada", "artista_incorrecte"),
    ("Oblivyx Harmatrix", "Scorpio", "Drip Driftcore", "US39N2682281", "CAT", "rebutjada", "artista_incorrecte"),
    ("Nyxalon Bassrift", "Scorpio", "Drip Driftcore", "US39N2682280", "CAT", "rebutjada", "artista_incorrecte"),
    ("Nytherion Bassshift", "Scorpio", "Drip Driftcore", "US39N2682279", "CAT", "rebutjada", "artista_incorrecte"),
    ("Nexaris Fluxengine", "Scorpio", "Drip Driftcore", "US39N2682278", "CAT", "rebutjada", "artista_incorrecte"),
    ("Menina Morcego", "Roser", "Menina Morcego", "QT82U2647837", "CAT", "rebutjada", "album_incorrecte"),
    ("Love and Predestination", "Oscar Peris", "Love and Predestination", "GXJBW2680555", "VAL", "rebutjada", "no_catala"),
    ("arqueologia shoegaze", "Vittara", "VTT ARA", "ES5062603807", "CAT", "aprovada", "ok"),
    ("Tanca el llum i obre la porta", "Vittara", "VTT ARA", "ES5062602601", "CAT", "aprovada", "ok"),
    ("Mapa", "Vittara", "VTT ARA", "ES5062603804", "CAT", "aprovada", "ok"),
    ("Tutto Passa", "Teks Meks", "Tutto Passa", "QZTB42624954", "CAT", "aprovada", "ok"),
    ("Color Lambrusco", "Teks Meks", "Color Lambrusco", "QZTB42685527", "CAT", "aprovada", "ok"),
    ("Die Magische Tijd", "Roger Martinez", "Die Magische Tijd - Remixed", "US83Z2616029", "CAT", "rebutjada", "album_incorrecte"),
    ("Die Magische Tijd (Ricky Ryan & Futura City Remix)", "Roger Martinez", "Die Magische Tijd - Remixed", "US83Z2616028", "CAT", "rebutjada", "album_incorrecte"),
    ("Die Magische Tijd (Montw Remix)", "Roger Martinez", "Die Magische Tijd - Remixed", "US83Z2616027", "CAT", "rebutjada", "album_incorrecte"),
    ("GENESIS (Sped Up)", "Quiets", "GENESIS", "QT82U2669888", "CAT", "rebutjada", "artista_incorrecte"),
    ("GENESIS (Super Slowed)", "Quiets", "GENESIS", "QT82U2638211", "CAT", "rebutjada", "artista_incorrecte"),
    ("GENESIS (Slowed)", "Quiets", "GENESIS", "QT82U2647746", "CAT", "rebutjada", "artista_incorrecte"),
    ("GENESIS", "Quiets", "GENESIS", "QT82U2621022", "CAT", "rebutjada", "artista_incorrecte"),
    ("Paizei Party", "Patch", "Paizei Party", "QZTB92694390", "CAT", "rebutjada", "album_incorrecte"),
    ("Non c'è pace", "Negre", "Non c'è pace", "QM6MZ2667714", "BAL", "rebutjada", "album_incorrecte"),
    ("Ordinary", "Maio", "Ordinary", "QZTL92622766", "CAT", "rebutjada", "album_incorrecte"),
    ("LONDON EYE", "l'Atelier", "LONDON EYE", "FXR752512584", "BAL", "rebutjada", "artista_incorrecte"),
    ("Amores de Combate", "Javier Sólo", "Amores de Combate", "ES31E2601733", "CAT", "rebutjada", "no_catala"),
    ("Totems de Sal (Remix)", "Foraster", "Totems de Sal (Remix)", "QZGLM2662586", "BAL", "rebutjada", "artista_incorrecte"),
    ("venenoso", "Iluminata", "venenoso", "BXJFP2600003", "CAT", "rebutjada", "album_incorrecte"),
    ("El Teu Aire", "Ernest Prana", "El Teu Aire", "QZGLM2608168", "CAT", "aprovada", "ok"),
    ("Matar o Morir", "Decibelios", "Jota", "QZTB42679204", "CAT", "rebutjada", "no_catala"),
    ("Botas y Tirantes", "Decibelios", "Jota", "QZTB42679203", "CAT", "rebutjada", "no_catala"),
    ("Viento de Libertad", "Decibelios", "Jota", "QZTB42679202", "CAT", "rebutjada", "no_catala"),
    ("Fill de Puta", "Decibelios", "Jota", "QZTB42679201", "CAT", "rebutjada", "no_catala"),
    ("Piara Indecente", "Decibelios", "Jota", "QZTB42679200", "CAT", "rebutjada", "no_catala"),
    ("Coses del Passat", "David Cabot", "Coses del Passat", "ES8572613301", "BAL", "aprovada", "ok"),
    ("Business Addict", "Chalart58", "Business Addict", "ES77F2600011", "CAT", "rebutjada", "no_catala"),
    ("Candy Freestyle", "Cavallo", "Candy Freestyle", "DEYW82604790", "VAL", "rebutjada", "artista_incorrecte"),
    ("GTC", "Bulma", "GTC", "QZTB52618131", "CAT", "rebutjada", "album_incorrecte"),
    ("Tot aquest temps", "Bucòlic", "L'únic que vull és tornar a casa", "ESA092603237", "CAT", "aprovada", "ok"),
    ("Salvador", "Bucòlic", "L'únic que vull és tornar a casa", "ESA092603236", "CAT", "aprovada", "ok"),
    ("No m'hi caps", "Bucòlic", "L'únic que vull és tornar a casa", "ESA092603235", "CAT", "aprovada", "ok"),
    ("Narcís", "Bucòlic", "L'únic que vull és tornar a casa", "ESA092603234", "CAT", "aprovada", "ok"),
    ("La resposta", "Bucòlic", "L'únic que vull és tornar a casa", "ESA092603233", "CAT", "aprovada", "ok"),
    ("L'únic que vull és tornar a casa", "Bucòlic", "L'únic que vull és tornar a casa", "ESA092603232", "CAT", "aprovada", "ok"),
    ("El pastís", "Bucòlic", "L'únic que vull és tornar a casa", "ESA092603231", "CAT", "aprovada", "ok"),
    ("Descompassats", "Bucòlic", "L'únic que vull és tornar a casa", "ESA092603230", "CAT", "aprovada", "ok"),
    ("La mentida", "Arnau Folch", "La mentida", "ES86D2600698", "CAT", "aprovada", "ok"),
    ("Mateo", "Alfred García", "Mateo", "ES5952507275", "CAT", "rebutjada", "no_catala"),
    ("Si El Amor Me Llama", "Scorpio", "Si El Amor Me Llama", "QT6622691152", "CAT", "rebutjada", "album_incorrecte"),
    ("Corsé", "Quinto", "Corsé", "USA2P2618129", "VAL", "rebutjada", "album_incorrecte"),
    ("fi del món", "Poggioli", "fi del món", "ES5062603805", "CAT", "aprovada", "ok"),
]


created = 0
skipped = 0
for row in DECISIONS:
    canco_nom, artista_nom, album_nom, isrc, territori, decisio, motiu = row
    exists = HistorialRevisio.objects.filter(
        canco_isrc=isrc, canco_nom=canco_nom
    ).exists()
    if exists:
        skipped += 1
        continue
    HistorialRevisio.objects.create(
        canco_nom=canco_nom,
        artista_nom=artista_nom,
        album_nom=album_nom,
        canco_isrc=isrc,
        isrc_prefix=isrc[:2] if len(isrc) >= 2 else "",
        artista_territori=territori,
        decisio=decisio,
        motiu=motiu,
    )
    created += 1

print(f"Created: {created}, Skipped (duplicates): {skipped}")
