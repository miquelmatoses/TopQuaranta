# Shared constants for the TopQuaranta project.
# Import from here instead of using magic numbers.

DIES_CADUCITAT = 365  # tracks older than this are excluded from ingestion
MAX_POSICIONS_TOP = 40  # top N positions per territory

# Territory codes and display names — single source of truth.
# The canonical data lives in the Territori DB model (music_territori); this
# dict mirrors it for use in templates and Python constants where we want
# display strings without a DB hit.
TERRITORI_NOMS = {
    "PPCC": "Països Catalans",
    "CAT": "Catalunya",
    "VAL": "País Valencià",
    "BAL": "Illes Balears",
    "ALT": "Altres territoris",
    "AND": "Andorra",
    "CNO": "Catalunya del Nord",
    "FRA": "Franja de Ponent",
    "ALG": "L'Alguer",
    "CAR": "El Carxe",
}
# Territories that have a ranking visible on the public site.
TERRITORIS_VALIDS = ("CAT", "VAL", "BAL", "PPCC", "ALT")

# ML classifier thresholds
ML_CLASSE_A_THRESHOLD = 0.7  # confidence >= this → class A
ML_CLASSE_B_THRESHOLD = 0.4  # confidence >= this → class B (below → class C)
MIN_TRAINING_SAMPLES = 20  # minimum HistorialRevisio records to train RF
MIN_NEW_DECISIONS = 5  # new decisions since last recalc to trigger retrain

# API rate limits (seconds between calls)
DEEZER_RATE_LIMIT = 1.0
LASTFM_RATE_LIMIT = 0.2
MAX_API_RETRIES = 3

# Score normalization batch size
SCORE_BATCH_SIZE = 500

# Motius de rebuig — single source of truth
MOTIUS_REBUIG = [
    ("no_catala", "No és en català"),
    ("artista_incorrecte", "El perfil Deezer no és el nostre artista"),
    ("album_incorrecte", "Àlbum incorrecte"),
    ("no_musica", "No és música"),
]
MOTIUS_VALIDS = {m[0] for m in MOTIUS_REBUIG}
