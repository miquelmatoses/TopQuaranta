import os
import sys
import time
from urllib.parse import urljoin

import psycopg2
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ──────────────── 🔧 Config ────────────────

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

from utils.logger import crear_logger

log = crear_logger("logs/worker_viasona.log")
log("🎬 Script iniciat")

print("📦 DB_HOST:", os.getenv("DB_HOST"))  # ara sí que funciona

# Connexió a BBDD
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT"),
)
cur = conn.cursor()

HEADERS = {"User-Agent": "Mozilla/5.0"}
URL_BASE = "https://www.viasona.cat"
LLETRES = [
    "numeros",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
]

# ──────────────── 📥 Extracció artista ────────────────


def obtindre_artistes_per_lletra(lletra):
    artistes = []
    pagina = 1
    while True:
        url = (
            f"{URL_BASE}/grups/lletra/{lletra}"
            if pagina == 1
            else f"{URL_BASE}/grups/lletra/{lletra}/pagina/{pagina}"
        )
        log(f"🌐 Processant lletra: {lletra} → {url}")
        try:
            res = requests.get(url, headers=HEADERS)
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.select("ul.llista-noestil li a")
            enllaços_valids = []
            for link in links:
                href = link.get("href", "")
                if "/grup/" not in href:
                    continue
                nom_tag = link.select_one("p.enc-llistat__title")
                nom = (
                    nom_tag.get_text(strip=True)
                    if nom_tag
                    else link.get_text(strip=True)
                )
                url_completa = (
                    href if href.startswith("http") else urljoin(URL_BASE, href)
                )
                enllaços_valids.append(
                    {"id_viasona": href.split("/")[-1], "nom": nom, "url": url_completa}
                )

            if not enllaços_valids:
                break  # eixim si no hi ha cap grup vàlid

            artistes.extend(enllaços_valids)
            log(
                f"🎶 {len(enllaços_valids)} artistes vàlids trobats per pàgina {pagina}"
            )
            pagina += 1
            time.sleep(1.5)
        except Exception as e:
            log(f"❌ Error a {url}: {e}")
            break
    log(f"✅ Total artistes trobats per {lletra}: {len(artistes)}")
    return artistes


def artista_ja_existeix(slug):
    cur.execute("SELECT 1 FROM artistes_viasona WHERE id_viasona = %s", (slug,))
    return cur.fetchone() is not None


def extraure_dades_artista(artista):
    try:
        res = requests.get(artista["url"], headers=HEADERS)
        soup = BeautifulSoup(res.text, "html.parser")
        dades = {
            "id_viasona": artista["id_viasona"],
            "nom": artista["nom"],
            "url": artista["url"],
        }

        # Dades: municipi i comarca
        grup_a = soup.find("div", class_="grup-a")
        if grup_a:
            lloc = grup_a.select_one("li.ico-location")
            if lloc:
                links = lloc.select("a")
                if len(links) >= 1:
                    dades["municipi"] = links[0].get_text(strip=True)
                if len(links) >= 2:
                    dades["comarca"] = links[1].get_text(strip=True)

        # Xarxes
        grup_b = soup.find("div", class_="grup-b")
        if grup_b:
            for li in grup_b.select("ul.llista-noestil li"):
                a = li.find("a", href=True)
                if a:
                    xarxa = li.get_text(strip=True).lower()
                    href = a["href"].strip()
                    if xarxa and href:
                        dades[xarxa] = href

        return dades
    except Exception as e:
        log(f"❌ Error extraient dades de {artista['nom']}: {e}")
        return None


def afegir_columna_si_no_existix(col):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'artistes_viasona' AND column_name = %s
    """,
        (col,),
    )
    if not cur.fetchone():
        log(f"➕ Afegint columna: {col}")
        cur.execute(f'ALTER TABLE artistes_viasona ADD COLUMN "{col}" TEXT')
        conn.commit()


def insertar_artista(dades):
    for col in dades:
        afegir_columna_si_no_existix(col)

    columnes = list(dades.keys())
    valors = [dades[c] for c in columnes]

    placeholders = ", ".join(["%s"] * len(columnes))
    cols_sql = ", ".join(f'"{c}"' for c in columnes)

    query = f"INSERT INTO artistes_viasona ({cols_sql}) VALUES ({placeholders})"
    cur.execute(query, valors)
    conn.commit()


# ──────────────── 🚀 Execució ────────────────

for lletra in LLETRES:
    artistes = obtindre_artistes_per_lletra(lletra)
    for artista in artistes:
        if artista_ja_existeix(artista["id_viasona"]):
            continue

        dades = extraure_dades_artista(artista)
        if dades:
            insertar_artista(dades)
            log(f"✅ {artista['nom']} afegit a artistes_viasona.")
        time.sleep(3)

cur.close()
conn.close()
