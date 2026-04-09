import base64
import os
import sys
import time
import warnings
from datetime import date, timedelta

import psycopg2
import requests
import spotipy
from dotenv import load_dotenv
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

# Afegim la carpeta arrel per poder importar utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import crear_logger
from utils.playlists import PLAYLIST_IDS

log = crear_logger("logs/update_playlist_daily.log")


def get_access_token_from_refresh(client_id, client_secret, refresh_token):
    auth_str = f"{client_id}:{client_secret}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}

    response = requests.post(
        "https://accounts.spotify.com/api/token", headers=headers, data=data
    )
    response.raise_for_status()
    return response.json()["access_token"]


def obtindre_tracks_playlist(id_playlist, intents=3):
    for intent in range(intents):
        try:
            return sp.playlist_items(id_playlist)["items"]
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 5))
                log(
                    f"⚠️ Has superat el límit de l'API. Esperant {retry_after} segons..."
                )
                time.sleep(retry_after)
            elif e.http_status >= 500:
                espera = 5 * (intent + 1)
                log(
                    f"⚠️ Error del servidor Spotify ({e.http_status}). Reintent en {espera} segons..."
                )
                time.sleep(espera)
            else:
                raise
    raise Exception("❌ No s'ha pogut obtindre la llista després de diversos intents.")


# 📦 Carrega variables d'entorn
load_dotenv()

# 🗓️ Data d'avui i d'ahir
avui = date.today()
ahir = avui - timedelta(days=1)

# Connexió a la BBDD
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT"),
)
cur = conn.cursor()

# 🔐 Spotify auth
access_token = get_access_token_from_refresh(
    os.getenv("SPOTIPY_CLIENT_ID_PLAYLIST"),
    os.getenv("SPOTIPY_CLIENT_SECRET_PLAYLIST"),
    os.getenv("SPOTIFY_REFRESH_TOKEN_PLAYLIST"),
)
sp = spotipy.Spotify(auth=access_token)

# 🔁 Territoris que volem combinar
territoris_codis = ["pv", "cat", "ib", "altres"]

# 📥 Llig totes les cançons de les views territorials
vistes_usades = []
track_info = {}

for territori_codi in territoris_codis:
    view_name = f"vw_top40_weekly_{territori_codi}"
    cur.execute(f"SELECT id_canco, score_setmanal FROM {view_name};")
    results = cur.fetchall()
    vistes_usades.append((view_name, len(results)))
    for canco_id, score in results:
        if canco_id not in track_info or score > track_info[canco_id]:
            track_info[canco_id] = score

# 🔽 Ordena per popularitat (de més a menys)
track_ids_ordenats = sorted(
    track_info.keys(), key=lambda x: track_info[x], reverse=True
)[:100]

# 🎯 ID de la playlist daily
playlist_id = PLAYLIST_IDS.get("daily")
if not playlist_id:
    log("❌ No s'ha trobat cap playlist amb la clau 'daily'")
    exit()

# 🧹 Esborra les cançons actuals
current_tracks = obtindre_tracks_playlist(playlist_id)
uris_actuals = [item["track"]["uri"] for item in current_tracks if item.get("track")]
if uris_actuals:
    sp.playlist_remove_all_occurrences_of_items(playlist_id, uris_actuals)
    log(f"🗑️ {len(uris_actuals)} cançons esborrades de la playlist 'daily'")

# ➕ Afig les noves cançons
for i in range(0, len(track_ids_ordenats), 100):
    sp.playlist_add_items(playlist_id, track_ids_ordenats[i : i + 100])

# ✅ Actualitza playlist 'daily' general
log(f"✅ {len(track_ids_ordenats)} cançons afegides a la playlist 'daily'")

# 🔄 Actualitza les playlists territorials
for territori_codi in territoris_codis:
    playlist_key = f"daily_{territori_codi}"
    playlist_id_territorial = PLAYLIST_IDS.get(playlist_key)
    if not playlist_id_territorial:
        log(f"⚠️ No s'ha trobat cap playlist per al territori '{territori_codi}'")
        continue

    # Llig les cançons d'esta view territorial
    view_name = f"vw_top40_weekly_{territori_codi}"
    cur.execute(f"SELECT id_canco FROM {view_name} ORDER BY score_setmanal DESC;")
    results = cur.fetchall()
    track_ids_territorials = [r[0] for r in results]

    # 🧹 Esborra les cançons actuals
    current_tracks_territorials = sp.playlist_items(playlist_id_territorial)["items"]
    uris_actuals_territorials = [
        item["track"]["uri"]
        for item in current_tracks_territorials
        if item.get("track")
    ]
    if uris_actuals_territorials:
        sp.playlist_remove_all_occurrences_of_items(
            playlist_id_territorial, uris_actuals_territorials
        )

    # ➕ Afig les noves cançons
    for i in range(0, len(track_ids_territorials), 100):
        sp.playlist_add_items(
            playlist_id_territorial, track_ids_territorials[i : i + 100]
        )

    log(
        f"🎧 Playlist 'daily_{territori_codi}' actualitzada amb {len(track_ids_territorials)} cançons"
    )

for v, n in vistes_usades:
    log(f"  ↳ {v}: {n} cançons")

# 🧠 Guarda ranking diari per cada territori
for territori_codi in territoris_codis:
    view_name = f"vw_top40_{territori_codi}"

    # Llig dades de la view
    cur.execute(
        f"""
        SELECT posicio, titol, artistes, album_titol, popularity, followers,
               id_canco, artistes_ids, album_id, album_data, album_caratula_url
        FROM {view_name}
    """
    )
    ranking_hui = cur.fetchall()

    # Obté les posicions d'ahir
    cur.execute(
        """
        SELECT id_canco, posicio
        FROM ranking_diari
        WHERE data = %s AND territori = %s
    """,
        (ahir, territori_codi),
    )
    ranking_ahir = {row[0]: row[1] for row in cur.fetchall()}

    # Guarda en la taula ranking_diari
    for fila in ranking_hui:
        (
            posicio,
            titol,
            artistes,
            album_titol,
            popularity,
            followers,
            id_canco,
            artistes_ids,
            album_id,
            album_data,
            album_caratula_url,
        ) = fila

        posicio_ahir = ranking_ahir.get(id_canco)
        canvi_posicio = None
        if posicio_ahir:
            canvi_posicio = posicio_ahir - posicio  # positiu = puja, negatiu = baixa

        cur.execute(
            """
            INSERT INTO ranking_diari (
                data, territori, posicio, id_canco,
                titol, artistes, album_titol, popularitat, followers,
                artistes_ids, album_id, album_data, album_caratula_url, canvi_posicio
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (data, territori, posicio) DO UPDATE SET
                id_canco = EXCLUDED.id_canco,
                titol = EXCLUDED.titol,
                artistes = EXCLUDED.artistes,
                album_titol = EXCLUDED.album_titol,
                popularitat = EXCLUDED.popularitat,
                followers = EXCLUDED.followers,
                artistes_ids = EXCLUDED.artistes_ids,
                album_id = EXCLUDED.album_id,
                album_data = EXCLUDED.album_data,
                album_caratula_url = EXCLUDED.album_caratula_url,
                canvi_posicio = EXCLUDED.canvi_posicio
        """,
            (
                avui,
                territori_codi,
                posicio,
                id_canco,
                titol,
                artistes,
                album_titol,
                popularity,
                followers,
                artistes_ids,
                album_id,
                album_data,
                album_caratula_url,
                canvi_posicio,
            ),
        )

    log(f"📊 Ranking guardat en la taula per {territori_codi}")

log(
    "  📍 "
    + ", ".join([f"{v.replace('vw_top40_', '')}: {n}" for v, n in vistes_usades])
)
log(f"  🌍 {len(track_ids_ordenats)} cançons globals")
log(f"✅ Finalitzada actualització Playlists:")
# 🔥 Actualitza playlists de novetats (una per dia)
# Lògica de dates:
# - Per a cada dia de la setmana, triem la data més recent d'eixe dia ≤ avui.
dies_setmana = [
    ("dilluns", 0),
    ("dimarts", 1),
    ("dimecres", 2),
    ("dijous", 3),
    ("divendres", 4),
    ("dissabte", 5),
    ("diumenge", 6),
]


def data_per_al_dia(weekday_objectiu, hui):
    offset = (hui.weekday() - weekday_objectiu) % 7
    return hui - timedelta(days=offset)


for nom_dia, weekday in dies_setmana:
    playlist_key = f"novetats_{nom_dia}"
    playlist_id_dia = PLAYLIST_IDS.get(playlist_key)

    if not playlist_id_dia:
        log(
            f"⚠️ No s'ha trobat cap playlist amb la clau '{playlist_key}'. Saltem {nom_dia}."
        )
        continue

    data_objectiu = data_per_al_dia(weekday, avui)

    # 📥 Traem directament de la taula base 'spotify_tracks'
    # Ens assegurem que la data tinga format 'YYYY-MM-DD' (length=10) i coincidisca exactament.
    cur.execute(
        """
        SELECT id
        FROM spotify_tracks
        WHERE length(album_release_date) = 10
          AND to_date(album_release_date, 'YYYY-MM-DD') = %s
        ORDER BY popularity DESC
        LIMIT 100
    """,
        (data_objectiu,),
    )
    tracks_dia = [r[0] for r in cur.fetchall()]

    # 🧹 Esborrem tot el que hi haja ara mateix en la playlist del dia
    tracks_actuals_dia = obtindre_tracks_playlist(playlist_id_dia)
    uris_actuals_dia = [
        item["track"]["uri"] for item in tracks_actuals_dia if item.get("track")
    ]
    if uris_actuals_dia:
        sp.playlist_remove_all_occurrences_of_items(playlist_id_dia, uris_actuals_dia)
        log(f"🗑️ {len(uris_actuals_dia)} esborrades en 'novetats_{nom_dia}'")

    # ➕ Afig fins a 100 cançons (batxos de 100 per seguretat)
    for i in range(0, len(tracks_dia), 100):
        sp.playlist_add_items(playlist_id_dia, tracks_dia[i : i + 100])

    log(
        f"🆕 'novetats_{nom_dia}' ({data_objectiu.isoformat()}) actualitzada amb {len(tracks_dia)} cançons"
    )

# 🔚 Confirma i tanca
conn.commit()

# 📤 Exporta artistes i ranking_diari a CSV
import pandas as pd

output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "export_postgresql")
)
os.makedirs(output_path, exist_ok=True)

taules_exportar = ["artistes", "artistes_viasona", "ranking_diari"]

for taula in taules_exportar:
    df = pd.read_sql_query(f"SELECT * FROM {taula}", conn)

    if taula == "ranking_diari":
        # 💥 Corregeix casos on artistes és ['Anna Andreu, Mar Pujol'] (una sola string amb coma)
        def corregir_artistes_llista(artistes):
            if (
                isinstance(artistes, list)
                and len(artistes) == 1
                and isinstance(artistes[0], str)
                and "," in artistes[0]
            ):
                return [a.strip() for a in artistes[0].split(",")]
            return artistes

        df["artistes"] = df["artistes"].apply(corregir_artistes_llista)

        # 🕵️‍♂️ Busca desquadres entre artistes i artistes_ids
        desquadres = df[
            df.apply(
                lambda row: isinstance(row["artistes"], list)
                and isinstance(row["artistes_ids"], list)
                and len(row["artistes"]) != len(row["artistes_ids"]),
                axis=1,
            )
        ]

        if not desquadres.empty:
            log("❌ Desquadres detectats entre 'artistes' i 'artistes_ids':")
            for idx, row in desquadres.iterrows():
                log(
                    f"- Fila {idx} | id_canco: {row['id_canco']} | artistes: {row['artistes']} | artistes_ids: {row['art\
istes_ids']}"
                )
        else:
            df = df.explode(["artistes", "artistes_ids"])
            df = df.rename(
                columns={"artistes": "artista", "artistes_ids": "artista_id"}
            )

    df.to_csv(os.path.join(output_path, f"{taula}.csv"), index=False)

# 🔚 Tanca connexió
cur.close()
conn.close()
