import os

from fastapi import FastAPI, Request

app = FastAPI()

PROJECT_PATH = (
    "/Users/miquel/Documents/topquaranta_local"  # <-- comprova que siga correcte
)


@app.get("/llegix")
async def llegix_fitxer(ruta: str):
    try:
        fitxer = os.path.join(PROJECT_PATH, ruta)
        with open(fitxer, "r") as f:
            contingut = f.read()
        return {"status": "ok", "contingut": contingut}
    except Exception as e:
        return {"status": "error", "missatge": str(e)}


import psycopg2
from fastapi.responses import JSONResponse
from psycopg2.extras import RealDictCursor

# Credencials de la teua base de dades PostgreSQL
DB_CONFIG = {
    "host": "localhost",  # o l'host que corresponga
    "port": 5432,
    "database": "topquaranta",  # substitueix pel teu nom real de BBDD
    "user": "postgres",  # el teu usuari de PostgreSQL
    "password": "la_teua_clau",  # substitueix-la pel password real
}


@app.get("/consulta")
async def consulta(sql: str):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql)
        resultats = cur.fetchall()
        cur.close()
        conn.close()
        return JSONResponse(content={"status": "ok", "resultats": resultats})
    except Exception as e:
        return JSONResponse(content={"status": "error", "missatge": str(e)})
