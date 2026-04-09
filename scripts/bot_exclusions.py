import json
import os
import re
import sys

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from telegram import Bot

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import crear_logger

logger = crear_logger("logs/bot_exclusions.log")

# 📦 Carrega entorn
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
LAST_ID_FILE = ".last_update_id"

# 🔌 Connexió PostgreSQL
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT"),
)

cur = conn.cursor(cursor_factory=RealDictCursor)

# 🤖 Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)


# 🎯 Funció per extraure ID de cançó, àlbum o artista
def extract_track_id(text):
    match = re.search(r"open\.spotify\.com/track/([a-zA-Z0-9]+)", text)
    return match.group(1) if match else None


def extract_album_id(text):
    match = re.search(r"open\.spotify\.com/album/([a-zA-Z0-9]+)", text)
    return match.group(1) if match else None


def extract_artist_id(text):
    match = re.search(r"open\.spotify\.com/artist/([a-zA-Z0-9]+)", text)
    return match.group(1) if match else None


# 🔁 Recupera últim update_id
if os.path.exists(LAST_ID_FILE):
    with open(LAST_ID_FILE, "r") as f:
        last_update_id = int(f.read())
else:
    last_update_id = None

# 🔁 Processa missatges nous
updates = bot.get_updates(
    offset=(last_update_id + 1) if last_update_id else None, timeout=10
)

try:
    for update in updates:
        if not update.message or update.message.chat_id != CHAT_ID:
            continue

        text = update.message.text
        update_id = update.update_id
        track_id = extract_track_id(text)
        album_id = extract_album_id(text)
        artist_id = extract_artist_id(text)

        if artist_id:
            try:
                # 1) Baixa a OUT en 'artistes' (si existix)
                cur.execute(
                    "UPDATE artistes SET status = 'out' WHERE id_spotify = %s",
                    (artist_id,),
                )
                n_artistes_out = cur.rowcount

                # 2) Esborra de 'cms_artists'
                cur.execute(
                    "DELETE FROM cms_artists WHERE id_spotify = %s", (artist_id,)
                )
                n_cms = cur.rowcount

                # 3) Esborra de 'spotify_artists'
                cur.execute("DELETE FROM spotify_artists WHERE id = %s", (artist_id,))
                n_sp = cur.rowcount

                conn.commit()
                bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"✅ Artista exclòs: {artist_id}\n· artistes→out: {n_artistes_out}\n· cms_artists esborrats: {n_\
cms}\n· spotify_artists esborrats: {n_sp}",
                )
                with open(LAST_ID_FILE, "w") as f:
                    f.write(str(update_id))
                continue

            except Exception as e:
                conn.rollback()
                logger(f"❌ Error en excloure artista {artist_id}: {e}")
                bot.send_message(
                    chat_id=CHAT_ID, text=f"❌ Error en excloure artista: {e}"
                )
                continue

        if album_id:
            try:
                # Esborra l'àlbum
                cur.execute("SELECT * FROM spotify_albums WHERE id = %s", (album_id,))
                album = cur.fetchone()
                if not album:
                    bot.send_message(
                        chat_id=CHAT_ID,
                        text=f"⚠️ L'àlbum {album_id} no està en la base de dades.",
                    )
                    continue

                cur.execute("DELETE FROM spotify_albums WHERE id = %s", (album_id,))
                logger(f"🗑️ Àlbum esborrat: {album['name']} ({album_id})")
                cur.execute(
                    """
                    INSERT INTO spotify_album_exclusions (album_id, name, reasons)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (album_id) DO NOTHING
                """,
                    (album_id, album["name"], ["Manual"]),
                )

                # Selecciona les seues cançons
                cur.execute(
                    "SELECT * FROM spotify_tracks WHERE album_id = %s", (album_id,)
                )
                tracks = cur.fetchall()

                if not tracks:
                    bot.send_message(
                        chat_id=CHAT_ID,
                        text=f"ℹ️ Àlbum {album['name']} ({album_id}) esborrat, però no tenia cap cançó.",
                    )
                    conn.commit()
                    continue

                n = 0
                for track in tracks:
                    isrc = track.get("external_ids", {}).get("isrc", "sense_isrc")
                    try:
                        artists = (
                            json.loads(track["artists"])
                            if isinstance(track["artists"], str)
                            else track["artists"]
                        )
                    except:
                        artists = []
                    artist_ids = [a["id"] for a in artists] if artists else []

                    cur.execute(
                        """
                        INSERT INTO spotify_exclusions (track_id, isrc, artist_ids, reasons)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (track_id, isrc) DO NOTHING
                    """,
                        (track["id"], isrc, artist_ids, ["Manual (àlbum)"]),
                    )

                    cur.execute(
                        "DELETE FROM spotify_tracks WHERE id = %s", (track["id"],)
                    )
                    cur.execute(
                        "DELETE FROM ranking_diari WHERE id_canco = %s", (track["id"],)
                    )
                    n += 1

                conn.commit()
                bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"✅ Àlbum esborrat i {n} cançons excloses: {album['name']}",
                )
                with open(LAST_ID_FILE, "w") as f:
                    f.write(str(update_id))
                continue

            except Exception as e:
                logger(f"❌ Error en excloure àlbum: {e}")
                bot.send_message(
                    chat_id=CHAT_ID, text=f"❌ Error en excloure àlbum: {e}"
                )
                continue

        if not track_id:
            bot.send_message(
                chat_id=CHAT_ID,
                text="⚠️ No he pogut detectar cap cançó de Spotify en el missatge.",
            )
            continue

        try:
            cur.execute("SELECT * FROM spotify_tracks WHERE id = %s", (track_id,))
            track = cur.fetchone()

            if not track:
                bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"⚠️ La cançó {track_id} no està en les cançons disponibles.",
                )
                continue

            # Agafa el primer artista si n'hi ha
            raw_artists = track.get("artists", [])
            try:
                artists = (
                    json.loads(raw_artists)
                    if isinstance(raw_artists, str)
                    else raw_artists
                )
                if not isinstance(artists, list):
                    artists = []
            except Exception as e:
                logger(f"⚠️ Error en parsejar 'artists': {e}")
                artists = []

            id_artista = artists[0]["id"] if artists else None
            nom_artista = artists[0]["name"] if artists else None

            # ⚠️ L'ISRC pot estar dins de track["external_ids"]["isrc"]
            isrc = track.get("external_ids", {}).get("isrc", "sense_isrc")

            # ⚠️ Recuperem tots els ID d'artistes
            artist_ids = [a["id"] for a in artists] if artists else []

            cur.execute(
                """
                INSERT INTO spotify_exclusions (
                    track_id, isrc, artist_ids, reasons
                ) VALUES (%s, %s, %s, %s)
            """,
                (track_id, isrc, artist_ids, ["Manual"]),
            )

            cur.execute("DELETE FROM spotify_tracks WHERE id = %s", (track_id,))
            cur.execute("DELETE FROM ranking_diari WHERE id_canco = %s", (track_id,))
            conn.commit()
            logger(
                f"✅ Cançó exclosa manualment: {track['name']} – {nom_artista} ({track_id})"
            )
            bot.send_message(
                chat_id=CHAT_ID,
                text=f"✅ Cançó exclosa i esborrada: {track['name']} – {nom_artista}",
            )

        except Exception as e:
            logger(f"❌ Error en excloure la cançó: {e}")
            bot.send_message(
                chat_id=CHAT_ID, text=f"❌ Error en excloure la cançó: {e}"
            )

        with open(LAST_ID_FILE, "w") as f:
            f.write(str(update_id))

finally:
    cur.close()
    conn.close()
