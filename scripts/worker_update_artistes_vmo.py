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

log = crear_logger("logs/worker_vmo.log")
log("🎬 Worker VMO iniciat")

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
URL_BASE = "https://valencianmusicoffice.com/va/artists"

# ──────────────── 🧠 Helpers ────────────────


def artista_ja_existeix(id_vmo):
    cur.execute("SELECT 1 FROM artistes_vmo WHERE id_vmo = %s", (id_vmo,))
    return cur.fetchone() is not None


def afegir_columna_si_no_existix(col):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'artistes_vmo' AND column_name = %s
    """,
        (col,),
    )
    if not cur.fetchone():
        log(f"➕ Afegint columna: {col}")
        cur.execute(f'ALTER TABLE artistes_vmo ADD COLUMN "{col}" TEXT')
        conn.commit()


def insertar_artista(dades):
    for col in dades:
        afegir_columna_si_no_existix(col)

    columnes = list(dades.keys())
    valors = [dades[c] for c in columnes]

    placeholders = ", ".join(["%s"] * len(columnes))
    cols_sql = ", ".join(f'"{c}"' for c in columnes)

    query = f"INSERT INTO artistes_vmo ({cols_sql}) VALUES ({placeholders})"
    cur.execute(query, valors)
    conn.commit()


# ──────────────── 📥 Extracció ────────────────


def obtindre_llista_artistes():
    artistes = []
    pagina = 1
    while True:
        url = f"{URL_BASE}?page={pagina}"
        log(f"🌐 Processant pàgina {pagina} → {url}")
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.text, "html.parser")
        targetes = soup.select("div.site-wrapper")

        artistes_pagina = []
        for t in targetes:
            a = t.select_one("a[href]")
            h4 = t.select_one("h4")
            if a and h4:
                artista = {
                    "id_vmo": a["href"].split("/")[-1],
                    "nom": h4.get_text(strip=True),
                    "url": a["href"],
                }
                artistes_pagina.append(artista)

        if not artistes_pagina:
            break  # si no hi ha cap artista amb enllaç i nom, eixim

        artistes.extend(artistes_pagina)
        pagina += 1
        time.sleep(1.5)

    return artistes


def extraure_dades_artista_vmo(artista):
    try:
        res = requests.get(artista["url"], headers=HEADERS)
        soup = BeautifulSoup(res.text, "html.parser")

        dades = {
            "id_vmo": artista["id_vmo"],
            "nom": artista["nom"],
            "url": artista["url"],
        }

        # Biografia
        bio_p = soup.select_one("div.award-details > div > p")
        if bio_p:
            dades["bio"] = bio_p.get_text(strip=True)

        # Contacte: guarda totes les línies com contact1, contact2, etc.
        contacte_h3 = next(
            (
                h3
                for h3 in soup.find_all("h3", class_="underline")
                if h3.get_text(strip=True) in ["Contacte", "Contact"]
            ),
            None,
        )
        if contacte_h3:
            actual = contacte_h3.find_next_sibling()
            count = 1
            while actual and actual.name == "p":
                text = actual.get_text(strip=True)
                if text:
                    dades[f"contact{count}"] = text
                    count += 1
                actual = actual.find_next_sibling()

        # Web
        web = soup.select_one("h3.underline a[href^='http']")
        if web:
            dades["web"] = web["href"]

        # Xarxes
        for li in soup.select(".site-single-share li a[href]"):
            href = li["href"]
            if "facebook.com" in href:
                dades["facebook"] = href
            elif "instagram.com" in href:
                dades["instagram"] = href
            elif "youtube.com" in href:
                dades["youtube"] = href
            else:
                dades[f"xarxa_extra_{href.split('//')[1].split('.')[0]}"] = href

        # PDF
        pdf = soup.select_one("a[href$='.pdf']")
        if pdf:
            dades["pdf"] = pdf["href"]

        # Imatge
        img_div = soup.select_one("div.award-image")
        if img_div and "background-image" in img_div["style"]:
            style = img_div["style"]
            img_url = style.split("url(")[1].split(")")[0]
            dades["imatge"] = img_url

        # YouTube
        iframe = soup.select_one("iframe[src*='youtube.com']")
        if iframe:
            dades["youtube_embed"] = iframe["src"]

        return dades

    except Exception as e:
        log(f"❌ Error extraient dades de {artista['nom']}: {e}")
        return None


# ──────────────── 🚀 Execució ────────────────

artistes = obtindre_llista_artistes()
log(f"🔢 {len(artistes)} artistes detectats")

for artista in artistes:
    if artista_ja_existeix(artista["id_vmo"]):
        log(f"⏭️ Ja existix: {artista['nom']}")
        continue

    dades = extraure_dades_artista_vmo(artista)
    if dades:
        insertar_artista(dades)
        log(f"✅ Afegit: {artista['nom']}")
    time.sleep(2)

cur.close()
conn.close()
log("🏁 Procés completat")
