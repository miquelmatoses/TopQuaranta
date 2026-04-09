import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv
from telegram import Bot
from telegram.utils.request import Request

# 🔧 Accés a utils/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import crear_logger

logger = crear_logger("logs/envia_post_telegram.log")
load_dotenv()
telegram_token = os.getenv("TELEGRAM_TOKEN")
telegram_chat_id = int(os.getenv("TELEGRAM_CHAT_ID"))
bot = Bot(token=telegram_token, request=Request(con_pool_size=8))


# 🗓️ Calcula dissabte més recent (hui si és dissabte)
def dissabte_mes_recent(ref: date) -> date:
    return (
        ref
        if ref.weekday() == 5
        else ref - timedelta(days=(ref.weekday() - 5) % 7 or 7)
    )


# 📥 Argument: territori [+ data opcional]
if len(sys.argv) not in [2, 3]:
    logger("❌ Ús: python envia_telegram_post.py <territori> [data_YYYYMMDD]")
    sys.exit(1)

territori = sys.argv[1].lower()
if territori not in ["pv", "cat", "ib", "illes", "general", "albums", "singles"]:
    logger("❌ Territori no vàlid. Usa: pv, cat, ib, illes, general, albums, singles")
    sys.exit(1)

if len(sys.argv) == 3:
    label_data = sys.argv[2]
else:
    label_data = dissabte_mes_recent(date.today()).strftime("%Y%m%d")

# 📂 Ruta del contingut
img_territori = "ppcc" if territori == "general" else territori
folder_path = os.path.join("outputs", f"Setmana{label_data}", img_territori)
post_path = os.path.join(
    folder_path, f"post_instagram_{img_territori}_{label_data}.txt"
)

if os.path.exists(post_path):
    with open(post_path, "r", encoding="utf-8") as f:
        missatge = f.read()
    logger(f"📤 Enviant post del territori '{territori}' per a la setmana {label_data}")
    bot.send_message(chat_id=telegram_chat_id, text=missatge)
else:
    logger(f"⚠️ No s’ha trobat el fitxer de text: {post_path} — s’envien només imatges.")

# 🖼️ Enviar imatges, primer provem 'posts/' i 'stories/', si no, directament del folder principal
imatges_enviades = 0
carpetes_buscar = []

for subcarpeta in ["posts", "stories"]:
    sub_path = os.path.join(folder_path, subcarpeta)
    if os.path.exists(sub_path):
        carpetes_buscar.append(sub_path)

# Si no hi ha cap subcarpeta, busca en el folder principal
if not carpetes_buscar:
    carpetes_buscar.append(folder_path)

for carpeta in carpetes_buscar:
    for nom in sorted(os.listdir(carpeta)):
        if nom.endswith(".png") and not nom.startswith("Poster"):
            ruta = os.path.join(carpeta, nom)
            with open(ruta, "rb") as img:
                bot.send_photo(chat_id=telegram_chat_id, photo=img)
            imatges_enviades += 1

logger(f"📦 Total imatges enviades: {imatges_enviades}")
