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

    if artista.spotify_id:
        score += 0.3
        raons.append("Artista al legacy (curado)")

    if artista.deezer_nb_fan and artista.deezer_nb_fan > 50000:
        score -= 0.3
        raons.append(f"{artista.deezer_nb_fan:,} fans Deezer")

    if artista.deezer_nb_album and artista.deezer_nb_album > 20:
        score -= 0.2
        raons.append(f"{artista.deezer_nb_album} àlbums Deezer")

    if len(artista.nom) <= 3:
        score -= 0.2
        raons.append(f"Nom curt ({len(artista.nom)} chars)")

    if artista.deezer_nom_similitud is not None:
        if artista.deezer_nom_similitud < 0.6:
            score -= 0.3
            raons.append(f"Baixa similitud nom ({artista.deezer_nom_similitud:.2f})")
        elif artista.deezer_nom_similitud > 0.9:
            score += 0.2
            raons.append(f"Alta similitud nom ({artista.deezer_nom_similitud:.2f})")

    if (canco.isrc or "").startswith("ES"):
        score += 0.2
        raons.append("ISRC espanyol")

    total = HistorialRevisio.objects.filter(artista_nom=artista.nom).count()
    rebutjades = HistorialRevisio.objects.filter(
        artista_nom=artista.nom, decisio="rebutjada"
    ).count()
    if total >= 3:
        ratio = rebutjades / total
        if ratio > 0.7:
            score -= 0.3
            raons.append(f"Historial: {ratio:.0%} rebutjades")
        elif ratio < 0.3:
            score += 0.2
            raons.append(f"Historial: {ratio:.0%} rebutjades")

    score = max(0.0, min(1.0, score))
    if score >= 0.65:
        classe = "A"
    elif score >= 0.35:
        classe = "B"
    else:
        classe = "C"

    return {"classe": classe, "confiança": round(score, 2), "raons": raons}
