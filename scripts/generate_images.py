import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Afegim la carpeta arrel per poder importar utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.imatges import genera_imatge_top_bloc, genera_imatge_top_individual
from utils.logger import crear_logger

logger = crear_logger("logs/generate_images.log")

# 🔧 Carrega variables d'entorn
load_dotenv()

# 📦 Connexió a la base de dades
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT"),
)
cur = conn.cursor()

# 📆 Agafa la data més recent de la taula ranking_setmanal
cur.execute("SELECT MAX(data) FROM ranking_setmanal;")
data_base = cur.fetchone()[0]
data_str = data_base.strftime("%Y-%m-%d")
data_folder = f"outputs/Setmana{data_base.strftime('%Y%m%d')}"

territoris = ["pv", "cat", "ib"]


def carregar_ranking(territori):
    query = """
        SELECT posicio AS posicio_territori, titol, artistes, album_titol,
               score_setmanal, id_canco, artistes_ids, album_id,
               album_data, album_caratula_url, canvi_posicio
        FROM ranking_setmanal
        WHERE data = %s AND territori = %s
        ORDER BY posicio
    """
    cur.execute(query, (data_base, territori))
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    return pd.DataFrame(rows, columns=cols)


# 🖼️ Imatges per a cada territori
for territori in territoris:
    try:
        print(f"🎨 Iniciant territori: {territori}")
        # 🔁 tot el codi de generació de cada territori...
    except Exception as e:
        print(f"❌ Error en territori {territori}: {e}")

    territori_post_folder = os.path.join(data_folder, territori, "posts")
    territori_story_folder = os.path.join(data_folder, territori, "stories")
    os.makedirs(territori_post_folder, exist_ok=True)
    os.makedirs(territori_story_folder, exist_ok=True)
    df = carregar_ranking(territori)
    print(f"📊 {territori} – Cançons carregades: {len(df)}")
    if df.empty:
        print(f"⚠️ {territori} – Data {data_base} sense dades!")
        continue

    # 👇 AFEGIT: marca 'es_novetat' només si mai ha estat al top d'este territori abans
    cur.execute(
        """
        SELECT DISTINCT id_canco
        FROM ranking_setmanal
        WHERE territori = %s AND data < %s
    """,
        (territori, data_base),
    )
    ids_anteriors_territori = {r[0] for r in cur.fetchall()}

    df["es_novetat"] = df["canvi_posicio"].isna() & ~df["id_canco"].isin(
        ids_anteriors_territori
    )

    if df.empty:
        logger(f"⚠️ No s'han trobat dades per a {territori} a la data {data_str}")
        continue

    for ini, fi in [(31, 40), (21, 30), (11, 20), (1, 10)]:
        genera_imatge_top_bloc(
            df,
            ini,
            fi,
            label_data=data_base.strftime("%Y%m%d"),
            carpeta_sortida=territori_post_folder,
            territori=territori,
        )

    # 1. Portada → es genera automàticament si no existeix
    if not df.empty:
        fila_dummy = df.iloc[0].to_dict()
        genera_imatge_top_individual(
            fila_dummy, data_base.strftime("%Y%m%d"), territori_story_folder, territori
        )

        for pos in range(5, 0, -1):
            fila = df[df["posicio_territori"] == pos].iloc[0]
            genera_imatge_top_individual(
                fila.to_dict(),
                data_base.strftime("%Y%m%d"),
                territori_story_folder,
                territori,
            )

        genera_imatge_top_individual(
            fila_dummy, data_base.strftime("%Y%m%d"), territori_story_folder, territori
        )

        df_nous = df[df["es_novetat"]].sort_values("posicio_territori", ascending=True)
        for fila in df_nous.itertuples(index=False):
            genera_imatge_top_individual(
                fila._asdict(),
                data_base.strftime("%Y%m%d"),
                territori_story_folder,
                territori,
            )

    # 2-6. TOP 5 a TOP 1 → amb prefix 01_ a 05_
    for pos in range(5, 0, -1):
        fila = df[df["posicio_territori"] == pos].iloc[0]
        genera_imatge_top_individual(
            fila.to_dict(),
            data_base.strftime("%Y%m%d"),
            territori_story_folder,
            territori,
        )

    # 7. Forcem la còpia de la imatge "novetats" (es fa automàticament dins la funció)
    genera_imatge_top_individual(
        fila_dummy, data_base.strftime("%Y%m%d"), territori_story_folder, territori
    )

    # 8. Novetats → prefix 07_, 08_, ... en ordre ascendent
    df_nous = df[df["es_novetat"]].sort_values("posicio_territori", ascending=True)
    for fila in df_nous.itertuples(index=False):
        genera_imatge_top_individual(
            fila._asdict(),
            data_base.strftime("%Y%m%d"),
            territori_story_folder,
            territori,
        )

    # 9. La imatge "playlist" es copia automàticament

    logger(f"✅ Imatges generades a: {territori_post_folder}")
    logger(f"✅ Imatges generades a: {territori_story_folder}")


# 🧮 Top 40 general
cur.execute(
    """
    SELECT titol, artistes, album_titol, score_setmanal, id_canco,
           artistes_ids, album_id, album_data, album_caratula_url, score_global, canvi_posicio
    FROM ranking_setmanal
    WHERE data = %s
    ORDER BY score_global DESC
""",
    (data_base,),
)
rows = cur.fetchall()
cols = [desc[0] for desc in cur.description]
df_total = pd.DataFrame(rows, columns=cols)

df_total = df_total.drop_duplicates(subset="id_canco", keep="first").reset_index(
    drop=True
)
df_total = df_total.head(40).copy()
df_total["posicio_territori"] = range(1, len(df_total) + 1)

# 👇 AFEGIT: per al rànquing general, considera qualsevol aparició prèvia (sense filtrar territori)
cur.execute(
    """
    SELECT DISTINCT id_canco
    FROM ranking_setmanal
    WHERE data < %s
""",
    (data_base,),
)
ids_anteriors_global = {r[0] for r in cur.fetchall()}

df_total["es_novetat"] = df_total["canvi_posicio"].isna() & ~df_total["id_canco"].isin(
    ids_anteriors_global
)

ppcc_post_folder = os.path.join(data_folder, "ppcc", "posts")
ppcc_story_folder = os.path.join(data_folder, "ppcc", "stories")
os.makedirs(ppcc_post_folder, exist_ok=True)
os.makedirs(ppcc_story_folder, exist_ok=True)

# 🔍 Artista amb la pujada més gran al rànquing general
df_pujades = df_total[df_total["canvi_posicio"] > 0].copy()
df_pujades = df_pujades.sort_values("canvi_posicio", ascending=False)

imatge_fons = None
if not df_pujades.empty:
    imatge_fons = None
    if not df_pujades.empty:
        artistes_ids = df_pujades.iloc[0]["artistes_ids"]
        if artistes_ids and isinstance(artistes_ids, list):
            for artista_id in artistes_ids:
                cur.execute(
                    """
                    SELECT COALESCE(a.imatge_url, sa.images->0->>'url') AS imatge_url
                    FROM artistes a
                    LEFT JOIN spotify_artists sa ON sa.id = a.id_spotify
                    WHERE a.id_spotify = %s
                    LIMIT 1
                """,
                    (artista_id,),
                )
                fila = cur.fetchone()
                if fila and fila[0]:
                    imatge_fons = fila[0]
                    break

for ini, fi in [(31, 40), (21, 30), (11, 20), (1, 10)]:
    nprefix_bloc = {
        (1, 10): "01_bloc01-10",
        (11, 20): "02_bloc11-20",
        (21, 30): "03_bloc21-30",
        (31, 40): "04_bloc31-40",
    }.get((ini, fi), f"bloc{ini}-{fi}")

    genera_imatge_top_bloc(
        df_total,
        ini,
        fi,
        label_data=data_base.strftime("%Y%m%d"),
        carpeta_sortida=ppcc_post_folder,
        territori="ppcc",
    )

for pos in range(40, 0, -1):
    fila = df_total[df_total["posicio_territori"] == pos].iloc[0]
    genera_imatge_top_individual(
        fila, data_base.strftime("%Y%m%d"), ppcc_story_folder, territori="ppcc"
    )

logger(f"✅ Imatges generades a: {ppcc_post_folder}")
logger(f"✅ Imatges generades a: {ppcc_story_folder}")

# 🔚 Tancar connexió
cur.close()
conn.close()
logger("🏁 Generació d’imatges completada.")
