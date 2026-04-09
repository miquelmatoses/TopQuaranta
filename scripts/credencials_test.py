import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

ARTIST_ID = "2lehndMSdeclXMI4YGDjfq"  # artista de prova

credencials = [
    ("SPOTIPY_CLIENT_ID_WORKER_A1", "SPOTIPY_CLIENT_SECRET_WORKER_A1"),
    ("SPOTIPY_CLIENT_ID_WORKER_B1", "SPOTIPY_CLIENT_SECRET_WORKER_B1"),
    ("SPOTIPY_CLIENT_ID_WORKER_C1", "SPOTIPY_CLIENT_SECRET_WORKER_C1"),
    ("SPOTIPY_CLIENT_ID_WORKER_D1", "SPOTIPY_CLIENT_SECRET_WORKER_D1"),
    ("SPOTIPY_CLIENT_ID_WORKER_E1", "SPOTIPY_CLIENT_SECRET_WORKER_E1"),
]

for client_id_key, client_secret_key in credencials:
    client_id = os.getenv(client_id_key)
    client_secret = os.getenv(client_secret_key)
    nom = client_id_key.split("_")[-1]

    try:
        # 1. Obtenir token
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=10,
        )
        token = r.json().get("access_token")
        if not token:
            print(f"❌ {nom}: no token ({r.status_code})")
            time.sleep(2.5)
            continue

        headers = {"Authorization": f"Bearer {token}"}

        # 2. Fer crida real per obtindre àlbums
        url = f"https://api.spotify.com/v1/artists/{ARTIST_ID}/albums"
        params = {"limit": 50}
        r2 = requests.get(url, headers=headers, params=params, timeout=10)

        if r2.status_code == 200:
            albums = r2.json().get("items", [])
            print(f"✅ {nom}: {len(albums)} àlbums")
        elif r2.status_code == 429:
            retry_after = r2.headers.get("Retry-After", "?")
            print(f"⚠️ {nom}: 429 ({retry_after}s)")
        else:
            print(f"❌ {nom}: {r2.status_code}")

    except Exception as e:
        print(f"❌ {nom}: {type(e).__name__}")

    time.sleep(2.5)
