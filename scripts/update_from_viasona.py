# scripts/update_viasona_localitats.py

import os
import time

import psycopg2
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from unidecode import unidecode

# ℹ️ Paquet addicional si no tens `unidecode`
# pip install Unidecode

HEADERS = {"User-Agent": "Mozilla/5.0"}


# 🔤 Normalitza el nom per a crear el slug de Viasona
def generar_slug(nom):
    slug = unidecode(nom.lower())
    slug = slug.replace("'", "").replace("·", "").replace("’", "")
    slug = "".join(c for c in slug if c.isalnum() or c in [" ", "-"])
    slug = slug.replace(" ", "-")
    return slug


# 🌐 Rasca dades de Viasona
def rascar_dades_viasona(slug):
    url = f"https://www.viasona.cat/grup/{slug}"
    res = requests.get(url, headers=HEADERS, timeout=10)
    if res.status_code != 200:
        return None

    soup = BeautifulSoup(res.text, "html.parser")
    lloc = soup.select_one("li.ico-location")
    localitat, comarca = None, None
    if lloc:
        enllacos = lloc.find_all("a")
        if len(enllacos) >= 2:
            localitat = enllacos[0].text.strip()
            comarca = enllacos[1].text.strip()

    insta = soup.select_one("li.xar-instagram a")
    instagram = insta["href"] if insta and insta.has_attr("href") else None

    return localitat, comarca, instagram


# 📦 Carrega entorn i connexió
load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT"),
)
cur = conn.cursor()

# 🔍 Selecciona artistes sense localitat ni comarca
cur.execute(
    """
    SELECT id_spotify, nom, popularitat
    FROM artistes
    WHERE (localitat IS NULL OR localitat = '' OR
       comarca IS NULL OR comarca = '' OR
       instagram IS NULL OR instagram = '')
    ORDER BY popularitat DESC NULLS LAST
"""
)
artistes = cur.fetchall()

print(f"🎯 {len(artistes)} artistes a revisar...")

for i, (id_artista, nom, _) in enumerate(artistes, start=1):
    slug = generar_slug(nom)
    try:
        dades = rascar_dades_viasona(slug)
        if not dades:
            print(f"❌ [{i}] No trobada fitxa per {nom}")
            continue

        localitat, comarca, instagram = dades

        if not any([localitat, comarca, instagram]):
            print(f"⚠️ [{i}] Sense dades útils per a {nom}")
            continue

        # ⚙️ Actualitza només els camps disponibles
        actualitzacions = []
        valors = []

        if localitat:
            actualitzacions.append("localitat = %s")
            valors.append(localitat)
        if comarca:
            actualitzacions.append("comarca = %s")
            valors.append(comarca)
        if instagram:
            actualitzacions.append("instagram = %s")
            valors.append(instagram)

        if actualitzacions:
            valors.append(id_artista)
            query = f"""
                UPDATE artistes
                SET {', '.join(actualitzacions)}
                WHERE id_spotify = %s
            """
            cur.execute(query, valors)
            conn.commit()
            print(f"✅ [{i}] Actualitzat: {nom}")
        else:
            print(f"➖ [{i}] Cap dada nova per {nom}")

        time.sleep(2.5)  # ⏳ Per no saturar Viasona

    except Exception as e:
        print(f"🚫 [{i}] Error amb {nom}: {e}")
        continue

cur.close()
conn.close()
print("🏁 Procés completat.")
