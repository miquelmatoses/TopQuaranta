import os
import time
from datetime import datetime

LOG_PATH = "/tmp/spotify_request_timestamps.log"
MAX_REQUESTS_PER_HOUR = 1000
MIN_INTERVAL_SECONDS = 2.5


def pot_fer_crida():
    """Espera fins que es puga fer una crida segura a l'API de Spotify."""
    while True:
        ara = time.time()

        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH, "w") as f:
                f.write(f"{ara}\n")
            return True

        with open(LOG_PATH, "r") as f:
            timestamps = [float(line.strip()) for line in f if line.strip()]

        timestamps = [t for t in timestamps if ara - t < 3600]

        if len(timestamps) < MAX_REQUESTS_PER_HOUR and (
            not timestamps or (ara - timestamps[-1]) >= MIN_INTERVAL_SECONDS
        ):
            with open(LOG_PATH, "a") as f:
                f.write(f"{ara}\n")
            return True

        time.sleep(1)
