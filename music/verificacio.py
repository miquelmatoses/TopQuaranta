from music.models import Canco, HistorialRevisio


def crear_historial(canco: Canco, decisio: str, motiu: str) -> HistorialRevisio:
    """
    Capture a snapshot of the canco and create an HistorialRevisio record.
    Must be called BEFORE deleting or modifying the canco.
    """
    artista = canco.artista
    territoris = ",".join(artista.territoris.values_list("codi", flat=True))
    isrc = canco.isrc or ""

    return HistorialRevisio.objects.create(
        canco_deezer_id=canco.deezer_id,
        canco_spotify_id=canco.spotify_id or "",
        canco_isrc=isrc,
        canco_nom=canco.nom,
        artista_nom=artista.nom,
        artista_territori=territoris,
        album_nom=canco.album.nom if canco.album_id else "",
        data_llancament=canco.data_llancament,
        isrc_prefix=isrc[:2] if len(isrc) >= 2 else "",
        artista_deezer_id=artista.deezer_id,
        artista_deezer_nb_fan=artista.deezer_nb_fan,
        artista_deezer_nb_album=artista.deezer_nb_album,
        artista_nom_deezer=artista.deezer_nom,
        artista_nom_similitud=artista.deezer_nom_similitud,
        decisio=decisio,
        motiu=motiu,
    )
