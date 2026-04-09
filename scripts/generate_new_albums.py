import os
import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv

warnings.filterwarnings(
    "ignore", category=UserWarning, message="pandas only supports SQLAlchemy"
)

# 🔧 Variables d'entorn
load_dotenv()

# 📁 Ruta arrel per a importar utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.imatges import (
    genera_imatge_album_individual,
    genera_imatge_portada_albums,
)
from utils.logger import crear_logger

logger = crear_logger("logs/generate_nous_àlbums.log")

# 📦 Connexió
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)
cur = conn.cursor()

# 📂 Carpeta d’eixida
hui = date.today()
data_base = hui - timedelta(days=(hui.weekday() - 5) % 7)
data_str = data_base.strftime("%Y%m%d")
carpeta_sortida = f"outputs/Setmana{data_str}/albums"
Path(carpeta_sortida).mkdir(parents=True, exist_ok=True)

# 📄 Carrega dades
query = "SELECT * FROM vw_albums_recents ORDER BY release_date DESC"
df_albums_all = pd.read_sql(query, conn)

# 🎯 Filtrar àlbums només
df_albums = df_albums_all[df_albums_all["album_type"] != "single"].copy()

if df_albums.empty:
    logger("⚠️ No s’han trobat nous àlbums.")
    print("⚠️ No s’han trobat nous àlbums.")
    sys.exit(0)

logger(f"📦 {len(df_albums)} nous àlbums trobats.")

# 🖼️ Portada
genera_imatge_portada_albums(df_albums, carpeta_sortida)

# 🖼️ Àlbums llargs
df_llargs = df_albums[df_albums["album_type"] == "album"].copy()
for i, fila in enumerate(df_llargs.to_dict(orient="records"), start=1):
    genera_imatge_album_individual(fila, carpeta_sortida, i)

logger("✅ Generació de nous àlbums completada.")
