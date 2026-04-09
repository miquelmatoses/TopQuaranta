import os
from datetime import datetime


def crear_logger(ruta_log):
    def log(msg):
        hora = datetime.now().strftime("%Y-%m-%d %H:%M")
        entrada = f"[{hora}] {msg}\n"

        # Crear el directori si no existeix
        os.makedirs(os.path.dirname(ruta_log), exist_ok=True)

        if not os.path.exists(ruta_log):
            with open(ruta_log, "w", encoding="utf-8") as f:
                f.write(entrada)
            return

        with open(ruta_log, "r", encoding="utf-8") as f:
            primera_linia = f.readline()
            if "] " in primera_linia:
                missatge_anterior = primera_linia.split("] ", 1)[1].strip()
            else:
                missatge_anterior = primera_linia.strip()

        if missatge_anterior == msg.strip():
            return

        with open(ruta_log, "r", encoding="utf-8") as f:
            contingut = f.read()

        with open(ruta_log, "w", encoding="utf-8") as f:
            f.write(entrada + contingut)

    return log
