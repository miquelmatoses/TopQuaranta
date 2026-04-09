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
    genera_imatge_bloc_singles,
    genera_imatge_portada_albums,
)
from utils.logger import crear_logger

logger = crear_logger("logs/generate_nous_singles.log")

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
carpeta_sortida = f"outputs/Setmana{data_str}/singles"
Path(carpeta_sortida).mkdir(parents=True, exist_ok=True)

# 📄 Carrega dades
query = "SELECT * FROM vw_albums_recents ORDER BY release_date DESC"
df_albums = pd.read_sql(query, conn)

# 🎯 Filtrar singles només
df_singles = df_albums[df_albums["album_type"] == "single"].copy()

if df_singles.empty:
    logger("⚠️ No s’han trobat nous singles.")
    print("⚠️ No s’han trobat nous singles.")
    sys.exit(0)

logger(f"📦 {len(df_singles)} nous singles trobats.")

# 🖼️ Portada
genera_imatge_portada_albums(df_singles, carpeta_sortida)

# 🖼️ Bloc de singles
genera_imatge_bloc_singles(df_singles, carpeta_sortida, idx_inicial=1)

logger("✅ Generació de nous singles completada.")
