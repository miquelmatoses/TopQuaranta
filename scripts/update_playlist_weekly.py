import base64
import os
import sys
from datetime import date, timedelta

import pandas as pd
import psycopg2
import requests
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

# Afegim la carpeta arrel per poder importar utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import crear_logger
from utils.playlists import PLAYLIST_IDS

log = crear_logger("logs/update_playlist_weekly.log")


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


# 📦 Carrega variables d'entorn
load_dotenv()

# 🗓️ Data de dissabte actual i dissabte anterior
avui = date.today()
avui = avui + timedelta((5 - avui.weekday()) % 7)  # dissabte actual
ahir = avui - timedelta(days=7)  # dissabte anterior

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

# 📥 Llig les cançons de la view global amb score_global i les ordena
cur.execute(
    """
    SELECT id_canco
    FROM vw_top40_weekly_ppcc
    ORDER BY posicio ASC
    LIMIT 40
"""
)
track_ids_ordenats = [r[0] for r in cur.fetchall()]

# 🎯 ID de la playlist weekly
playlist_id = PLAYLIST_IDS.get("weekly")
if not playlist_id:
    log("❌ No s'ha trobat cap playlist amb la clau 'weekly'")
    exit()

# 🧹 Esborra les cançons actuals
current_tracks = sp.playlist_items(playlist_id)["items"]
uris_actuals = [item["track"]["uri"] for item in current_tracks if item.get("track")]
if uris_actuals:
    sp.playlist_remove_all_occurrences_of_items(playlist_id, uris_actuals)
    log(f"🗑️ {len(uris_actuals)} cançons esborrades de la playlist 'weekly'")

# ➕ Afig les noves cançons
if track_ids_ordenats:
    sp.playlist_add_items(playlist_id, track_ids_ordenats)

# ✅ Actualitza playlist 'weekly' general
log(f"✅ {len(track_ids_ordenats)} cançons afegides a la playlist 'weekly'")

# 🔄 Actualitza les playlists territorials
for territori_codi in territoris_codis:
    playlist_key = f"weekly_{territori_codi}"
    playlist_id_territorial = PLAYLIST_IDS.get(playlist_key)
    if not playlist_id_territorial:
        log(f"⚠️ No s'ha trobat cap playlist per al territori '{territori_codi}'")
        continue

    # Llig les cançons d'esta view territorial
    view_name = f"vw_top40_weekly_{territori_codi}"
    cur.execute(f"SELECT id_canco FROM {view_name} ORDER BY posicio ASC LIMIT 40;")
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
    if track_ids_territorials:
        sp.playlist_add_items(playlist_id_territorial, track_ids_territorials)

    log(
        f"🎧 Playlist 'weekly_{territori_codi}' actualitzada amb {len(track_ids_territorials)} cançons"
    )

# 🧠 Guarda ranking setmanal per cada territori
for territori_codi in territoris_codis:
    view_name = f"vw_top40_weekly_{territori_codi}"

    # Llig dades de la view
    cur.execute(
        f"""
        SELECT posicio, titol, artistes, album_titol, score_setmanal,
               id_canco, artistes_ids, album_id, album_data, album_caratula_url
        FROM {view_name}
        ORDER BY posicio ASC
        LIMIT 40
    """
    )
    ranking_hui = cur.fetchall()

    # Obté les posicions d'ahir
    cur.execute(
        """
        SELECT id_canco, posicio
        FROM ranking_setmanal
        WHERE data = %s AND territori = %s
    """,
        (ahir, territori_codi),
    )
    ranking_ahir = {row[0]: row[1] for row in cur.fetchall()}

    # Guarda en la taula ranking_setmanal
    for fila in ranking_hui:
        (
            posicio,
            titol,
            artistes,
            album_titol,
            score_setmanal,
            id_canco,
            artistes_ids,
            album_id,
            album_data,
            album_caratula_url,
        ) = fila

        # Penalització per territori (4% per cada posició a partir de la 2a)
        penalitzacio = (posicio - 1) * 0.04
        score_global = (
            round(float(score_setmanal) * (1 - penalitzacio), 2)
            if score_setmanal
            else 0
        )

        posicio_ahir = ranking_ahir.get(id_canco)
        canvi_posicio = None
        if posicio_ahir:
            canvi_posicio = posicio_ahir - posicio  # positiu = puja, negatiu = baixa

        cur.execute(
            """
            INSERT INTO ranking_setmanal (
                data, territori, posicio, id_canco,
                titol, artistes, album_titol, score_setmanal, score_global,
                artistes_ids, album_id, album_data, album_caratula_url, canvi_posicio
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (data, territori, posicio) DO UPDATE SET
                id_canco = EXCLUDED.id_canco,
                titol = EXCLUDED.titol,
                artistes = EXCLUDED.artistes,
                album_titol = EXCLUDED.album_titol,
                score_setmanal = EXCLUDED.score_setmanal,
                score_global = EXCLUDED.score_global,
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
                score_setmanal,
                score_global,
                artistes_ids,
                album_id,
                album_data,
                album_caratula_url,
                canvi_posicio,
            ),
        )

    log(f"📊 Ranking guardat en la taula per {territori_codi}")

log(f"  🌍 {len(track_ids_ordenats)} cançons globals")
log(f"✅ Finalitzada actualització Playlists:")

# 🔚 Confirma i tanca
conn.commit()

# 📤 Exporta artistes i ranking_setmanal a CSV
output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "export_postgresql")
)
os.makedirs(output_path, exist_ok=True)

taules_exportar = ["artistes", "ranking_setmanal"]

for taula in taules_exportar:
    df = pd.read_sql_query(f"SELECT * FROM {taula}", conn)

    if taula == "ranking_setmanal":
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
            print("❌ Desquadres detectats entre 'artistes' i 'artistes_ids':")
            for idx, row in desquadres.iterrows():
                print(
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
