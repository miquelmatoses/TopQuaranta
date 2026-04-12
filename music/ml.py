"""
Heuristic pre-classifier for track verification.

Calibrated 2026-04-12 from 120 real decisions. Key findings:

  Signal                  | Rejection rate | Observation
  ------------------------|----------------|-------------------------------------------
  ISRC prefix ES          |           14%  | Strong approval signal
  ISRC prefix QT/QM/QZ   |           80%  | Digital distributors, mostly non-Catalan
  ISRC prefix other       |           87%  | International, almost always reject
  Name length 4-6         |           97%  | Short names = generic = wrong Deezer match
  Name length 7+          |           51%  | Coin-flip, need other signals
  Name length 1-3         |            -   | No data yet (0 decisions)
  deezer_nb_fan           |       varies   | >50K fans = likely international
  deezer_nb_album         |       varies   | >20 albums = likely international
  deezer_nom_similitud    |       varies   | <0.5 = bad match
  spotify_id (legacy)     |      uniform   | All artists have it — useless as signal

  Top rejection reasons: no_catala (29), album_incorrecte (28), artista_incorrecte (19)
"""

import logging
import os
import time

from django.db.models import QuerySet

logger = logging.getLogger(__name__)

LAST_RECALC_FILE = "/tmp/tq_last_ml_recalc"
MIN_NEW_DECISIONS = 5


def pre_classificar(canco) -> dict:
    """
    Heuristic pre-classification for track verification.
    Returns {'classe': 'A'|'B'|'C', 'confiança': float, 'raons': list[str]}
      A = probably valid (approve)
      B = uncertain (manual review)
      C = probably reject
    """
    from music.models import HistorialRevisio

    raons = []
    score = 0.5
    artista = canco.artista
    isrc = canco.isrc or ""

    # --- ISRC prefix (strongest signal, 120 decisions) ---
    isrc_prefix = isrc[:2].upper() if len(isrc) >= 2 else ""
    if isrc_prefix == "ES":
        score += 0.3
        raons.append("ISRC espanyol (14% rebuig)")
    elif isrc_prefix in ("QT", "QM", "QZ"):
        score -= 0.25
        raons.append(f"ISRC distrib. digital ({isrc_prefix}, 80% rebuig)")
    elif isrc_prefix:
        score -= 0.3
        raons.append(f"ISRC internacional ({isrc_prefix}, 87% rebuig)")

    # --- Artist name length (4-6 chars → 97% rejection) ---
    nom_len = len(artista.nom)
    if nom_len <= 3:
        score -= 0.3
        raons.append(f"Nom molt curt ({nom_len} chars)")
    elif nom_len <= 6:
        score -= 0.25
        raons.append(f"Nom curt ({nom_len} chars, 97% rebuig)")

    # --- Deezer metadata ---
    if artista.deezer_nb_fan is not None:
        if artista.deezer_nb_fan > 100000:
            score -= 0.35
            raons.append(f"{artista.deezer_nb_fan:,} fans Deezer (molt probable internacional)")
        elif artista.deezer_nb_fan > 50000:
            score -= 0.25
            raons.append(f"{artista.deezer_nb_fan:,} fans Deezer")
        elif artista.deezer_nb_fan < 1000:
            score += 0.1
            raons.append(f"{artista.deezer_nb_fan:,} fans Deezer (petit, bon senyal)")

    if artista.deezer_nb_album is not None:
        if artista.deezer_nb_album > 30:
            score -= 0.25
            raons.append(f"{artista.deezer_nb_album} àlbums Deezer (prolífic)")
        elif artista.deezer_nb_album > 20:
            score -= 0.15
            raons.append(f"{artista.deezer_nb_album} àlbums Deezer")

    # --- Deezer name similarity ---
    if artista.deezer_nom_similitud is not None:
        if artista.deezer_nom_similitud < 0.5:
            score -= 0.3
            raons.append(f"Baixa similitud nom ({artista.deezer_nom_similitud:.2f})")
        elif artista.deezer_nom_similitud < 0.7:
            score -= 0.15
            raons.append(f"Similitud nom moderada ({artista.deezer_nom_similitud:.2f})")
        elif artista.deezer_nom_similitud >= 0.95:
            score += 0.15
            raons.append(f"Alta similitud nom ({artista.deezer_nom_similitud:.2f})")

    # --- Rejection history (fires at 3+ decisions) ---
    total_hist = HistorialRevisio.objects.filter(artista_nom=artista.nom).count()
    if total_hist >= 3:
        rebutjades = HistorialRevisio.objects.filter(
            artista_nom=artista.nom, decisio="rebutjada"
        ).count()
        ratio = rebutjades / total_hist
        if ratio > 0.8:
            score -= 0.35
            raons.append(f"Historial: {ratio:.0%} rebutjades ({rebutjades}/{total_hist})")
        elif ratio > 0.5:
            score -= 0.2
            raons.append(f"Historial: {ratio:.0%} rebutjades ({rebutjades}/{total_hist})")
        elif ratio < 0.2:
            score += 0.2
            raons.append(f"Historial: {ratio:.0%} rebutjades ({rebutjades}/{total_hist})")

    score = max(0.0, min(1.0, score))
    if score >= 0.65:
        classe = "A"
    elif score >= 0.35:
        classe = "B"
    else:
        classe = "C"

    return {"classe": classe, "confiança": round(score, 2), "raons": raons}


def classificar_i_guardar(canco) -> None:
    """Compute ML classification and save to the canco's db fields."""
    result = pre_classificar(canco)
    canco.ml_classe = result["classe"]
    canco.ml_confianca = result["confiança"]
    canco.save(update_fields=["ml_classe", "ml_confianca"])


def recalcular_ml(qs: QuerySet | None = None, limit: int | None = None) -> int:
    """
    Recalculate ml_classe and ml_confianca for unverified cancons.
    Returns number of cancons updated.
    """
    from music.models import Canco

    if qs is None:
        qs = Canco.objects.filter(verificada=False).select_related("artista")

    if limit:
        qs = qs[:limit]

    updated = 0
    for canco in qs.iterator() if not limit else qs:
        result = pre_classificar(canco)
        canco.ml_classe = result["classe"]
        canco.ml_confianca = result["confiança"]
        canco.save(update_fields=["ml_classe", "ml_confianca"])
        updated += 1

    # Update timestamp
    try:
        with open(LAST_RECALC_FILE, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass

    logger.info("ML recalculated for %d cancons", updated)
    return updated


def recalcular_ml_si_cal() -> int:
    """
    Recalculate ML if there have been ≥5 new decisions since last recalc.
    Returns number of cancons updated, or 0 if skipped.
    """
    from music.models import HistorialRevisio

    # Read last recalc timestamp
    last_recalc = 0.0
    try:
        with open(LAST_RECALC_FILE) as f:
            last_recalc = float(f.read().strip())
    except (OSError, ValueError):
        pass

    from django.utils import timezone
    from datetime import datetime

    last_dt = datetime.fromtimestamp(last_recalc, tz=timezone.utc)
    new_decisions = HistorialRevisio.objects.filter(created_at__gt=last_dt).count()

    if new_decisions < MIN_NEW_DECISIONS:
        return 0

    logger.info(
        "ML recalc triggered: %d new decisions since last recalc", new_decisions
    )
    return recalcular_ml()
