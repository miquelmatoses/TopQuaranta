import os
import sys
from collections import Counter
from datetime import date

import psycopg2

# 🧱 Inicialització
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import crear_logger

logger = crear_logger("logs/genera_post_instagram.log")

today = date.today()

territoris = ["pv", "cat", "ib", "general"]
territori_textos = {
    "pv": "del País Valencià",
    "cat": "de Catalunya",
    "ib": "de les Illes Balears",
    "general": "en català",
}

# 🔌 Connexió a la base de dades
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
)
cur = conn.cursor()

# 🔁 Generació de post per cada territori
for territori in territoris:
    logger(f"🛠️ Generant post per al territori: {territori}")
    label_data = today.strftime("%Y%m%d")

    # 🔍 Carrega el top 40 des de la vista del territori
    if territori == "general":
        cur.execute(
            """
            SELECT titol, artistes, album_titol, album_data, artistes_ids
            FROM vw_top40_weekly_ppcc
            ORDER BY posicio ASC
            LIMIT 40
        """
        )
        top40 = cur.fetchall()
        top_lines = []
        for i, (titol, artistes, album_titol, album_data, artistes_ids) in enumerate(
            top40, 1
        ):
            extra = []
            if album_data and (today - album_data).days <= 30:
                extra.append("acabat d’eixir del forn! 🎉")
            artistes_str = ", ".join(artistes)
            artista_principal = artistes[0].strip() if artistes else ""
            detall = " ".join(extra)
            top_lines.append(
                f"{i}. {artistes_str} - {titol} ({artista_principal} és l’artista principal) {detall}".strip()
            )

    else:
        vista = f"vw_top40_weekly_{territori}"
        cur.execute(
            f"""
            SELECT posicio, titol, artistes, album_titol, album_data,
                   artistes_ids, posicio_anterior
            FROM {vista}
            ORDER BY posicio ASC
            LIMIT 40
        """
        )
        top40 = cur.fetchall()
        top_lines = []
        for (
            pos,
            titol,
            artistes,
            album_titol,
            album_data,
            artistes_ids,
            posicio_anterior,
        ) in top40:
            extra = []
            if album_data and (today - album_data).days <= 30:
                extra.append("acabat d’eixir del forn! 🎉")
            if posicio_anterior is None:
                extra.append("nova entrada 🆕")
            elif pos == 1 and posicio_anterior == 1:
                extra.append("continua al número 1! 🔥")
            elif posicio_anterior is None:
                extra.append(f"ha pujat esta setmana ⬆️ (41→{pos})")
            elif posicio_anterior > pos:
                extra.append(f"ha pujat esta setmana ⬆️ ({posicio_anterior}→{pos})")
            artistes_str = ", ".join(artistes)
            artista_principal = artistes[0].strip() if artistes else ""
            detall = " ".join(extra)
            top_lines.append(f"{pos}. {artistes_str} - {titol} {detall}".strip())

    # 📝 Construcció del post
    línies = [f"🎧 Esta setmana al #Top40 {territori_textos[territori]}!\n"]

    línies.append("🔥 El Top 5:")
    línies.extend(top_lines[:5])
    línies.append("")

    novetats = [l for l in top_lines if "nova entrada" in l]
    if novetats:
        línies.append("🆕 Novetats destacades:")
        for l in novetats[:3]:
            try:
                posicio = l.split(".")[0].strip()
                resum = l.split(". ", 1)[1]
                línies.append(f"- Entra directament al {posicio}: {resum}")
            except IndexError:
                línies.append(f"- {l}")
        línies.append("")

    # 🔍 Calcula pujada més forta (incloent novetats com si vingueren del 41)
    pujada_mes_forta = None
    max_pujada = 0
    for l in top_lines:
        try:
            posicio = int(l.split(".")[0])
            if "nova entrada" in l:
                pujada = 41 - posicio
            elif "ha pujat esta setmana" in l:
                anterior = int(l.split("⬆️")[1].split("(")[1].split("→")[0].strip())
                pujada = anterior - posicio
            else:
                continue
            if pujada > max_pujada:
                max_pujada = pujada
                pujada_mes_forta = l
        except Exception as e:
            continue

    if pujada_mes_forta:
        línies.append("⬆️ Pujada més forta:")
        línies.append(f"- {pujada_mes_forta.split('. ', 1)[1]}")
        línies.append("")

    # Extrau tots els artistes de cada línia (després del número i abans del " - ")
    artistes_totals = []
    for l in top_lines:
        try:
            artistes_str = l.split(" - ")[0].split(". ", 1)[1]
            artistes_totals.extend(a.strip() for a in artistes_str.split(","))
        except IndexError:
            continue

    comptador = Counter(artistes_totals)
    if comptador:
        artista_top, num = comptador.most_common(1)[0]
        if num > 1:
            línies.append(
                f"🔁 L’artista amb més cançons: {artista_top} ({num} cançons al rànquing)"
            )
            línies.append("")

    curiositats = [l for l in top_lines if "emergent" in l or "primer àlbum" in l]
    if curiositats:
        línies.append("✨ Curiositats:")
        línies.extend(f"- {l.split('. ', 1)[1]}" for l in curiositats[:2])
        línies.append("")

    línies.append("🔗 Escolta’l sencer: enllaç a la bio")
    post_instagram = "\n".join(línies)

    # 💾 Guarda el post
    img_territori = "ppcc" if territori == "general" else territori
    folder_path = os.path.join("outputs", f"Setmana{label_data}", img_territori)
    os.makedirs(folder_path, exist_ok=True)
    post_path = os.path.join(
        folder_path, f"post_instagram_{img_territori}_{label_data}.txt"
    )

    with open(post_path, "w", encoding="utf-8") as f:
        f.write(post_instagram)

    logger(f"✅ Post generat i guardat: {post_path}")

# 🔚 Finalització
cur.close()
conn.close()
logger("🏁 Generació completada per a tots els territoris.")
