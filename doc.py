import os
import shutil
import subprocess
from datetime import datetime

import psycopg2
from dotenv import load_dotenv

# 🔧 Configuració de filtres per ignorar fitxers i carpetes no rellevants
IGNORAR_DIRS = {
    "venv",
    "__pycache__",
    "logs",
    "data",
    "outputs",
    ".git",
    ".vscode-server",
}
IGNORAR_EXTENSIONS = {".log", ".csv", ".pyc", ".so", ".pyd", ".zip"}
FITXERS_ADMESOS = {".py", ".sh", ".sql", ".txt", ".md", ".env"}

OUTPUT_FILE = f"ultima_documentacio.md"
TITOLS = []
CONTINGUT = []


# 🔍 Decideix si un fitxer és rellevant per incloure
def es_fitxer_valit(nom_fitxer):
    return any(nom_fitxer.endswith(ext) for ext in FITXERS_ADMESOS) and not any(
        nom_fitxer.endswith(ext) for ext in IGNORAR_EXTENSIONS
    )


# 🧠 Detecta l'idioma per fer format de codi en Markdown
def detectar_llenguatge(nom_fitxer):
    if nom_fitxer.endswith(".py"):
        return "python"
    elif nom_fitxer.endswith(".sh"):
        return "bash"
    elif nom_fitxer.endswith(".sql"):
        return "sql"
    else:
        return ""


# 🔗 Prepara els títols perquè es puguen usar com a enllaços d'índex
def netejar_anchor(text):
    return (
        text.lower()
        .replace(" ", "-")
        .replace("/", "")
        .replace(".", "")
        .replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ò", "o")
        .replace("ó", "o")
        .replace("ú", "u")
    )


# Trenquem les línies massa llargues
def trencar_linia_llarga(text, max_len=120):
    """Parteix línies llargues en múltiples línies"""
    result = []
    for line in text.splitlines():
        if len(line) > max_len:
            # Divideix en trossos i afegeix barra de continuació
            parts = [line[i : i + max_len] + "\\" for i in range(0, len(line), max_len)]
            parts[-1] = parts[-1].rstrip("\\")  # L'últim no porta barra
            result.extend(parts)
        else:
            result.append(line)
    return "\n".join(result)


# 📷 Afegim logotips al principi si estan a utils/imatges
logo_dir = os.path.join("assets", "img")
logos = (
    [f for f in os.listdir(logo_dir) if f.endswith((".png", ".jpg", ".jpeg", ".svg"))]
    if os.path.isdir(logo_dir)
    else []
)
if logos:
    CONTINGUT.append("## 🖼️ Logotips\n\n")
    for logo in sorted(logos):
        ruta = os.path.join(logo_dir, logo)
        CONTINGUT.append(f"![{logo}]({ruta})\n\n")

# ✍️ Introducció al projecte
CONTINGUT.append(
    """
# 🎵 TopQuaranta

**TopQuaranta** és un sistema que genera un rànquing musical en valencià, basat en dades de Spotify. 
El projecte recopila informació de cançons i artistes de diversos territoris de parla catalana, i la presenta de forma o\
rganitzada.

## ✨ Funcionalitats destacades

- Extracció de dades via API de Spotify.
- Filtratge per territori i exclusions.
- Càrrega i visualització de rànquings diaris i setmanals.
- Actualització automàtica mitjançant crons.
- Generació de visualitzacions i publicació en xarxes socials.

---
"""
)
CONTINGUT.append(
    f"\n🗓️ **Document generat el {datetime.now().strftime('%d/%m/%Y a les %H:%M')}**\n\n"
)
# 🛠️ Documentació del workflow Git (dev/prod)
TITOLS.append(
    ("##", "🛠️ Gestió del codi i desplegament (Git, dev i prod)", "git-workflow")
)
CONTINGUT.append(
    """
# 🛠️ Gestió del codi i desplegament (Git, dev i prod)

TopQuaranta utilitza dos directoris amb git al mateix servidor:

- **Producció (prod)**: `/root/TopQuaranta`
- **Desenvolupament (dev)**: `/root/TopQuaranta_dev`

El repositori *real* de treball és el de **dev**. Producció es manté sincronitzat fent `git pull` des de prod apuntant a\
 dev.

## 📂 Repositoris locals

- `/root/TopQuaranta_dev`: on es fan els canvis, commits i branques.
- `/root/TopQuaranta`: on s'executen crons, workers i la web.

Els dos són repositoris git, però només **dev** es toca manualment.

## 🔄 Flux de treball habitual

1. **Assegurar que dev té l'última versió de prod**:

   