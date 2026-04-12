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
  deezer_nb_fan           |            -   | All NULL — backfill pending
  deezer_nb_album         |            -   | All NULL — backfill pending
  deezer_nom_similitud    |            -   | All NULL — backfill pending
  spotify_id (legacy)     |      uniform   | All artists have it — useless as signal

  Top rejection reasons: no_catala (29), album_incorrecte (28), artista_incorrecte (19)

Previous calibration problems:
  - spotify_id bonus (+0.3) fired for all artists → everything shifted to A
  - Non-ES ISRC had no penalty → false positives passed through
  - Starting score 0.5 + legacy bonus 0.3 = 0.8 base was too high
"""

from music.models import Canco, HistorialRevisio


def pre_classificar(canco: Canco) -> dict:
    """
    Heuristic pre-classification for track verification.
    Returns {'classe': 'A'|'B'|'C', 'confiança': float, 'raons': list[str]}
      A = probably valid (approve)
      B = uncertain (manual review)
      C = probably reject
    """
    raons = []
    score = 0.5
    artista = canco.artista
    isrc = canco.isrc or ""

    # --- ISRC prefix (strongest signal, 120 decisions) ---
    # ES → 14% rejection. QT/QM/QZ → 80%. Other → 87%.
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

    # --- Deezer metadata (will activate after backfill) ---
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
