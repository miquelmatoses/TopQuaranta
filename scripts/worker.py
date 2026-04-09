import json
import os
import sys
import time
from datetime import datetime, timedelta

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

# 🛠️ Afig la ruta arrel al path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import crear_logger

log = crear_logger("logs/worker.log")

# 📥 Carrega variables d'entorn
load_dotenv()

# 🧠 Connexió PostgreSQL
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)
cur = conn.cursor(cursor_factory=RealDictCursor)

# 💤 Control de crides
sleep_base = 0.1

# 🔢 Comptadors globals per al resum final
total_tracks_actualitzats = 0
total_tracks_esborrats = 0
total_albums_afegits = 0
total_albums_esborrats = 0
total_artistes_actualitzats = 0


# 🔄 Sincronitzar artistes amb status 'go'
def sync_artistes_go():
    try:
        cur.execute(
            """
            SELECT id_spotify AS id, status
            FROM artistes
            WHERE status = 'go'
        """
        )
        artistes = cur.fetchall()

        afegits = 0
        actualitzats = 0
        for art in artistes:
            cur.execute(
                """
                INSERT INTO spotify_artists (id, status)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE
                SET status = EXCLUDED.status
                WHERE spotify_artists.status IS DISTINCT FROM EXCLUDED.status
            """,
                (art["id"], art["status"]),
            )
            if cur.rowcount == 1:
                actualitzats += 1

        conn.commit()

    except Exception as e:
        log(f"❌ Error sincronitzant artistes 'go': {e}")


def actualitzar_artistes_des_de_spotify():
    try:
        cur.execute(
            """
            UPDATE artistes a SET
                imatge_url = sa.images->0->>'url',
                popularitat = sa.popularity,
                followers = sa.followers_total,
                generes = array_to_string(sa.genres, ', '),
                nom_spotify = sa.name
            FROM spotify_artists sa
            WHERE a.id_spotify = sa.id
              AND (
                  a.imatge_url IS DISTINCT FROM sa.images->0->>'url' OR
                  a.popularitat IS DISTINCT FROM sa.popularity OR
                  a.followers IS DISTINCT FROM sa.followers_total OR
                  a.generes IS DISTINCT FROM array_to_string(sa.genres, ', ') OR
                  a.nom_spotify IS DISTINCT FROM sa.name
              )
        """
        )
        conn.commit()

    except Exception as e:
        log(f"❌ Error sincronitzant artistes → {e}")


def sync_cms_artists_into_artistes():
    """
    - Inserta en artistes els que estiguen en cms_artists i no existisquen (status='go').
    - Promociona a 'go' els que existixen en artistes però no estan en 'go'.
    - Actualitza en artistes els camps manuals quan en CMS NO estan buits.
    """
    try:
        # 1) Inserir nous artistes (source = CMS)
        cur.execute(
            """
            INSERT INTO artistes (
                id_spotify, nom, territori, comarca, localitat, id_viasona, bio, web, viquipedia,
                instagram, youtube, tiktok, soundcloud, bandcamp, deezer, bluesky, myspace, email, telefon, status
            )
            SELECT
                c.id_spotify, c.nom, c.territori, c.comarca, c.localitat, c.id_viasona, c.bio, c.web, c.viquipedia,
                c.instagram, c.youtube, c.tiktok, c.soundcloud, c.bandcamp, c.deezer, c.bluesky, c.myspace, c.email, c.t\
elefon,
                'go'
            FROM cms_artists c
            LEFT JOIN artistes a ON a.id_spotify = c.id_spotify
            WHERE a.id_spotify IS NULL
        """
        )
        inserides = cur.rowcount

        # 2) Estat segons CMS (publicat / proposat / rebutjat)

        # 2a) Publicat → 'go'
        cur.execute(
            """
            UPDATE artistes a
            SET status = 'go'
            FROM cms_artists c
            WHERE a.id_spotify = c.id_spotify
              AND c.live = TRUE
              AND a.status IS DISTINCT FROM 'go'
            """
        )
        go_promocionades = cur.rowcount

        # 2b) Proposat (no publicat) → 'ready' SI l'últim workflow NO està 'cancelled'
        cur.execute(
            """
            WITH ct AS (
              SELECT id AS content_type_id
              FROM django_content_type
              WHERE app_label = 'home' AND model = 'cmsartista'
            ),
            latest_ws AS (
              SELECT ws.object_id, ws.status
              FROM (
                SELECT ws.*,
                       ROW_NUMBER() OVER (PARTITION BY ws.object_id ORDER BY ws.created_at DESC) AS rn
                FROM wagtailcore_workflowstate ws
                JOIN ct ON ct.content_type_id = ws.content_type_id
              ) ws
              WHERE ws.rn = 1
            )
            UPDATE artistes a
            SET status = 'ready'
            FROM cms_artists c
            LEFT JOIN latest_ws lws ON lws.object_id = c.id_spotify
            WHERE a.id_spotify = c.id_spotify
              AND c.live = FALSE
              AND COALESCE(lws.status, 'in_progress') <> 'cancelled'
              AND a.status <> 'ready'
            """
        )
        ready_baixades = cur.rowcount

        # 2c) Rebutjat (últim workflow = 'cancelled') → 'out', només si NO hi ha versió live
        cur.execute(
            """
            WITH ct AS (
              SELECT id AS content_type_id
              FROM django_content_type
              WHERE app_label = 'home' AND model = 'cmsartista'
            ),
            latest_ws AS (
              SELECT sub.object_id, sub.status
              FROM (
                SELECT ws.object_id, ws.status, ws.created_at,
                       ROW_NUMBER() OVER (PARTITION BY ws.object_id ORDER BY ws.created_at DESC) AS rn
                FROM wagtailcore_workflowstate ws
                JOIN ct ON ct.content_type_id = ws.content_type_id
              ) sub
              WHERE sub.rn = 1
            )
            UPDATE artistes a
            SET status = 'out'
            FROM cms_artists c
            JOIN latest_ws lws ON lws.object_id = c.id_spotify
            WHERE a.id_spotify = c.id_spotify
              AND c.live = FALSE
              AND lws.status = 'cancelled'
              AND a.status IS DISTINCT FROM 'out'
            """
        )
        out_marcats = cur.rowcount


        # 3) Merge de camps manuals (NO buits en CMS ⇒ actualitzen artistes)
        cur.execute(
            """
            UPDATE artistes a
            SET
              nom        = COALESCE(NULLIF(TRIM(c.nom), ''),        a.nom),
              territori  = COALESCE(NULLIF(TRIM(c.territori), ''),  a.territori),
              comarca    = COALESCE(NULLIF(TRIM(c.comarca), ''),    a.comarca),
              localitat  = COALESCE(NULLIF(TRIM(c.localitat), ''),  a.localitat),
              id_viasona = COALESCE(NULLIF(TRIM(c.id_viasona), ''), a.id_viasona),
              bio        = COALESCE(NULLIF(TRIM(c.bio), ''),        a.bio),
              web        = COALESCE(NULLIF(TRIM(c.web), ''),        a.web),
              viquipedia = COALESCE(NULLIF(TRIM(c.viquipedia), ''), a.viquipedia),
              instagram  = COALESCE(NULLIF(TRIM(c.instagram), ''),  a.instagram),
              youtube    = COALESCE(NULLIF(TRIM(c.youtube), ''),    a.youtube),
              tiktok     = COALESCE(NULLIF(TRIM(c.tiktok), ''),     a.tiktok),
              soundcloud = COALESCE(NULLIF(TRIM(c.soundcloud), ''), a.soundcloud),
              bandcamp   = COALESCE(NULLIF(TRIM(c.bandcamp), ''),   a.bandcamp),
              deezer     = COALESCE(NULLIF(TRIM(c.deezer), ''),     a.deezer),
              bluesky    = COALESCE(NULLIF(TRIM(c.bluesky), ''),    a.bluesky),
              myspace    = COALESCE(NULLIF(TRIM(c.myspace), ''),    a.myspace),
              email      = COALESCE(NULLIF(TRIM(c.email), ''),      a.email),
              telefon    = COALESCE(NULLIF(TRIM(c.telefon), ''),    a.telefon)
            FROM cms_artists c
            WHERE a.id_spotify = c.id_spotify
              AND (
                a.nom        IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.nom), ''),        a.nom) OR
                a.territori  IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.territori), ''),  a.territori) OR
                a.comarca    IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.comarca), ''),    a.comarca) OR
                a.localitat  IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.localitat), ''),  a.localitat) OR
                a.id_viasona IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.id_viasona), ''), a.id_viasona) OR
                a.bio        IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.bio), ''),        a.bio) OR
                a.web        IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.web), ''),        a.web) OR
                a.viquipedia IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.viquipedia), ''), a.viquipedia) OR
                a.instagram  IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.instagram), ''),  a.instagram) OR
                a.youtube    IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.youtube), ''),    a.youtube) OR
                a.tiktok     IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.tiktok), ''),     a.tiktok) OR
                a.soundcloud IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.soundcloud), ''), a.soundcloud) OR
                a.bandcamp   IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.bandcamp), ''),   a.bandcamp) OR
                a.deezer     IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.deezer), ''),     a.deezer) OR
                a.bluesky    IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.bluesky), ''),    a.bluesky) OR
                a.myspace    IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.myspace), ''),    a.myspace) OR
                a.email      IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.email), ''),      a.email) OR
                a.telefon    IS DISTINCT FROM COALESCE(NULLIF(TRIM(c.telefon), ''),    a.telefon)
              )
        """
        )
        actualitzades = cur.rowcount

        conn.commit()
        log(
            f"✅ CMS→ARTISTES: inserides {inserides}, go→{go_promocionades}, ready→{ready_baixades}, out→{out_marcats}, a\
ctualitzades {actualitzades}"
        )
    except Exception as e:
        log(f"❌ Error en sync_cms_artists_into_artistes: {e}")
        conn.rollback()


def backfill_artistes_to_cms():
    """
    Backfill: si en CMS el camp està buit i en ARTISTES està ple, copiar cap a CMS.
    NO toca camps Spotify (es faran en una funció de mètriques separada).
    """
    try:
        cur.execute(
            """
            UPDATE cms_artists c
            SET
              nom        = CASE WHEN (c.nom IS NULL OR TRIM(c.nom)='') AND a.nom IS NOT NULL THEN a.nom ELSE c.nom END,
              territori  = CASE WHEN (c.territori IS NULL OR TRIM(c.territori)='') AND a.territori IS NOT NULL THEN a.te\
rritori ELSE c.territori END,
              comarca    = CASE WHEN (c.comarca IS NULL OR TRIM(c.comarca)='') AND a.comarca IS NOT NULL THEN a.comarca \
ELSE c.comarca END,
              localitat  = CASE WHEN (c.localitat IS NULL OR TRIM(c.localitat)='') AND a.localitat IS NOT NULL THEN a.lo\
calitat ELSE c.localitat END,
              id_viasona = CASE WHEN (c.id_viasona IS NULL OR TRIM(c.id_viasona)='') AND a.id_viasona IS NOT NULL THEN a\
.id_viasona ELSE c.id_viasona END,
              bio        = CASE WHEN (c.bio IS NULL OR TRIM(c.bio)='') AND a.bio IS NOT NULL THEN a.bio ELSE c.bio END,
              web        = CASE WHEN (c.web IS NULL OR TRIM(c.web)='') AND a.web IS NOT NULL THEN a.web ELSE c.web END,
              viquipedia = CASE WHEN (c.viquipedia IS NULL OR TRIM(c.viquipedia)='') AND a.viquipedia IS NOT NULL THEN a\
.viquipedia ELSE c.viquipedia END,
              instagram  = CASE WHEN (c.instagram IS NULL OR TRIM(c.instagram)='') AND a.instagram IS NOT NULL THEN a.in\
stagram ELSE c.instagram END,
              youtube    = CASE WHEN (c.youtube IS NULL OR TRIM(c.youtube)='') AND a.youtube IS NOT NULL THEN a.youtube \
ELSE c.youtube END,
              tiktok     = CASE WHEN (c.tiktok IS NULL OR TRIM(c.tiktok)='') AND a.tiktok IS NOT NULL THEN a.tiktok ELSE\
 c.tiktok END,
              soundcloud = CASE WHEN (c.soundcloud IS NULL OR TRIM(c.soundcloud)='') AND a.soundcloud IS NOT NULL THEN a\
.soundcloud ELSE c.soundcloud END,
              bandcamp   = CASE WHEN (c.bandcamp IS NULL OR TRIM(c.bandcamp)='') AND a.bandcamp IS NOT NULL THEN a.bandc\
amp ELSE c.bandcamp END,
              deezer     = CASE WHEN (c.deezer IS NULL OR TRIM(c.deezer)='') AND a.deezer IS NOT NULL THEN a.deezer ELSE\
 c.deezer END,
              bluesky    = CASE WHEN (c.bluesky IS NULL OR TRIM(c.bluesky)='') AND a.bluesky IS NOT NULL THEN a.bluesky \
ELSE c.bluesky END,
              myspace    = CASE WHEN (c.myspace IS NULL OR TRIM(c.myspace)='') AND a.myspace IS NOT NULL THEN a.myspace \
ELSE c.myspace END,
              email      = CASE WHEN (c.email IS NULL OR TRIM(c.email)='') AND a.email IS NOT NULL THEN a.email ELSE c.e\
mail END,
              telefon    = CASE WHEN (c.telefon IS NULL OR TRIM(c.telefon)='') AND a.telefon IS NOT NULL THEN a.telefon \
ELSE c.telefon END,
              updated_at = NOW()
            FROM artistes a
            WHERE a.id_spotify = c.id_spotify
              AND (
                ((c.nom IS NULL OR TRIM(c.nom)='') AND a.nom IS NOT NULL) OR
                ((c.territori IS NULL OR TRIM(c.territori)='') AND a.territori IS NOT NULL) OR
                ((c.comarca IS NULL OR TRIM(c.comarca)='') AND a.comarca IS NOT NULL) OR
                ((c.localitat IS NULL OR TRIM(c.localitat)='') AND a.localitat IS NOT NULL) OR
                ((c.id_viasona IS NULL OR TRIM(c.id_viasona)='') AND a.id_viasona IS NOT NULL) OR
                ((c.bio IS NULL OR TRIM(c.bio)='') AND a.bio IS NOT NULL) OR
                ((c.web IS NULL OR TRIM(c.web)='') AND a.web IS NOT NULL) OR
                ((c.viquipedia IS NULL OR TRIM(c.viquipedia)='') AND a.viquipedia IS NOT NULL) OR
                ((c.instagram IS NULL OR TRIM(c.instagram)='') AND a.instagram IS NOT NULL) OR
                ((c.youtube IS NULL OR TRIM(c.youtube)='') AND a.youtube IS NOT NULL) OR
                ((c.tiktok IS NULL OR TRIM(c.tiktok)='') AND a.tiktok IS NOT NULL) OR
                ((c.soundcloud IS NULL OR TRIM(c.soundcloud)='') AND a.soundcloud IS NOT NULL) OR
                ((c.bandcamp IS NULL OR TRIM(c.bandcamp)='') AND a.bandcamp IS NOT NULL) OR
                ((c.deezer IS NULL OR TRIM(c.deezer)='') AND a.deezer IS NOT NULL) OR
                ((c.bluesky IS NULL OR TRIM(c.bluesky)='') AND a.bluesky IS NOT NULL) OR
                ((c.myspace IS NULL OR TRIM(c.myspace)='') AND a.myspace IS NOT NULL) OR
                ((c.email IS NULL OR TRIM(c.email)='') AND a.email IS NOT NULL) OR
                ((c.telefon IS NULL OR TRIM(c.telefon)='') AND a.telefon IS NOT NULL)
              )
        """
        )
        backfilled = cur.rowcount
        conn.commit()
        log(f"✅ BACKFILL ARTISTES→CMS: {backfilled} camps emplenats")
    except Exception as e:
        log(f"❌ Error en backfill_artistes_to_cms: {e}")
        conn.rollback()


def push_spotify_metrics_to_cms():
    """
    Copia mètriques de spotify_artists cap a cms_artists (no manuals).
    """
    try:
        cur.execute(
            """
            UPDATE cms_artists c
            SET
              nom_spotify = sa.name,
              followers   = sa.followers_total,
              popularitat = sa.popularity,
              imatge_url  = sa.images->0->>'url',
              updated_at  = NOW()
            FROM spotify_artists sa
            WHERE sa.id = c.id_spotify
              AND (
                c.nom_spotify IS DISTINCT FROM sa.name OR
                c.followers   IS DISTINCT FROM sa.followers_total OR
                c.popularitat IS DISTINCT FROM sa.popularity OR
                c.imatge_url  IS DISTINCT FROM sa.images->0->>'url'
              )
        """
        )
        afectades = cur.rowcount
        conn.commit()
        log(f"✅ SPOTIFY→CMS: {afectades} files actualitzades")
    except Exception as e:
        log(f"❌ Error en push_spotify_metrics_to_cms: {e}")
        conn.rollback()

def enforce_cms_master_status():
    """
    CMS és la font de veritat: qualsevol artista que NO estiga a cms_artists
    passa a 'ready' en artistes i en spotify_artists.
    """
    try:
        # artistes: go -> ready si no és a CMS
        cur.execute(
            """
            UPDATE artistes a
               SET status = 'ready'
             WHERE a.status = 'go'
               AND NOT EXISTS (
                   SELECT 1 FROM cms_artists c
                   WHERE c.id_spotify = a.id_spotify
               )
            """
        )
        baixats_artistes = cur.rowcount

        # spotify_artists: go -> ready si no és a CMS
        cur.execute(
            """
            UPDATE spotify_artists sa
               SET status = 'ready'
             WHERE sa.status = 'go'
               AND NOT EXISTS (
                   SELECT 1 FROM cms_artists c
                   WHERE c.id_spotify = sa.id
               )
            """
        )
        baixats_spotify = cur.rowcount

        conn.commit()
        log(f"✅ CMS master: baixats a 'ready' — artistes:{baixats_artistes}, spotify_artists:{baixats_spotify}")
    except Exception as e:
        conn.rollback()
        log(f"❌ Error en enforce_cms_master_status: {e}")

def rebuild_cms_albums_from_spotify():
    """
    Reconstrueix completament CMS_ALBUMS des de SPOTIFY_ALBUMS.
    Esborra el contingut actual i el torna a omplir en cada execució.
    """
    try:
        # 1 i 2) Primer esborrem songs i albums (té FK a albums)
        cur.execute("TRUNCATE TABLE cms_songs, cms_albums")

        # 3) Inserim albums des de spotify_albums
        cur.execute(
            """
            INSERT INTO cms_albums (id, "name", album_type, release_date, image_url, artist_ids, artist_names, artist_na\
mes_str)
            SELECT
                sa.id,
                COALESCE(sa."name", ''),
                COALESCE(sa.album_type, ''),
                COALESCE(sa.release_date, ''),
                sa.images->0->>'url' AS image_url,
                art.artist_ids,
                art.artist_names,
                CASE WHEN art.artist_names IS NULL THEN NULL ELSE array_to_string(art.artist_names, ', ') END AS artist_\
names_str
            FROM spotify_albums sa
            LEFT JOIN LATERAL (
                SELECT
                    array_agg(a->>'id')   AS artist_ids,
                    array_agg(a->>'name') AS artist_names
                FROM jsonb_array_elements(sa.artists) a
            ) art ON TRUE
        """
        )
        afectades = cur.rowcount
        conn.commit()
        log(f"✅ CMS_ALBUMS reconstruït: {afectades} àlbums")
    except Exception as e:
        log(f"❌ Error en rebuild_cms_albums_from_spotify: {e}")
        conn.rollback()


def rebuild_cms_songs_from_spotify():
    """
    Reconstrueix completament CMS_SONGS des de SPOTIFY_TRACKS.
    Esborra el contingut actual i el torna a omplir en cada execució.
    Requereix que CMS_ALBUMS estiga ja omplida (FK).
    """
    try:
        # 1) Esborrem cançons
        cur.execute("TRUNCATE TABLE cms_songs")

        # 2) Inserim cançons des de spotify_tracks
        cur.execute(
            """
            INSERT INTO cms_songs (id, "name", popularity, isrc, artist_ids, artist_names, artist_names_str, album_id)
            SELECT
                st.id,
                COALESCE(st."name", ''),
                st.popularity,
                st.external_ids->>'isrc' AS isrc,
                art.artist_ids,
                art.artist_names,
                CASE WHEN art.artist_names IS NULL THEN NULL ELSE array_to_string(art.artist_names, ', ') END AS artist_\
names_str,
                st.album_id
            FROM spotify_tracks st
            LEFT JOIN LATERAL (
                SELECT
                    array_agg(a->>'id')   AS artist_ids,
                    array_agg(a->>'name') AS artist_names
                FROM jsonb_array_elements(st.artists) a
            ) art ON TRUE
            -- Garantim coherència referencial: només inserim si l'àlbum existeix a CMS
            JOIN cms_albums ca ON ca.id = st.album_id
        """
        )
        afectades = cur.rowcount
        conn.commit()
        log(f"✅ CMS_SONGS reconstruït: {afectades} cançons")
    except Exception as e:
        log(f"❌ Error en rebuild_cms_songs_from_spotify: {e}")
        conn.rollback()


def neteja_base_de_dades():

    # 🔸 Tracks en exclusions
    cur.execute(
        """
        DELETE FROM spotify_tracks
        WHERE id IN (
            SELECT track_id FROM spotify_exclusions
        )
    """
    )
    global total_tracks_esborrats
    total_tracks_esborrats += cur.rowcount

    # 🔸 Tracks massa antics
    cur.execute(
        """
        DELETE FROM spotify_tracks
        WHERE album_release_date IS NOT NULL
        AND TO_DATE(album_release_date, 'YYYY-MM-DD') < NOW() - INTERVAL '365 days'
    """
    )
    total_tracks_esborrats += cur.rowcount

    # 🔸 Àlbums massa antics (amb qualsevol date_updated)
    cur.execute(
        """
        DELETE FROM spotify_albums
        WHERE release_date IS NOT NULL
        AND (
            CASE 
                WHEN length(release_date) = 4 THEN TO_DATE(release_date || '-01-01', 'YYYY-MM-DD')
                WHEN length(release_date) = 7 THEN TO_DATE(release_date || '-01', 'YYYY-MM-DD')
                ELSE TO_DATE(release_date, 'YYYY-MM-DD')
            END
        ) < NOW() - INTERVAL '365 days'
    """
    )
    global total_albums_esborrats
    total_albums_esborrats += cur.rowcount

    # 🔸 Tracks sense cap artista en 'go' (cap coincidència amb artistes.status='go')
    cur.execute(
        """
        DELETE FROM spotify_tracks t
        WHERE NOT EXISTS (
            SELECT 1
            FROM jsonb_array_elements(COALESCE(t.artists::jsonb, '[]'::jsonb)) AS a(value)
            JOIN artistes ar
              ON ar.id_spotify = a.value->>'id'
             AND ar.status = 'go'
        )
        """
    )
    total_tracks_esborrats += cur.rowcount
    # 🔸 Tracks dels àlbums sense cap artista en 'go' (neteja d'orfenats)
    cur.execute(
        """
        DELETE FROM spotify_tracks st
        WHERE st.album_id IN (
            SELECT sa.id
            FROM spotify_albums sa
            WHERE NOT EXISTS (
                SELECT 1
                FROM jsonb_array_elements(COALESCE(sa.artists::jsonb, '[]'::jsonb)) AS a(value)
                JOIN artistes ar
                  ON ar.id_spotify = a.value->>'id'
                 AND ar.status = 'go'
            )
        )
        """
    )
    total_tracks_esborrats += cur.rowcount

    # 🔸 Àlbums sense cap artista en 'go'
    cur.execute(
        """
        DELETE FROM spotify_albums sa
        WHERE NOT EXISTS (
            SELECT 1
            FROM jsonb_array_elements(COALESCE(sa.artists::jsonb, '[]'::jsonb)) AS a(value)
            JOIN artistes ar
              ON ar.id_spotify = a.value->>'id'
             AND ar.status = 'go'
        )
        """
    )
    total_albums_esborrats += cur.rowcount

    conn.commit()


def formatar_nom(text):
    if not text:
        return ""
    excepcions = {
        "de",
        "del",
        "la",
        "el",
        "i",
        "les",
        "els",
        "lo",
        "en",
        "dels",
        "al",
        "als",
        "amb",
        "per",
        "contra",
        "segons",
        "us",
        "vos",
        "a",
        "o",
    }
    particules = ["l'", "d'", "m'", "s'", "n'", "t'"]
    paraules = text.split()
    resultat = []
    for i, p in enumerate(paraules):
        p_lower = p.lower()
        if any(p_lower.startswith(part) for part in particules):
            prefix = p_lower[:2]
            resta = p_lower[2:].capitalize()
            resultat.append(prefix + resta)
        elif i == 0 or p_lower not in excepcions:
            resultat.append(p.capitalize())
        else:
            resultat.append(p_lower)
    if resultat:
        resultat[0] = resultat[0][0].upper() + resultat[0][1:]
    return " ".join(resultat)


credencials = [
    ("SPOTIPY_CLIENT_ID_WORKER_A1", "SPOTIPY_CLIENT_SECRET_WORKER_A1"),
    ("SPOTIPY_CLIENT_ID_WORKER_B1", "SPOTIPY_CLIENT_SECRET_WORKER_B1"),
    ("SPOTIPY_CLIENT_ID_WORKER_C1", "SPOTIPY_CLIENT_SECRET_WORKER_C1"),
    ("SPOTIPY_CLIENT_ID_WORKER_D1", "SPOTIPY_CLIENT_SECRET_WORKER_D1"),
    ("SPOTIPY_CLIENT_ID_WORKER_E1", "SPOTIPY_CLIENT_SECRET_WORKER_E1"),
]
credencial_index = 0
credencials_estat = {}


def regenerar_token():
    global SPOTIFY_TOKEN, HEADERS, CLIENT_ID, CLIENT_SECRET, sleep_base, credencial_index

    while credencial_index < len(credencials):
        client_id_key, client_secret_key = credencials[credencial_index]
        CLIENT_ID = os.getenv(client_id_key)
        CLIENT_SECRET = os.getenv(client_secret_key)
        try:
            auth_response = requests.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(CLIENT_ID, CLIENT_SECRET),
                timeout=10,
            )
            auth_response.raise_for_status()
            SPOTIFY_TOKEN = auth_response.json()["access_token"]
            HEADERS = {"Authorization": f"Bearer {SPOTIFY_TOKEN}"}
            credencial = client_id_key.split("_")[-1]
            return True
        except Exception as e:
            credencial = client_id_key.split("_")[-1]
            credencials_estat[credencial] = "❌ Exception"
            log(f"❌ Error obtenint token amb {client_id_key}")
            sleep_base *= 1.5
            credencial_index += 1

    log("🔁 Totes les credencials han fallat — reiniciant amb A1")
    credencial_index = 0
    if regenerar_token():
        return spotify_safe_get(url, params)
    else:
        log("⛔ No s’ha pogut regenerar el token amb cap credencial")
        sys.exit(1)


# 🔁 Recuperar credencial anterior si existeix
try:
    with open("/tmp/spotify_credencial.txt", "r") as f:
        credencial_usada = f.read().strip()
        for i, (cid, _) in enumerate(credencials):
            if cid.endswith(credencial_usada):
                credencial_index = i
                log(f"🔁 Credencial recuperada: {credencial_usada}")
                break
except:
    credencial_index = 0
    log("🆕 Cap credencial guardada prèviament, començant per A1")

regenerar_token()

log("🚀 Inici del worker Spotify")


def spotify_safe_get(url, params=None):
    global sleep_base, credencial_index
    for i in range(credencial_index, len(credencials)):
        try:
            time.sleep(sleep_base)
            resp = requests.get(url, headers=HEADERS, params=params, timeout=(5, 10))

            if resp.status_code == 200:
                credencial = credencials[i][0].split("_")[-1]
                credencials_estat[credencial] = "✅ OK"
                return resp.json()

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 1))
                sleep_base *= 1.5
                if sleep_base > 6.0:
                    log(f"♻️ sleep_base supera 6.0 → reiniciem a 0.8")
                    sleep_base = 0.8
                credencial = credencials[i][0].split("_")[-1]
                temps = str(timedelta(seconds=retry_after))
                credencials_estat[credencial] = f"⚠️ 429 (retry_after: {temps})"
                log(
                    f"❗ 429 amb {credencials[i][0]} – Retry-After: {retry_after}s – sleep_base ara: {sleep_base:.2f}"
                )

                if retry_after <= 600:
                    log(f"⏳ Esperem {retry_after}s amb {credencials[i][0]}")
                    time.sleep(retry_after + 1)
                    continue
                else:
                    if i + 1 < len(credencials):
                        credencial_index = i + 1
                        log(
                            f"🔁 Supera 10 minuts → canviem a {credencials[credencial_index][0]}"
                        )
                        if not regenerar_token():
                            return None
                        continue
                    else:
                        log(
                            "🔁 Supera 10 minuts amb última credencial → tornem a començar per A1"
                        )
                        credencial_index = 0
                        if regenerar_token():
                            return spotify_safe_get(url, params)
                        else:
                            log(
                                "⛔ No s’ha pogut regenerar el token amb cap credencial"
                            )
                            sys.exit(1)

            elif resp.status_code in (401, 400):
                sleep_base *= 1.5
                credencial = credencials[i][0].split("_")[-1]
                credencials_estat[credencial] = f"❌ Error {resp.status_code}"
                log(
                    f"⚠️ Token invàlid amb {credencials[i][0]} ({resp.status_code}) – regenerem token i reintentem"
                )

                # Primer intentem renovar el token amb la mateixa credencial
                if not regenerar_token():
                    return None

                # Reintentem una vegada més amb la nova token
                time.sleep(sleep_base)
                resp = requests.get(url, headers=HEADERS, params=params)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 1))
                    sleep_base *= 1.5
                    log(
                        f"❗ 429 després de renovar token – Retry-After: {retry_after}s"
                    )
                    time.sleep(retry_after + 1)
                    continue

                elif resp.status_code in (401, 400):
                    # Ara sí, passem a la següent credencial
                    log(
                        f"❌ Nova token també invàlida amb {credencials[i][0]} – canviem de credencial"
                    )
                    credencial_index = i + 1
                    if credencial_index < len(credencials):
                        if not regenerar_token():
                            return None
                        continue
                    else:
                        log("⛔ Totes les credencials han fallat")
                        sys.exit(1)

                resp.raise_for_status()
                credencial = credencials[i][0].split("_")[-1]
                if f"✅ {credencial}" not in credencials_estat:
                    credencials_estat[credencial] = "✅ OK"
                return resp.json()

        except Exception as e:
            credencial = credencials[i][0].split("_")[-1]
            credencials_estat[credencial] = "❌ Exception"
            sleep_base *= 1.5  # 🔴 Qualsevol error → augmentem
            log(f"❌ Error inesperat amb {credencials[i][0]} a {url} → {e}")
            time.sleep(5)

    # 💡 Comprovem si s’han provat totes
    credencials_provades = set(c[0] for c in credencials[:credencial_index])
    credencials_restants = [
        i
        for i in range(len(credencials))
        if credencials[i][0] not in credencials_provades
    ]

    if credencials_restants:
        credencial_index = credencials_restants[0]
        log(
            f"🔁 Reintent amb credencials pendents: {', '.join(credencials[i][0] for i in credencials_restants)}"
        )
        if regenerar_token():
            return spotify_safe_get(url, params)

    log("⛔ Totes les credencials han fallat – aturant")
    sys.exit(1)


def actualitzar_tracks():
    cur.execute(
        """
        SELECT id, album_release_date FROM spotify_tracks
        WHERE 
            (date_updated IS NULL OR date_updated < NOW() - INTERVAL '2 days')
        ORDER BY date_updated NULLS FIRST
        LIMIT 1
    """
    )
    track = cur.fetchone()
    if not track:
        return False

    track_id = track["id"]
    release_date = track.get("album_release_date")

    # 🔎 Comprovar exclusions
    cur.execute(
        """
        SELECT 1 FROM spotify_exclusions
        WHERE track_id = %s OR isrc IN (
            SELECT external_ids->>'isrc'
            FROM spotify_tracks
            WHERE id = %s
        )
    """,
        (track_id, track_id),
    )
    if cur.fetchone():
        global total_tracks_esborrats
        total_tracks_esborrats += 1
        cur.execute("DELETE FROM spotify_tracks WHERE id = %s", (track_id,))
        conn.commit()
        return True

    # 🗓️ Comprovar si és massa antiga
    if release_date:
        try:
            parts = release_date.split("-")
            any_data = int(parts[0])
            mes_data = int(parts[1]) if len(parts) > 1 else 1
            dia_data = int(parts[2]) if len(parts) > 2 else 1
            data_track = datetime(any_data, mes_data, dia_data)
            if data_track < datetime.now() - timedelta(days=365):
                total_tracks_esborrats += 1
                cur.execute("DELETE FROM spotify_tracks WHERE id = %s", (track_id,))
                conn.commit()
                return True
        except Exception as e:
            log(f"⚠️ Error analitzant release_date de {track_id}: {e}")

    # 🧠 Crida a Spotify
    url = f"https://api.spotify.com/v1/tracks/{track_id}"
    dades = spotify_safe_get(url)

    if dades is False:
        log(f"⛔ Crida amb error greu per {track_id}")
        sys.exit(1)
    if not dades:
        log(f"⚠️ Crida sense dades per {track_id}")
        return True

    # 🧩 Prepara update complet
    update_fields = {
        "name": formatar_nom(dades.get("name")),
        "popularity": dades.get("popularity"),
        "duration_ms": dades.get("duration_ms"),
        "explicit": dades.get("explicit"),
        "is_local": dades.get("is_local"),
        "is_playable": dades.get("is_playable"),
        "disc_number": dades.get("disc_number"),
        "track_number": dades.get("track_number"),
        "preview_url": dades.get("preview_url"),
        "href": dades.get("href"),
        "uri": dades.get("uri"),
        "type": dades.get("type"),
        "external_ids": json.dumps(dades.get("external_ids", {})),
        "external_urls": json.dumps(dades.get("external_urls", {})),
        "available_markets": dades.get("available_markets"),
        "artists": json.dumps(dades.get("artists")),
        "album_id": dades["album"]["id"],
        "album_name": formatar_nom(dades["album"]["name"]),
        "album_release_date": dades["album"]["release_date"],
        "album_total_tracks": dades["album"].get("total_tracks"),
        "album_album_type": dades["album"].get("album_type"),
        "album_images": json.dumps(dades["album"].get("images", [])),
        "album_external_urls": json.dumps(dades["album"].get("external_urls", {})),
        "album_available_markets": dades["album"].get("available_markets"),
        "album_uri": dades["album"].get("uri"),
        "album_type": dades["album"].get("type"),
        "album_href": dades["album"].get("href"),
        "date_updated": datetime.now(),
    }

    set_exprs = ", ".join([f"{k} = %s" for k in update_fields])
    values = list(update_fields.values()) + [track_id]
    sql = f"UPDATE spotify_tracks SET {set_exprs} WHERE id = %s"
    cur.execute(sql, values)
    conn.commit()
    global total_tracks_actualitzats
    total_tracks_actualitzats += 1
    return True


def actualitzar_albums_tracks():

    # 🔁 Esborrar albums massa antics
    cur.execute(
        """
        DELETE FROM spotify_albums
        WHERE 
            release_date IS NOT NULL
            AND release_date ~ '^\d{4}' -- assegurem que és parsable
            AND (
                CASE 
                    WHEN length(release_date) = 4 THEN TO_DATE(release_date || '-01-01', 'YYYY-MM-DD')
                    WHEN length(release_date) = 7 THEN TO_DATE(release_date || '-01', 'YYYY-MM-DD')
                    ELSE TO_DATE(release_date, 'YYYY-MM-DD')
                END
            ) < NOW() - INTERVAL '365 days'
            AND date_updated IS NULL
    """
    )
    conn.commit()

    # 🔍 Buscar àlbum pendent
    cur.execute(
        """
        SELECT id FROM spotify_albums
        WHERE date_updated IS NULL
        ORDER BY release_date DESC
        LIMIT 1
    """
    )
    album = cur.fetchone()
    if not album:
        return False  # Passar a la següent fase

    album_id = album["id"]

    # 🔗 Crida a Spotify
    url = f"https://api.spotify.com/v1/albums/{album_id}/tracks"
    dades = spotify_safe_get(url)
    if dades is False:
        sys.exit(1)
    if not dades or "items" not in dades:
        log(f"⚠️ Error obtenint pistes de l'àlbum {album_id}")
        return True

    # 🎼 Processar cada cançó
    for pista in dades["items"]:
        try:
            insert_fields = {
                "id": pista["id"],
                "name": formatar_nom(pista["name"]),
                "duration_ms": pista["duration_ms"],
                "explicit": pista.get("explicit"),
                "disc_number": pista.get("disc_number"),
                "track_number": pista.get("track_number"),
                "preview_url": pista.get("preview_url"),
                "href": pista.get("href"),
                "uri": pista.get("uri"),
                "type": pista.get("type"),
                "artists": json.dumps(pista.get("artists", [])),
                "album_id": album_id,
                "date_updated": None,
            }

            cols = ", ".join(insert_fields.keys())
            vals = ", ".join(["%s"] * len(insert_fields))
            sql = f"INSERT INTO spotify_tracks ({cols}) VALUES ({vals}) ON CONFLICT DO NOTHING"
            cur.execute(sql, list(insert_fields.values()))
            global total_tracks_actualitzats
            total_tracks_actualitzats += 1
        except Exception as e:
            log(f"⚠️ Error afegint pista {pista.get('id')} → {e}")

    # 🕒 Marcar àlbum com actualitzat
    cur.execute(
        """
        UPDATE spotify_albums SET date_updated = NOW() WHERE id = %s
    """,
        (album_id,),
    )
    conn.commit()

    return True


def actualitzar_artistes_albums():

    # 🔍 Buscar artista pendent
    cur.execute(
        """
        SELECT id FROM spotify_artists
        WHERE status = 'go'
        AND (date_updated_albums IS NULL OR date_updated_albums < CURRENT_DATE)
        ORDER BY popularity DESC
        LIMIT 1
    """
    )
    artista = cur.fetchone()
    if not artista:
        return False

    artist_id = artista["id"]
    url = f"https://api.spotify.com/v1/artists/{artist_id}/albums"
    params = {
        "include_groups": "album,single",  # Excloem compilacions i apareix en...
        "limit": 50,
        "market": "ES",
    }

    dades = spotify_safe_get(url, params)
    if dades is False:
        sys.exit(1)
    if not dades or "items" not in dades:
        log(f"⚠️ Error obtenint àlbums per a {artist_id}")
        return True

    afegits = 0
    for album in dades["items"]:
        try:
            album_id = album.get("id")
            if not album_id:
                continue

            # ❌ Comprova si l'àlbum està exclòs
            cur.execute(
                "SELECT 1 FROM spotify_album_exclusions WHERE album_id = %s",
                (album_id,),
            )
            if cur.fetchone():
                log(f"🚫 Àlbum exclòs: {album_id} ({album.get('name')}) – omés")
                continue
            # 🗓️ Saltar si és massa antic
            rd = album.get("release_date")
            if not rd:
                continue
            parts = rd.split("-")
            any_, mes, dia = int(parts[0]), 1, 1
            if len(parts) > 1:
                mes = int(parts[1])
            if len(parts) > 2:
                dia = int(parts[2])
            data_album = datetime(any_, mes, dia)
            if data_album < datetime.now() - timedelta(days=365):
                continue

            insert_fields = {
                "id": album["id"],
                "name": formatar_nom(album["name"]),
                "album_type": album["album_type"],
                "total_tracks": album.get("total_tracks"),
                "release_date": album["release_date"],
                "release_date_precision": album.get("release_date_precision"),
                "uri": album["uri"],
                "href": album["href"],
                "type": album["type"],
                "external_urls": json.dumps(album.get("external_urls", {})),
                "available_markets": album.get("available_markets"),
                "images": json.dumps(album.get("images", [])),
                "artists": json.dumps(album.get("artists", [])),
                "date_updated": None,
            }

            cols = ", ".join(insert_fields.keys())
            vals = ", ".join(["%s"] * len(insert_fields))
            sql = f"INSERT INTO spotify_albums ({cols}) VALUES ({vals}) ON CONFLICT DO NOTHING"
            cur.execute(sql, list(insert_fields.values()))
            afegits += 1
            global total_albums_afegits
            total_albums_afegits += 1

        except Exception as e:
            log(f"⚠️ Error afegint àlbum → {e}")

    # 🔁 Actualitzar artista
    cur.execute(
        "UPDATE spotify_artists SET date_updated_albums = CURRENT_DATE WHERE id = %s",
        (artist_id,),
    )
    conn.commit()

    return True


def actualitzar_artistes_info():
    # 🔍 Seleccionar artistes a actualitzar
    cur.execute(
        """
        SELECT id FROM spotify_artists
        WHERE status = 'go'
        AND (date_updated IS NULL OR date_updated < NOW() - INTERVAL '1 day')
        ORDER BY date_updated ASC NULLS FIRST
        LIMIT 50
    """
    )
    files = cur.fetchall()
    if not files:
        return False

    artist_ids = [f["id"] for f in files]
    ids_str = ",".join(artist_ids)
    url = "https://api.spotify.com/v1/artists"
    params = {"ids": ids_str}
    dades = spotify_safe_get(url, params)

    if dades is False:
        sys.exit(1)
    if not dades or "artists" not in dades:
        log(f"⚠️ Error obtenint dades per a artistes {artist_ids}")
        return True

    ids_retornats = [a.get("id") for a in dades["artists"] if a.get("id")]
    ids_demanats = set(artist_ids)

    if not ids_demanats.intersection(ids_retornats):
        log(f"❗ Cap dels IDs retornats coincideix literalment amb els demanats.")
        log(
            "🧪 Intentarem fer el matching dins el bucle artista per si han canviat els IDs."
        )

    if not dades["artists"]:
        log(
            f"⚠️ Spotify ha retornat una llista buida per artistes {artist_ids} – marquem com a finalitzat"
        )
        return False

    for artista in dades["artists"]:
        id_api = artista["id"]
        id_original = (
            id_api
            if id_api in artist_ids
            else next(
                (
                    i
                    for i in artist_ids
                    if artista.get("name", "").lower() in i.lower()
                    or artista.get("uri", "").endswith(i)
                ),
                None,
            )
        )

        if not id_original:
            log(
                f"❗ ID {id_api} no estava entre els demanats i no s’ha pogut identificar amb nom/uri"
            )
            continue

        if id_api != id_original:
            log(f"🔁 ID canviat per Spotify: {id_original} → {id_api}")
            try:
                # Comprovem si ja existix en 'artistes'
                cur.execute(
                    "SELECT status FROM artistes WHERE id_spotify = %s", (id_api,)
                )
                resultat = cur.fetchone()

                if resultat:
                    if resultat["status"] != "go":
                        cur.execute(
                            "UPDATE artistes SET status = 'go' WHERE id_spotify = %s",
                            (id_api,),
                        )
                        log(
                            f"✅ Canviat status a 'go' per artista existent amb id {id_api}"
                        )
                    else:
                        log(
                            f"ℹ️ El nou ID {id_api} ja existia amb status 'go'. No s’ha fet cap canvi a 'artistes'."
                        )
                else:
                    # Actualitzem id a spotify_artists i artistes
                    cur.execute(
                        "UPDATE spotify_artists SET id = %s WHERE id = %s",
                        (id_api, id_original),
                    )
                    cur.execute(
                        "UPDATE artistes SET id_spotify = %s WHERE id_spotify = %s",
                        (id_api, id_original),
                    )
                    cur.execute(
                        "UPDATE cms_artists SET id_spotify = %s WHERE id_spotify = %s",
                        (id_api, id_original),
                    )
                    log(
                        f"✅ Substituït ID {id_original} per {id_api} en les tres taules"
                    )
                conn.commit()
            except Exception as e:
                log(f"⚠️ Error actualitzant ID {id_original} → {id_api}: {e}")
                continue

        try:
            update_fields = {
                "name": formatar_nom(artista["name"]),
                "popularity": artista.get("popularity"),
                "followers_total": artista.get("followers", {}).get("total"),
                "genres": artista.get("genres", []),
                "uri": artista.get("uri"),
                "href": artista.get("href"),
                "type": artista.get("type"),
                "external_urls": json.dumps(artista.get("external_urls", {})),
                "images": json.dumps(artista.get("images", [])),
                "date_updated": datetime.now(),
            }
            set_exprs = ", ".join([f"{k} = %s" for k in update_fields])
            values = list(update_fields.values()) + [id_api]
            sql = f"UPDATE spotify_artists SET {set_exprs} WHERE id = %s"
            cur.execute(sql, values)
        except Exception as e:
            log(f"⚠️ Error actualitzant artista {id_api} → {e}")

    conn.commit()
    if dades["artists"]:
        global total_artistes_actualitzats
        total_artistes_actualitzats += len(dades["artists"])
    return True


# 🛑 Intercepta SIGTERM per capturar el timeout i executar el finally
import signal


def handler_sigterm(signum, frame):
    raise KeyboardInterrupt("⏹️ SIGTERM rebut – Timeout o finalització manual")


signal.signal(signal.SIGTERM, handler_sigterm)

if __name__ == "__main__":
    try:
        # 🔁 Recuperar sleep_base anterior si existeix
        try:
            with open("/tmp/spotify_sleep_base.txt", "r") as f:
                sleep_base = float(f.read().strip())
                sleep_base_inicial = sleep_base
                log(f"🔁 sleep_base recuperat: {sleep_base:.2f}")
        except:
            sleep_base = 0.5
            log(f"🆕 sleep_base inicialitzat: {sleep_base:.2f}")

        # 1) CMS ⇒ ARTISTES (inserir/promocionar/merge)
        sync_cms_artists_into_artistes()

        # 2) BACKFILL ARTISTES ⇒ CMS (ompli buits, no inserta nous)
        backfill_artistes_to_cms()

        # 3) CMS mana: baixa a 'ready' tot el que NO estiga a CMS (abans de netejar)
        enforce_cms_master_status()

        # 4) ARTISTES (go) ⇒ SPOTIFY_ARTISTS
        sync_artistes_go()

        # 5) Neteja (ara que els estats ja estan actualitzats)
        neteja_base_de_dades()

        # SPOTIFY ⇒ ARTISTES i ⇒ CMS (mètriques)
        actualitzar_artistes_des_de_spotify()
        push_spotify_metrics_to_cms()

        while True:
            if actualitzar_tracks():
                continue
            if actualitzar_albums_tracks():
                continue
            if actualitzar_artistes_albums():
                continue
            break  # cap fase ha retornat feina nova → finalitza

        # 🔄 Finalment, actualitzem informació dels artistes (una vegada)
        while actualitzar_artistes_info():
            pass

        # 🧱 Reconstrucció completa de col·leccions CMS a partir de Spotify
        neteja_base_de_dades()
        #   - Primer àlbums (per la FK)
        rebuild_cms_albums_from_spotify()
        #   - Després cançons
        rebuild_cms_songs_from_spotify()

    except Exception as e:
        log(f"💥 Error global: {e}")

    finally:
        resum_línies = []

        if total_tracks_actualitzats:
            resum_línies.append(f"· {total_tracks_actualitzats} tracks actualitzats")
        if total_tracks_esborrats:
            resum_línies.append(f"· {total_tracks_esborrats} tracks esborrats")
        if total_albums_afegits:
            resum_línies.append(f"· {total_albums_afegits} àlbums afegits")
        if total_albums_esborrats:
            resum_línies.append(f"· {total_albums_esborrats} àlbums esborrats")
        if total_artistes_actualitzats:
            resum_línies.append(
                f"· {total_artistes_actualitzats} artistes actualitzats"
            )

        if resum_línies:
            log("📊 Resum final:\n" + "\n".join(f"   {l}" for l in resum_línies))
        else:
            log("📊 Cap actualització feta.")
        if credencials_estat:
            log(
                "🧾 Estat credencials:\n"
                + "\n".join(f"   · {k}: {v}" for k, v in credencials_estat.items())
            )

        # 💾 Guardar sleep_base només si ha canviat
        try:
            if sleep_base != sleep_base_inicial:
                with open("/tmp/spotify_sleep_base.txt", "w") as f:
                    f.write(str(sleep_base))
                log(f"💤 sleep_base guardat: {sleep_base:.2f}")
        except Exception as e:
            log(f"⚠️ No s'ha pogut guardar sleep_base: {e}")

        # 💾 Guardar credencial usada
        try:
            credencial_actual = credencials[credencial_index][0].split("_")[-1]
            with open("/tmp/spotify_credencial.txt", "w") as f:
                f.write(credencial_actual)
        except Exception as e:
            log(f"⚠️ No s'ha pogut guardar la credencial usada: {e}")

        if cur:
            cur.close()
        if conn:
            conn.close()
