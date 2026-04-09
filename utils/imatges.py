import os
import warnings
from io import BytesIO

import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageFont

warnings.filterwarnings(
    "ignore", category=UserWarning, message="pandas only supports SQLAlchemy"
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 🎨 Configuració visual
fonts_top40 = {
    "regular": os.path.join(BASE_DIR, "assets/fonts/Regular.ttf"),
    "bold": os.path.join(BASE_DIR, "assets/fonts/Bold.ttf"),
    "heavy": os.path.join(BASE_DIR, "assets/fonts/Heavy.ttf"),
}
PALETES = {
    "pv": {
        "primary_100": "#fe9284",
        "primary_200": "#fe6350",
        "primary_300": "#b24538",
        "accent_100": "#50ebfe",
        "accent_200": "#fe5094",
        "text_100": "#ffffff",
        "text_200": "#cccccc",
        "bg_100": "#1c163d",
        "bg_200": "#494564",
        "bg_300": "#140f2b",
    },
    "cat": {
        "primary_100": "#fcd47d",
        "primary_200": "#fbc145",
        "primary_300": "#b08730",
        "accent_100": "#457ffb",
        "accent_200": "#fb6645",
        "text_100": "#ffffff",
        "text_200": "#cccccc",
        "bg_100": "#1c163d",
        "bg_200": "#494564",
        "bg_300": "#140f2b",
    },
    "ib": {
        "primary_100": "#5fbccd",
        "primary_200": "#1b9fb7",
        "primary_300": "#136f80",
        "accent_100": "#ff4726",
        "accent_200": "#1bb781",
        "text_100": "#ffffff",
        "text_200": "#cccccc",
        "bg_100": "#1c163d",
        "bg_200": "#494564",
        "bg_300": "#140f2b",
    },
    "ppcc": {
        "primary_100": "#fcd47d",
        "primary_200": "#fbc145",
        "primary_300": "#b08730",
        "accent_100": "#fe6350",
        "accent_200": "#1b9fb7",
        "text_100": "#ffffff",
        "text_200": "#cccccc",
        "bg_100": "#1c163d",
        "bg_200": "#494564",
        "bg_300": "#140f2b",
    },
}


def get_colors(territori):
    paleta = PALETES.get(territori, PALETES.get("ppcc", {}))
    return {
        "color_1": paleta.get("primary_100", "#F9A100"),
        "color_2": paleta.get("primary_200", "#E28F00"),
        "color_3": paleta.get("primary_300", "#8f0010"),
        "text_main": paleta.get("text_100", "#141415"),
        "text_sec": paleta.get("text_200", "#57687c"),
        "bg_main": paleta.get("bg_100", "#FFFFFF"),
        "bg_alt": paleta.get("bg_200", "#EEEEEE"),
        "bg_deep": paleta.get("bg_300", "#CCCCCC"),
        "accent_main": paleta.get("accent_100", "#239C7B"),
        "accent_sec": paleta.get("accent_200", "#946d00"),
    }


noms_territoris_llargs = {
    "pv": "País Valencià",
    "cat": "Catalunya",
    "ib": "Balears",
    "general": "",
    "ppcc": "",
}

img_w, img_h = 1080, 1350


def get_logo_path(_territori):
    return "assets/img/Top40Logo_banner.png"


def carregar_font(mida: int, pes: str = "regular"):
    return ImageFont.truetype(fonts_top40[pes], mida)


def genera_imatge_top_bloc(
    df,
    ini,
    fi,
    label_data,
    carpeta_sortida,
    territori="",
    prefix_bloc="Top",
    # New flags (backwards-compatible defaults):
    titol_portada=None,          # Custom cover title (e.g., playlist title)
    simple_portada=False,        # If True, draw a single simple cover (no artist photos)
    mostrar_footer=True,         # If False, remove explanatory footer text
    color_top1=True,             # If False, first row uses normal alternating bg (not highlighted)
):
    import os
    from datetime import datetime
    from io import BytesIO

    import requests
    from PIL import Image, ImageDraw, ImageFont

    img_w, img_h = 1080, 1350
    header_h = 100
    footer_h = 80
    header_y0 = 20
    header_y1 = header_y0 + header_h
    offset_extra = 20
    y_top_offset = header_y1 + offset_extra

    n_files = fi - ini + 1
    franja_h = (img_h - y_top_offset - footer_h) // n_files

    marge_hor = 30
    marge_vert = 12
    radius = 25

    font_pos = carregar_font(50, "heavy")
    font_titol = carregar_font(38, "bold")
    font_artista = carregar_font(26, "bold")
    font_new = carregar_font(20, "heavy")
    font_header = carregar_font(60, "heavy")
    font_territori = carregar_font(32, "bold")
    font_footer = carregar_font(24, "regular")
    font_icona = carregar_font(50, "bold")

    territori_nom = noms_territoris_llargs.get(
        (territori or "general").lower(), territori or "General"
    )
    colors = get_colors(territori)

    # ------------------------------
    # PORTADES (10 artistes, sense filtres)
    # ------------------------------
    import json
    from datetime import datetime

    import psycopg2
    from dotenv import load_dotenv
    from psycopg2.extras import RealDictCursor

    load_dotenv()

    # 1) Reunim fins a 10 imatges d'artistes (primer artista de cada cançó)
    imatges_artistes = []

    # If territory is general (ppcc), do not use artist backgrounds
    if (territori or "general").lower() in ("ppcc", "general"):
        imatges_artistes = [None]
    else:
        try:
            conn_p = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT"),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
            )
            cur_p = conn_p.cursor(cursor_factory=RealDictCursor)

            # df ja ve ordenat més avall, però ací assegurem: posició asc.
            df_ordenat = df.sort_values("posicio_territori").reset_index(drop=True)

            for _, r in df_ordenat.iterrows():
                if len(imatges_artistes) >= 10:
                    break
                aids = r.get("artistes_ids")
                # Si ve en text JSON (ex.: '["id1","id2"]') el convertim
                if isinstance(aids, str):
                    try:
                        aids = json.loads(aids)
                    except Exception:
                        aids = []
                if not isinstance(aids, list) or not aids:
                    continue
                primer_id = aids[0]

                cur_p.execute(
                    """
                    SELECT
                      COALESCE(a.imatge_url, sa.images->0->>'url') AS imatge_url
                    FROM artistes a
                    LEFT JOIN spotify_artists sa ON sa.id = a.id_spotify
                    WHERE a.id_spotify = %s
                    LIMIT 1
                """,
                    (primer_id,),
                )
                fila_img = cur_p.fetchone()
                url = fila_img["imatge_url"] if fila_img else None
                if url:
                    imatges_artistes.append(url)

            cur_p.close()
            conn_p.close()
        except Exception as e:
            print(f"⚠️ No s'han pogut obtindre imatges d'artistes: {e}")

    # Si no arrepleguem 10, continuem igualment amb les que hi haja (1..9)
    # 2) Dibuix de cadascuna de les 10 portades
    territori_nom = noms_territoris_llargs.get(
        (territori or "general").lower(), territori or "General"
    )
    label_data_str_portada = datetime.strptime(label_data, "%Y%m%d").strftime(
        "%d/%m/%Y"
    )
    setmana_num = (
        datetime.strptime(label_data, "%Y%m%d")
        - datetime.strptime("2025-05-24", "%Y-%m-%d")
    ).days // 7 + 1

    # Títol i subtítol: EXACTAMENT com fins ara (dues frases)
    text_titol_portada = "TOP QUARANTA" if territori != "ppcc" else "TOP QUARANTA"
    # (Si vols incloure el territori dins del títol per als regionals, descomenta):
    # if territori in ("pv", "cat", "ib"):
    #     text_titol_portada = f"TOP QUARANTA {territori_nom.upper()}"

    # Si ve d'una playlist (simple_portada=True) i tenim titol_portada,
    # usem el nom de la playlist com a subtítol; si no, mantenim "Setmana X".
    text_subtitol = (titol_portada.strip() if simple_portada and titol_portada else f"Setmana {setmana_num}")

    font_titol_portada = carregar_font(80, "heavy")
    font_subtitol = carregar_font(40, "bold")

    # Estil: franges baix-esquerra (colors de la paleta existent)
    pad_x = 36
    pad_y = 22
    gap_y = 12
    radius_portada = 28

    # Si per algun motiu no hi ha cap imatge, fem un fons llis
    if not imatges_artistes:
        imatges_artistes = [None]

    for idx, img_url in enumerate(imatges_artistes[:10], start=1):
        # Fons: foto tal qual, sense filtres. Si no hi ha, bg llis.
        imatge_portada = Image.new("RGB", (img_w, img_h), color=colors["bg_main"])
        if img_url:
            try:
                resposta = requests.get(img_url, timeout=6)
                img_original = Image.open(BytesIO(resposta.content)).convert("RGB")
                ow, oh = img_original.size
                ratio_o = ow / oh
                ratio_d = img_w / img_h
                if ratio_o > ratio_d:
                    nh = img_h
                    nw = int(nh * ratio_o)
                else:
                    nw = img_w
                    nh = int(nw / ratio_o)
                redim = img_original.resize((nw, nh), Image.LANCZOS)
                x0 = (nw - img_w) // 2
                y0 = (nh - img_h) // 2
                imatge_portada.paste(redim.crop((x0, y0, x0 + img_w, y0 + img_h)))
            except Exception as e:
                print(f"⚠️ Fons artista {idx} no aplicat: {e}")

        draw_p = ImageDraw.Draw(imatge_portada)

        # ▣ Xapeta de territori dalt-dreta (només PV/CAT/IB)
        if territori in ("pv", "cat", "ib"):
            font_terr = carregar_font(32, "bold")
            terr_txt = territori_nom.upper()
            pad_chip_x, pad_chip_y = 18, 10
            marge_top, marge_right = 30, 40

            tw = font_terr.getlength(terr_txt)
            chip_w = int(tw) + 2 * pad_chip_x
            chip_h = font_terr.size + 2 * pad_chip_y

            x1 = img_w - marge_right
            y1 = marge_top
            x0 = x1 - chip_w
            y0 = y1
            # Fons de chip amb el bg_alt per assegurar llegibilitat damunt foto
            draw_p.rounded_rectangle(
                [(x0, y0), (x1, y1 + chip_h)], radius=18, fill=colors["bg_alt"]
            )
            # Text en el color principal de text
            tx = x0 + pad_chip_x
            ty = y0 + pad_chip_y
            draw_p.text((tx, ty), terr_txt, font=font_terr, fill=colors["text_main"])

        # Mesurem textos
        tw = font_titol_portada.getlength(text_titol_portada)
        sw = font_subtitol.getlength(text_subtitol)
        maxw = int(max(tw, sw)) + 2 * pad_x
        th = font_titol_portada.size + 2 * pad_y
        sh = font_subtitol.size + 2 * pad_y

        # Posicionament baix (no arran del peu)
        base_y = img_h - 160  # separació del marge inferior
        x_left = 40

        # Barra de TÍTOL (color de paleta)
        draw_p.rounded_rectangle(
            [(x_left, base_y - th - sh - gap_y), (x_left + maxw, base_y - sh - gap_y)],
            radius=radius_portada,
            fill=colors["bg_main"],
        )

        # 🖼️ Logo segons territori (SVG → PNG en memòria)
        try:
            import cairosvg
            from PIL import Image

            logo_map = {
                "pv": "/root/TopQuaranta/media/logo-hz-pv.svg",
                "cat": "/root/TopQuaranta/media/logo-hz-cat.svg",
                "ib": "/root/TopQuaranta/media/logo-hz-ib.svg",
                "ppcc": "/root/TopQuaranta/media/logo-hz.svg",
                "general": "/root/TopQuaranta/media/logo-hz.svg",
            }
            logo_svg = logo_map.get(
                territori or "general", "/root/TopQuaranta/media/logo-hz.svg"
            )

            # Convertim SVG a PNG en memòria (un pèl més xicotet d'entrada)
            png_bytes = cairosvg.svg2png(url=logo_svg, output_width=520)
            logo_img = Image.open(BytesIO(png_bytes)).convert("RGBA")

            # Escalat amb marge intern perquè no toque vores
            lw, lh = logo_img.size
            pad_logo = 20  # aire als laterals dins la barra
            max_w_logo = maxw - 2 * pad_x - pad_logo

            # Reduïm sempre al 90% del màxim disponible (o menys si ja és menut)
            target_w = int(min(lw, max_w_logo) * 0.90)
            ratio = target_w / lw
            logo_img = logo_img.resize((target_w, int(lh * ratio)), Image.LANCZOS)
            lw, lh = logo_img.size

            # Posició amb un xicotet desplaçament cap a dins (padding visual)
            lx = x_left + pad_x + pad_logo // 2
            ly = base_y - sh - gap_y - th + (th - lh) // 2
            imatge_portada.paste(logo_img, (lx, ly), logo_img)

        except Exception as e:
            print(f"⚠️ Error mostrant el logo SVG: {e}")
            # Si falla, fem servir el text com a recurs
            tx = x_left + pad_x
            ty = base_y - sh - gap_y - th + pad_y
            draw_p.text(
                (tx, ty),
                text_titol_portada,
                font=font_titol_portada,
                fill=colors["color_3"],
            )

        # Barra de SUBTÍTOL (fa de “xapeta” inferior). Color = text_main; text en bg_main.
        draw_p.rounded_rectangle(
            [(x_left, base_y - sh), (x_left + maxw, base_y)],
            radius=radius_portada,
            fill=colors["text_main"],
        )
        sx = x_left + pad_x
        sy = base_y - sh + pad_y
        draw_p.text((sx, sy), text_subtitol, font=font_subtitol, fill=colors["bg_main"])

        # Guarda (reescriu sempre)
        nom_fitxer_portada = (
            f"00_portada{idx:02d}_{territori or 'general'}_{label_data}_bt40.png"
        )
        ruta_portada = os.path.join(carpeta_sortida, nom_fitxer_portada)
        imatge_portada.save(ruta_portada)

    # ------------------------------
    # BLOCS DE CANÇONS
    # ------------------------------

    df_bloc = df[
        (df["posicio_territori"] >= ini) & (df["posicio_territori"] <= fi)
    ].copy()
    df_bloc = df_bloc.sort_values("posicio_territori")

    imatge = Image.new("RGB", (img_w, img_h), color=colors["bg_main"])
    draw = ImageDraw.Draw(imatge)

    bloc_w = int((img_w - 2 * marge_hor) * 0.6)
    bloc_h = header_h
    bloc_x0 = marge_hor
    bloc_x1 = bloc_x0 + bloc_w
    bloc_y0 = header_y0
    bloc_y1 = bloc_y0 + bloc_h

    # 🖼️ Logo segons territori (SVG → PNG) al header, alineat a la dreta i sense xapeta
    try:
        import cairosvg

        png_pad_right = 24  # aire mínim amb la vora dreta
        png_pad_top = 10  # aire superior

        logo_map = {
            "pv": "/root/TopQuaranta/media/logo-hz-pv.svg",
            "cat": "/root/TopQuaranta/media/logo-hz-cat.svg",
            "ib": "/root/TopQuaranta/media/logo-hz-ib.svg",
            "ppcc": "/root/TopQuaranta/media/logo-hz.svg",
            "general": "/root/TopQuaranta/media/logo-hz.svg",
        }
        logo_svg = logo_map.get(
            territori or "general", "/root/TopQuaranta/media/logo-hz.svg"
        )

        # Render SVG → PNG i escalat perquè isca un pèl més menut que l'alçada del header
        png_bytes = cairosvg.svg2png(url=logo_svg, output_width=520)
        logo_img = Image.open(BytesIO(png_bytes)).convert("RGBA")

        lw, lh = logo_img.size
        max_h_logo = header_h - 2 * png_pad_top
        # Escalem per alçar-lo dins del "header" virtual i un 92% per donar aire
        scale = min(max_h_logo / lh, 1.0) * 0.92
        new_w, new_h = int(lw * scale), int(lh * scale)
        if new_w > 0 and new_h > 0:
            logo_img = logo_img.resize((new_w, new_h), Image.LANCZOS)
            lw, lh = logo_img.size

        # Alineat a l'esquerra, un pèl separat de la vora; centrat verticalment al header
        png_pad_left = 24
        lx = bloc_x0 + png_pad_left
        ly = bloc_y0 + (header_h - lh) // 2
        imatge.paste(logo_img, (lx, ly), logo_img)

    except Exception as e:
        print(f"⚠️ Header: error mostrant el logo SVG: {e}")
        # Fallback: no fem res; sense xapeta i sense text

    text_w = font_territori.getlength(territori_nom)
    territori_x = img_w - text_w - marge_hor
    territori_y = bloc_y0 + bloc_h // 2 - font_territori.size // 2
    draw.text(
        (territori_x, territori_y),
        territori_nom,
        font=font_territori,
        fill=colors["text_main"],
    )

    y_top_offset = header_y1 + offset_extra

    for idx, fila in enumerate(df_bloc.itertuples(), start=0):
        y_top = y_top_offset + idx * franja_h
        y0 = y_top + marge_vert
        y1 = y_top + franja_h
        x0 = marge_hor
        x1 = img_w - marge_hor

        # If color_top1 is False, row #1 uses normal alternating background
        if color_top1:
            color_fons = (
                colors["accent_sec"]
                if fila.posicio_territori == 1
                else (colors["bg_alt"] if idx % 2 == 0 else colors["bg_deep"])
            )
        else:
            color_fons = colors["bg_alt"] if idx % 2 == 0 else colors["bg_deep"]

        draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=radius, fill=color_fons)

        pos_w = 90
        pos_x = x0
        pos_y0 = y0
        pos_y1 = y1
        draw.rounded_rectangle(
            [(pos_x, pos_y0), (pos_x + pos_w, pos_y1)],
            radius=20,
            fill=colors["color_1"],
        )

        pos_text = str(fila.posicio_territori)
        text_width = font_pos.getlength(pos_text)
        text_x = pos_x + (pos_w - text_width) / 2
        text_y = pos_y0 + (franja_h - font_pos.size) / 2 - 5
        draw.text((text_x, text_y), pos_text, font=font_pos, fill=colors["color_3"])

        try:
            if hasattr(fila, "album_caratula_url") and fila.album_caratula_url:
                url = fila.album_caratula_url
                if isinstance(url, str) and url.strip().startswith("{"):
                    try:
                        import json

                        url = json.loads(url)["url"]
                    except Exception as e:
                        print(
                            f"⚠️ No s'ha pogut extraure la URL de la caràtula (posició {fila.posicio_territori}): {e}"
                        )
                        url = None
                if url:
                    resposta = requests.get(url, timeout=5)
                caratula = Image.open(BytesIO(resposta.content)).convert("RGB")
                caratula = caratula.resize((75, 75))
                y_caratula = y0 + (y1 - y0 - 75) // 2
                x_caratula = x1 - 90 - 15
                imatge.paste(caratula, (x_caratula, y_caratula))
        except Exception as e:
            print(f"⚠️ Error carregant caràtula posició {fila.posicio_territori}: {e}")

        x_text = pos_x + pos_w + 20
        y_titol = y0 + 10
        y_artista = y_titol + font_titol.size + 8

        color_titol = colors["text_main"]
        titol_str = fila.titol
        paraules_titol = titol_str.split(" ")
        titol_draw = titol_str
        while (
            font_titol.getlength(titol_draw) + 30 > (x1 - x_text - 110)
            and len(paraules_titol) > 1
        ):
            paraules_titol.pop()
            titol_draw = " ".join(paraules_titol).strip() + "..."
        draw.text((x_text, y_titol), titol_draw, font=font_titol, fill=color_titol)

        artistes_str = (
            ", ".join(fila.artistes)
            if isinstance(fila.artistes, list)
            else str(fila.artistes)
        )
        paraules = artistes_str.split(" ")
        artistes_draw = artistes_str
        while (
            font_artista.getlength(artistes_draw) + 30 > (x1 - x_text - 110)
            and len(paraules) > 1
        ):
            paraules.pop()
            artistes_draw = " ".join(paraules).strip() + "..."
        color_artista = (
            colors["text_main"] if fila.posicio_territori == 1 else colors["text_sec"]
        )
        draw.text(
            (x_text, y_artista), artistes_draw, font=font_artista, fill=color_artista
        )

        titol_width = font_titol.getlength(fila.titol)
        x_indicator = x_text + titol_width + 15
        # 'NOU' només si es_novetat == True (no per simples reentrades)
        es_nou = getattr(fila, "es_novetat", False)
        if es_nou is True:
            draw.rectangle(
                [(x_indicator, y_titol + 5), (x_indicator + 60, y_titol + 30)],
                fill=colors["accent_sec"],
            )
            draw.text(
                (x_indicator + 7, y_titol + 7),
                "NOU",
                font=font_new,
                fill=colors["bg_main"],
            )
        elif (
            hasattr(fila, "canvi_posicio")
            and (not pd.isna(fila.canvi_posicio))
            and fila.canvi_posicio > 0
        ):
            draw.text(
                (x_indicator, y_titol - 20),
                "↑",
                font=font_icona,
                fill=colors["accent_main"],
            )
    # Footer block can be fully disabled with mostrar_footer=False
    if mostrar_footer:

        y_footer = img_h - footer_h
        footer = Image.new("RGB", (img_w, footer_h), color=colors["bg_main"])
        footer_draw = ImageDraw.Draw(footer)

        font_footer = carregar_font(18, "regular")
        text1 = "El TOP QUARANTA es basa en les dades de popularitat de Spotify."
        text2 = "Per a saber com construïm el ranking visita'ns a @TopQuaranta"

        text1_w = font_footer.getlength(text1)
        text2_w = font_footer.getlength(text2)

        x_text1 = (img_w - text1_w) // 2
        x_text2 = (img_w - text2_w) // 2
        y_text1 = 15
        y_text2 = y_text1 + font_footer.size + 6

        footer_draw.text(
            (x_text1, y_text1), text1, font=font_footer, fill=colors["text_sec"]
        )
        footer_draw.text(
            (x_text2, y_text2), text2, font=font_footer, fill=colors["text_sec"]
        )

        imatge.paste(footer, (0, y_footer))

    nprefix_bloc = {
        (1, 10): "01_bloc01-10",
        (11, 20): "02_bloc11-20",
        (21, 30): "03_bloc21-30",
        (31, 40): "04_bloc31-40",
    }.get((ini, fi), f"bloc{ini}-{fi}")

    prefix = f"{nprefix_bloc}_{territori or 'general'}_{label_data}_bt40"
    nom_fitxer = f"{prefix}.png"
    ruta = os.path.join(carpeta_sortida, nom_fitxer)
    imatge.save(ruta)


def genera_imatge_top_individual(fila, label_data, carpeta_sortida, territori=""):
    from datetime import datetime

    img_w, img_h = 1080, 1920
    colors = get_colors(territori)
    territori_nom = noms_territoris_llargs.get((territori or "general").lower(), "")
    label_data_str = datetime.strptime(label_data, "%Y%m%d").strftime("%d/%m/%Y")
    novetat_prefix = "07"  # Story de novetat comença per 07, 08, etc.

    # 🧾 Comprovem si cal fer portada
    nom_fitxer_portada = f"00_portada_{territori or 'general'}_{label_data}.png"
    ruta_portada = os.path.join(carpeta_sortida, nom_fitxer_portada)
    if not os.path.exists(ruta_portada):
        imatge_portada = Image.new("RGB", (img_w, img_h), color=colors["bg_main"])
        draw_portada = ImageDraw.Draw(imatge_portada)

        # Fonts portada
        font_titol = carregar_font(100, "heavy")
        font_territori = carregar_font(60, "bold")
        font_data = carregar_font(40, "regular")

        # Requadre arrodonit
        quadre_w, quadre_h = 800, 500
        quadre_x0 = (img_w - quadre_w) // 2
        quadre_y0 = (img_h - quadre_h) // 2
        quadre_x1 = quadre_x0 + quadre_w
        quadre_y1 = quadre_y0 + quadre_h
        draw_portada.rounded_rectangle(
            [(quadre_x0, quadre_y0), (quadre_x1, quadre_y1)],
            radius=60,
            fill=colors["bg_alt"],
        )

        y = quadre_y0 + 60
        # TOP 40
        txt = "TOP 40" if territori == "ppcc" else "TOP 5"
        x = (img_w - font_titol.getlength(txt)) // 2
        draw_portada.text((x, y), txt, font=font_titol, fill=colors["color_1"])
        y += font_titol.size + 40

        # TERRITORI
        if territori_nom:
            txt = territori_nom.upper()
            x = (img_w - font_territori.getlength(txt)) // 2
            draw_portada.text(
                (x, y), txt, font=font_territori, fill=colors["text_main"]
            )
            y += font_territori.size + 30

        # DATA
        setmana_num = (
            datetime.strptime(label_data, "%Y%m%d")
            - datetime.strptime("2025-05-24", "%Y-%m-%d")
        ).days // 7 + 1
        txt = f"Setmana {setmana_num}"
        x = (img_w - font_data.getlength(txt)) // 2
        draw_portada.text((x, y), txt, font=font_data, fill=colors["text_sec"])

        imatge_portada.save(ruta_portada)

    # 🎵 Imatge de cançó individual
    imatge = Image.new("RGB", (img_w, img_h), color=colors["bg_main"])
    draw = ImageDraw.Draw(imatge)

    # Mides i marges
    card_margin = 175
    card_w = img_w - 2 * card_margin
    card_h = 1150
    card_x0 = card_margin
    card_y0 = 325
    card_x1 = card_x0 + card_w
    card_y1 = card_y0 + card_h
    radius = 60

    # 🏷️ Text del territori damunt
    font_label = carregar_font(40, "bold")
    if territori_nom:
        text_w = font_label.getlength(territori_nom.upper())
        text_x = (img_w - text_w) // 2
        text_y = card_y0 - 140
        draw.text(
            (text_x, text_y),
            territori_nom.upper(),
            font=font_label,
            fill=colors["text_sec"],
        )

    # 🏷️ Requadre principal
    draw.rounded_rectangle(
        [(card_x0, card_y0), (card_x1, card_y1)], radius=radius, fill=colors["bg_alt"]
    )

    # 📸 Caràtula
    caratula_margin = 30
    caratula_w = card_w - 2 * caratula_margin
    caratula_h = int(caratula_w)
    x_caratula = card_x0 + caratula_margin
    y_caratula = card_y0 + caratula_margin
    try:
        url = fila.get("album_caratula_url")
        if url:
            if isinstance(url, str) and url.strip().startswith("{"):
                try:
                    import json

                    url = json.loads(url)["url"]
                except Exception as e:
                    print(f"⚠️ No s'ha pogut extraure la URL de la caràtula: {e}")
                    url = None
            if url:
                try:
                    resposta = requests.get(url, timeout=5)
                    caratula = Image.open(BytesIO(resposta.content)).convert("RGB")
                    caratula = caratula.resize((caratula_w, caratula_h))
                    mask = Image.new("L", (caratula_w, caratula_h), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.rounded_rectangle(
                        [(0, 0), (caratula_w, caratula_h)], radius=40, fill=255
                    )
                    imatge.paste(caratula, (x_caratula, y_caratula), mask)
                except Exception as e:
                    print(f"⚠️ Error carregant la caràtula: {e}")
            caratula = Image.open(BytesIO(resposta.content)).convert("RGB")
            caratula = caratula.resize((caratula_w, caratula_h))
            mask = Image.new("L", (caratula_w, caratula_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle(
                [(0, 0), (caratula_w, caratula_h)], radius=40, fill=255
            )
            imatge.paste(caratula, (x_caratula, y_caratula), mask)
    except Exception as e:
        print(f"⚠️ No s'ha pogut carregar la caràtula: {e}")

    # Fonts
    font_pos = carregar_font(60, "heavy")
    font_titol = carregar_font(52, "bold")
    font_artista = carregar_font(34, "regular")

    # Text TOP
    x_text = card_x0 + 60
    y_text = y_caratula + caratula_h + 50
    draw.text(
        (x_text, y_text),
        f"TOP {fila['posicio_territori']}",
        font=font_pos,
        fill=colors["text_main"],
    )
    y_text += font_pos.size + 30

    # Funció per trencar línies
    def wrap_text(text, font, max_width):
        paraules = text.split()
        línies = []
        línia = ""
        for paraula in paraules:
            test_line = f"{línia} {paraula}".strip()
            if font.getlength(test_line) <= max_width:
                línia = test_line
            else:
                línies.append(línia)
                línia = paraula
        if línia:
            línies.append(línia)
        return línies

    # TÍTOL
    titol_str = fila["titol"].upper()
    titol_lines = wrap_text(titol_str, font_titol, card_w - 120)
    for lin in titol_lines:
        draw.text((x_text, y_text), lin, font=font_titol, fill=colors["color_1"])
        y_text += font_titol.size + 8

    # ARTISTES
    artistes_str = (
        ", ".join(fila["artistes"])
        if isinstance(fila["artistes"], list)
        else str(fila["artistes"])
    )
    art_lines = wrap_text(
        artistes_str.upper(), font=font_artista, max_width=card_w - 120
    )
    for lin in art_lines:
        draw.text((x_text, y_text), lin, font=font_artista, fill=colors["text_sec"])
        y_text += font_artista.size + 6

    # Guarda
    # Prefix per defecte segons tipus de contingut
    prefix = f"Top{fila['posicio_territori']:02d}"

    # Comprovem si és portada
    if fila["posicio_territori"] == 1 and not any(
        "portada" in f for f in os.listdir(carpeta_sortida)
    ):
        prefix = "00_portada"

    # Si és una novetat real (mai havia entrat)
    if fila.get("es_novetat") is True:
        prefix = f"{novetat_prefix}_{fila['posicio_territori']:02d}_novetat"

    # Si és TOP 5 a 1 (story)
    if fila["posicio_territori"] in range(1, 6):
        pos = 6 - fila["posicio_territori"]  # 1 → 05, 2 → 04, ..., 5 → 01
        prefix = f"{pos:02d}_top{fila['posicio_territori']:02d}"

    nom_fitxer = f"{prefix}_{territori or 'general'}_{label_data}.png"
    ruta = os.path.join(carpeta_sortida, nom_fitxer)
    imatge.save(ruta)

    # 🔁 Copiem els separadors de playlist i novetats amb prefixos
    for subcarpeta in ["playlist", "novetats"]:
        origen = f"assets/img/{subcarpeta}/{territori}.png"
        if os.path.exists(origen):
            prefix = "99" if subcarpeta == "playlist" else "06"
            desti = os.path.join(
                carpeta_sortida, f"{prefix}_{subcarpeta}_{territori}.png"
            )
            try:
                Image.open(origen).save(desti)
            except Exception as e:
                print(
                    f"⚠️ No s'ha pogut copiar {prefix}_{subcarpeta}_{territori}.png: {e}"
                )
        else:
            print(f"⚠️ No trobat: {origen}")

    ruta = os.path.join(carpeta_sortida, nom_fitxer)
    imatge.save(ruta)


def genera_imatge_portada_albums(df_albums, carpeta_sortida):
    import os
    from PIL import Image, ImageDraw

    img_w, img_h = 1080, 1350
    colors = get_colors("ppcc")

    # Funció interna per dibuixar una portada genèrica
    def crea_portada(text_linia1, text_linia2, nom_fitxer):
        imatge = Image.new("RGB", (img_w, img_h), color=colors["bg_main"])
        draw = ImageDraw.Draw(imatge)

        font_titol = carregar_font(80, "heavy")

        # Requadre central
        radius = 60
        quadre_w = 800
        quadre_h = 350
        quadre_x0 = (img_w - quadre_w) // 2
        quadre_y0 = (img_h - quadre_h) // 2
        quadre_x1 = quadre_x0 + quadre_w
        quadre_y1 = quadre_y0 + quadre_h

        draw.rounded_rectangle(
            [(quadre_x0, quadre_y0), (quadre_x1, quadre_y1)],
            radius=radius,
            fill=colors["bg_alt"],
        )

        # Text centrat
        línies = [text_linia1, text_linia2]
        y = quadre_y0 + 60
        for lin in línies:
            tw = font_titol.getlength(lin)
            x = (img_w - tw) // 2
            draw.text((x, y), lin, font=font_titol, fill=colors["color_1"])
            y += font_titol.size + 40

        ruta = os.path.join(carpeta_sortida, nom_fitxer)
        imatge.save(ruta)
        print(f"🖼️ Portada guardada: {ruta}")

    # ========================
    # 1️⃣ Portada NOUS ÀLBUMS
    # ========================
    crea_portada("NOUS", "ÀLBUMS", "00_portada_albums.png")

    # ========================
    # 2️⃣ Portada NOUS SINGLES
    # ========================
    crea_portada("NOUS", "SINGLES", "00_portada_singles.png")


def genera_imatge_album_individual(fila, carpeta_sortida, numero_imatge):
    from io import BytesIO

    import requests
    from PIL import Image, ImageDraw

    img_w, img_h = 1080, 1350
    colors = get_colors("ppcc")
    imatge = Image.new("RGB", (img_w, img_h), color=colors["bg_main"])
    draw = ImageDraw.Draw(imatge)

    # Mides i marges
    card_margin = 100
    card_w = img_w - 2 * card_margin
    card_h = 980
    card_x0 = card_margin
    card_y0 = 180
    card_x1 = card_x0 + card_w
    card_y1 = card_y0 + card_h
    radius = 60

    # 🏷️ Requadre principal
    draw.rounded_rectangle(
        [(card_x0, card_y0), (card_x1, card_y1)], radius=radius, fill=colors["bg_alt"]
    )

    # 📸 Caràtula
    caratula_margin = 40
    caratula_w = card_w - 2 * caratula_margin
    caratula_h = caratula_w  # Quadrat
    x_caratula = card_x0 + caratula_margin
    y_caratula = card_y0 + caratula_margin

    try:
        url = fila.get("image_url")
        if url:
            resposta = requests.get(url, timeout=5)
            caratula = Image.open(BytesIO(resposta.content)).convert("RGB")
            caratula = caratula.resize((caratula_w, caratula_h))

            # Màscara arrodonida
            mask = Image.new("L", (caratula_w, caratula_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle(
                [(0, 0), (caratula_w, caratula_h)], radius=40, fill=255
            )

            imatge.paste(caratula, (x_caratula, y_caratula), mask)
    except Exception as e:
        print(f"⚠️ Error carregant la caràtula: {e}")

    # 🎨 Fonts
    font_titol = carregar_font(50, "bold")
    font_artista = carregar_font(30, "regular")

    # 🧾 Textos
    x_text = card_x0 + 60
    y_text = y_caratula + caratula_h + 15

    # Wrap helper
    def wrap_text(text, font, max_width):
        paraules = text.split()
        línies = []
        línia = ""
        for paraula in paraules:
            test = (línia + " " + paraula).strip()
            if font.getlength(test) <= max_width:
                línia = test
            else:
                línies.append(línia)
                línia = paraula
        if línia:
            línies.append(línia)
        return línies

    # TÍTOL
    titol_str = fila["name"].strip().upper()
    titol_lines = wrap_text(titol_str, font_titol, card_w - 120)
    for lin in titol_lines:
        draw.text((x_text, y_text), lin, font=font_titol, fill=colors["color_1"])
        y_text += font_titol.size + 8

    # ARTISTES
    artistes_str = (
        ", ".join(fila["artist_names"])
        if isinstance(fila["artist_names"], list)
        else str(fila["artist_names"])
    )
    art_lines = wrap_text(
        artistes_str.upper(), font=font_artista, max_width=card_w - 120
    )
    for lin in art_lines:
        draw.text((x_text, y_text), lin, font=font_artista, fill=colors["text_sec"])
        y_text += font_artista.size + 6

    # Guarda
    titol_net = fila["name"].strip().replace("/", "-").replace("\\", "-")[:30]
    nom_fitxer = f"{numero_imatge:02d}_album_{titol_net}.png"
    ruta = os.path.join(carpeta_sortida, nom_fitxer)
    imatge.save(ruta)
    print(f"🖼️ Àlbum guardat: {nom_fitxer}")


def genera_imatge_bloc_singles(df_singles, carpeta_sortida, idx_inicial=15):
    from io import BytesIO

    import requests
    from PIL import Image, ImageDraw

    img_w, img_h = 1080, 1350
    header_h = 100
    footer_h = 80
    header_y0 = 20
    header_y1 = header_y0 + header_h
    offset_extra = 20
    y_top_offset = header_y1 + offset_extra
    n_files = 10
    franja_h = (img_h - y_top_offset - footer_h) // n_files

    marge_hor = 30
    marge_vert = 12
    radius = 25

    font_titol = carregar_font(38, "bold")
    font_artista = carregar_font(26, "bold")
    font_header = carregar_font(60, "heavy")
    font_footer = carregar_font(18, "regular")

    colors = get_colors("ppcc")

    num_blocs = (len(df_singles) + n_files - 1) // n_files  # Arrodoneix cap amunt

    for bloc_idx in range(num_blocs):
        imatge = Image.new("RGB", (img_w, img_h), color=colors["bg_main"])
        draw = ImageDraw.Draw(imatge)

        # 🔲 Header "NOUS SINGLES"
        bloc_w = int((img_w - 2 * marge_hor) * 0.6)
        bloc_h = header_h
        bloc_x0 = marge_hor
        bloc_x1 = bloc_x0 + bloc_w
        bloc_y0 = header_y0
        bloc_y1 = bloc_y0 + bloc_h
        draw.rounded_rectangle(
            [(bloc_x0, bloc_y0), (bloc_x1, bloc_y1)],
            radius=radius,
            fill=colors["color_1"],
        )

        text_header = "NOUS SINGLES"
        for i, line in enumerate(text_header.split("\n")):
            text_w = font_header.getlength(line)
            text_x = bloc_x0 + bloc_w // 2 - text_w // 2
            text_y = bloc_y0 + 10 + i * (font_header.size + 4)
            draw.text((text_x, text_y), line, font=font_header, fill=colors["color_3"])

        # 🔁 Llistat de 10 singles
        df_bloc = (
            df_singles.iloc[bloc_idx * n_files : (bloc_idx + 1) * n_files]
            .copy()
            .reset_index(drop=True)
        )
        for idx in range(10):
            y_top = y_top_offset + idx * franja_h
            y0 = y_top + marge_vert
            y1 = y_top + franja_h
            x0 = marge_hor
            x1 = img_w - marge_hor

            color_fons = colors["bg_alt"] if idx % 2 == 0 else colors["bg_deep"]
            draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=radius, fill=color_fons)

            if idx < len(df_bloc):
                fila = df_bloc.iloc[idx].to_dict()
                titol_str = str(fila.get("name", "")).strip()
                artistes = fila.get("artist_names", [])
                artistes_str = (
                    ", ".join(artistes) if isinstance(artistes, list) else str(artistes)
                )

                # Caràtula
                try:
                    url = fila.get("image_url")
                    if url:
                        resposta = requests.get(url, timeout=5)
                        caratula = Image.open(BytesIO(resposta.content)).convert("RGB")
                        caratula = caratula.resize((75, 75))
                        y_caratula = y0 + (y1 - y0 - 75) // 2
                        x_caratula = x1 - 90 - 15
                        imatge.paste(caratula, (x_caratula, y_caratula))
                except Exception as e:
                    print(f"⚠️ Error carregant caràtula del single: {e}")

                # Títol i artistes
                x_text = x0 + 20
                y_titol = y0 + 10
                y_artista = y_titol + font_titol.size + 8

                # Títol amb truncament
                paraules_titol = titol_str.split()
                titol_draw = titol_str
                while (
                    font_titol.getlength(titol_draw) + 30 > (x1 - x_text - 110)
                    and len(paraules_titol) > 1
                ):
                    paraules_titol.pop()
                    titol_draw = " ".join(paraules_titol).strip() + "..."
                draw.text(
                    (x_text, y_titol),
                    titol_draw,
                    font=font_titol,
                    fill=colors["text_main"],
                )

                # Artistes amb truncament
                paraules = artistes_str.split()
                artistes_draw = artistes_str
                while (
                    font_artista.getlength(artistes_draw) + 30 > (x1 - x_text - 110)
                    and len(paraules) > 1
                ):
                    paraules.pop()
                    artistes_draw = " ".join(paraules).strip() + "..."
                draw.text(
                    (x_text, y_artista),
                    artistes_draw,
                    font=font_artista,
                    fill=colors["text_sec"],
                )

        # 👣 Peu
        y_footer = img_h - footer_h
        footer = Image.new("RGB", (img_w, footer_h), color=colors["bg_main"])
        footer_draw = ImageDraw.Draw(footer)

        text1 = "Llistat automatitzat amb àlbums recents de Spotify."
        text2 = "Segueix-nos a @TopQuaranta per descobrir novetats cada diumenge."

        text1_w = font_footer.getlength(text1)
        text2_w = font_footer.getlength(text2)
        x_text1 = (img_w - text1_w) // 2
        x_text2 = (img_w - text2_w) // 2
        y_text1 = 15
        y_text2 = y_text1 + font_footer.size + 6

        footer_draw.text(
            (x_text1, y_text1), text1, font=font_footer, fill=colors["text_sec"]
        )
        footer_draw.text(
            (x_text2, y_text2), text2, font=font_footer, fill=colors["text_sec"]
        )

        imatge.paste(footer, (0, y_footer))

        # 🧾 Guarda amb numeració
        num_fitxer = idx_inicial + bloc_idx
        nom_fitxer = f"{num_fitxer:02d}_bloc_singles.png"
        ruta = os.path.join(carpeta_sortida, nom_fitxer)
        imatge.save(ruta)
        print(f"✅ Bloc de singles guardat: {ruta}")
