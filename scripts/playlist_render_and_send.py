# /root/TopQuaranta_Local/scripts/playlist_render_and_send.py
import os
import re
import sys
import time
import argparse
from datetime import date
from urllib.parse import urlparse, parse_qs

import pandas as pd
import psycopg2
import requests
import spotipy
from dotenv import load_dotenv
from spotipy.exceptions import SpotifyException

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Afegim la carpeta arrel per a utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import crear_logger
from utils.imatges import genera_imatge_top_bloc  # ja dibuixa com els blocs del rànquing

# ──────────────────────────────────────────────────────────────────────────────
# Config / helpers
# ──────────────────────────────────────────────────────────────────────────────
log = crear_logger(os.path.join(BASE_DIR, "logs", "playlist_render_and_send.log"))
load_dotenv()

# Telegram opcional
try:
    from telegram import Bot
    from telegram.utils.request import Request
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    if TELEGRAM_CHAT_ID:
        TELEGRAM_CHAT_ID = int(TELEGRAM_CHAT_ID)
except Exception:
    TELEGRAM_TOKEN = None
    TELEGRAM_CHAT_ID = None

def get_access_token_from_refresh(client_id, client_secret, refresh_token):
    auth_str = f"{client_id}:{client_secret}".encode()
    b64_auth = __import__("base64").b64encode(auth_str).decode()
    headers = {"Authorization": f"Basic {b64_auth}", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    r = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]

def parse_playlist_id(s: str) -> str:
    """
    Accepta:
      - ID pur: 37i9dQZF1DX… (cap slash)
      - URL web: https://open.spotify.com/playlist/<id>?si=...
      - URI: spotify:playlist:<id>
    """
    s = s.strip()
    if s.startswith("spotify:playlist:"):
        return s.split("spotify:playlist:")[-1].split("?")[0]
    if "open.spotify.com/playlist/" in s:
        path = urlparse(s).path  # /playlist/<id>
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "playlist":
            return parts[1]
    # fallback: suposem que és l'ID directament
    return re.sub(r"[^A-Za-z0-9]", "", s)

def obtindre_tracks_playlist(sp, id_playlist, intents=3):
    for intent in range(intents):
        try:
            items = []
            results = sp.playlist_items(id_playlist, additional_types=["track"], limit=100, offset=0)
            items.extend(results.get("items", []))
            while results.get("next"):
                results = sp.next(results)
                items.extend(results.get("items", []))
            return items
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 5))
                log(f"⚠️ Rate limit Spotify. Esperant {retry_after}s…")
                time.sleep(retry_after)
            elif e.http_status >= 500:
                espera = 5 * (intent + 1)
                log(f"⚠️ Error {e.http_status} de Spotify. Reintent en {espera}s…")
                time.sleep(espera)
            else:
                raise
    raise RuntimeError("❌ No s'han pogut obtindre els ítems de la playlist.")

def reorder_playlist_by_popularity(sp, playlist_id, items):
    # Extraiem (uri, popularity) de cada track vàlid
    tracks = []
    for it in items:
        tr = it.get("track")
        if not tr or tr.get("is_local"):
            continue
        uri = tr.get("uri")
        pop = tr.get("popularity", 0) or 0
        tracks.append((uri, pop))
    if not tracks:
        return 0

    # Ordenem descendent per popularitat i reescrivim la playlist
    uris_sorted = [uri for uri, _ in sorted(tracks, key=lambda x: x[1], reverse=True)]

    # Esborrem totes les ocurrències (com al teu diari)
    if uris_sorted:
        # Carrega actual per esborrar
        current = obtindre_tracks_playlist(sp, playlist_id)
        uris_actuals = [it["track"]["uri"] for it in current if it.get("track")]
        if uris_actuals:
            sp.playlist_remove_all_occurrences_of_items(playlist_id, uris_actuals)
            log(f"🗑️ {len(uris_actuals)} cançons esborrades")

        # Afig en blocs de 100
        for i in range(0, len(uris_sorted), 100):
            sp.playlist_add_items(playlist_id, uris_sorted[i : i + 100])
    return len(uris_sorted)

def build_dataframe_from_playlist_items(items):
    """
    Construeix un DataFrame amb les columnes que espera genera_imatge_top_bloc:
      - posicio_territori (1..N)
      - titol
      - artistes (llista de noms)
      - artistes_ids (llista d'IDs)
      - album_titol
      - album_caratula_url
      - id_canco
      - album_id
      - album_data (release_date ISO si disponible)
      - canvi_posicio (None)  -> no la fem servir ací
    """
    rows = []
    for it in items:
        tr = it.get("track")
        if not tr:
            continue
        # Camps base
        tid = tr.get("id")
        tname = tr.get("name") or ""
        artists = tr.get("artists") or []
        artist_names = [a.get("name", "") for a in artists if a]
        artist_ids = [a.get("id") for a in artists if a and a.get("id")]
        album = tr.get("album") or {}
        album_name = album.get("name") or ""
        album_id = album.get("id")
        album_date = album.get("release_date")
        images = album.get("images") or []
        cover = images[0]["url"] if images else None

        rows.append(
            {
                "titol": tname,
                "artistes": artist_names,
                "artistes_ids": artist_ids,
                "album_titol": album_name,
                "album_caratula_url": cover,
                "id_canco": tid,
                "album_id": album_id,
                "album_data": album_date,
                "canvi_posicio": None,
            }
        )

    if not rows:
        return pd.DataFrame(columns=[
            "posicio_territori","titol","artistes","artistes_ids",
            "album_titol","album_caratula_url","id_canco","album_id",
            "album_data","canvi_posicio"
        ])

    # Ordenació per popularitat desc (per coherència amb la reordenació)
    # Si per qualsevol motiu calguera, traiem la popularitat i ordenem ací també:
    pops = []
    for it in items:
        tr = it.get("track")
        pops.append(tr.get("popularity", 0) if tr else 0)
    df = pd.DataFrame(rows)
    df["__pop"] = pops
    df = df.sort_values("__pop", ascending=False).drop(columns="__pop").reset_index(drop=True)

    # posicio_territori 1..N
    df["posicio_territori"] = range(1, len(df) + 1)
    return df

def safe_name(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s.strip()).strip("_")[:60]

def send_telegram_images(folder_posts):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("⚠️ TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurats. No s'envien imatges.")
        return 0
    bot = Bot(token=TELEGRAM_TOKEN, request=Request(con_pool_size=8))
    enviades = 0
    for nom in sorted(os.listdir(folder_posts)):
        if nom.endswith(".png"):
            ruta = os.path.join(folder_posts, nom)
            with open(ruta, "rb") as fh:
                bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=fh)
            enviades += 1
    return enviades

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Reordena una playlist per popularitat desc, genera imatges de blocs i (opcionalment) les envia per \
Telegram."
    )
    parser.add_argument("playlist", help="ID, URL o URI de la playlist pròpia de Spotify")
    parser.add_argument("--territori", default="ppcc", help="Per a paleta i logo (pv|cat|ib|ppcc). Per defecte: ppcc")
    parser.add_argument("--no-reorder", action="store_true", help="No reordenar la playlist (només generar imatges)")
    parser.add_argument("--no-send", action="store_true", help="No enviar per Telegram (només generar)")
    parser.add_argument("--max", type=int, default=40, help="Límit de cançons per a les imatges (per defecte 40)")
    args = parser.parse_args()

    playlist_id = parse_playlist_id(args.playlist)

    # Spotify auth (mateix estil que update_playlist_daily.py però amb credencials *PLAYLIST*)
    access_token = get_access_token_from_refresh(
        os.getenv("SPOTIPY_CLIENT_ID_PLAYLIST"),
        os.getenv("SPOTIPY_CLIENT_SECRET_PLAYLIST"),
        os.getenv("SPOTIFY_REFRESH_TOKEN_PLAYLIST"),
    )
    sp = spotipy.Spotify(auth=access_token)

    # Llig playlist meta (nom) per a la carpeta
    meta = sp.playlist(playlist_id, fields="name,owner(id),tracks(total)")
    pl_name = meta.get("name", f"playlist_{playlist_id}")
    total = (meta.get("tracks") or {}).get("total", 0)
    log(f"🎧 Playlist: {pl_name} ({total} pistes)")

    # Ítems
    items = obtindre_tracks_playlist(sp, playlist_id)
    if not items:
        log("❌ Playlist buida o sense cançons vàlides.")
        return

    # Reordenació in-place (esborra i reafegeix) — opcional
    if not args.no_reorder:
        n = reorder_playlist_by_popularity(sp, playlist_id, items)
        log(f"✅ Playlist reordenada per popularitat (total {n})")

        # Torna a llegir ítems ja reordenats per assegurar coherència
        items = obtindre_tracks_playlist(sp, playlist_id)

    # Construeix DF per a imatges (coherent amb genera_imatge_top_bloc)
    df = build_dataframe_from_playlist_items(items)
    if df.empty:
        log("❌ No hi ha dades per generar imatges.")
        return

    # Limitem a N (per defecte Top 40) i renumerem posicions
    df = df.head(max(1, args.max)).copy()
    df["posicio_territori"] = range(1, len(df) + 1)

    # Carpetes d’eixida
    label = date.today().strftime("%Y%m%d")
    base_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outputs"))
    folder = os.path.join(base_out, "playlist", f"{safe_name(pl_name)}_{label}", args.territori)
    folder_posts = os.path.join(folder, "posts")
    os.makedirs(folder_posts, exist_ok=True)

    # Build dynamic chunks to avoid orphan blocks:
    # choose k so that each block size is between 10 and 15
    def make_blocks(n):
        # Try k from ceil(n/15) to ceil(n/10) to find a valid partition
        import math
        k_min = max(1, math.ceil(n / 15))
        k_max = max(1, math.ceil(n / 10))
        for k in range(k_min, k_max + 1):
            size_min = n // k
            size_max = (n + k - 1) // k  # ceil
            if 10 <= size_min <= 15 and 10 <= size_max <= 15:
                # Distribute remainder (n - size_min*k) as +1 to the first r chunks
                r = n - size_min * k
                sizes = [size_min + 1] * r + [size_min] * (k - r)
                starts, trams_local = [], []
                s = 1
                for sz in sizes:
                    trams_local.append((s, s + sz - 1))
                    s += sz
                return trams_local
        # Fallback: blocks of 12 with a possible last 10–15
        sizes = []
        remain = n
        while remain > 0:
            if 10 <= remain <= 15:
                sizes.append(remain)
                break
            take = 12 if remain - 12 >= 10 else min(15, remain)
            sizes.append(take)
            remain -= take
        trams_local, s = [], 1
        for sz in sizes:
            trams_local.append((s, s + sz - 1))
            s += sz
        return trams_local

    n = len(df)
    trams = make_blocks(n)


    # Crida a la teua funció d'imatges per a cada tram
    for (ini, fi) in trams:
        genera_imatge_top_bloc(
            df,
            ini,
            fi,
            label_data=label,
            carpeta_sortida=folder_posts,
            territori=args.territori,
            # New options:
            titol_portada=pl_name,     # show playlist title on the simple cover
            simple_portada=True,       # one simple cover, no artist photos
            mostrar_footer=False,      # remove explanatory footer text
            color_top1=False,          # first row uses normal alternating bg
        )

        log(f"🖼️ Bloc {ini}-{fi} generat")

    log(f"📁 Imatges guardades a: {folder_posts}")

    # Telegram opcional
    if not args.no_send:
        enviades = send_telegram_images(folder_posts)
        log(f"📤 {enviades} imatges enviades per Telegram")

if __name__ == "__main__":
    main()
