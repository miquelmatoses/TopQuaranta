from wagtail import blocks
from django.db.models import F


class CarouselBlock(blocks.StructBlock):
    section_title = blocks.CharBlock(label="Títol de secció", required=True)
    source = blocks.ChoiceBlock(
        label="Font",
        choices=[("albums", "Àlbums"), ("songs", "Cançons"), ("artists", "Artistes")],
    )
    order = blocks.CharBlock(
        label="Ordenació",
        required=False,
        help_text="Clau d'ordenació permesa (p.ex. release_desc / release_asc).",
    )
    limit = blocks.IntegerBlock(
        label="Número d’elements", default=12, min_value=1, max_value=100
    )
    # Filtres opcionals
    artist_id = blocks.CharBlock(
        label="Filtra per Artist ID (Spotify)",
        required=False,
        help_text="Per a Àlbums o Cançons",
    )
    album_id = blocks.CharBlock(
        label="Filtra per Album ID (Spotify)", required=False, help_text="Només Cançons"
    )
    subtitle_kind = blocks.ChoiceBlock(
        label="Subtítol a mostrar",
        required=False,
        choices=[
            ("", "—"),
            ("artist_names", "Noms d’artista(s)"),
            ("popularity", "Popularitat (només cançons)"),
            ("followers", "Followers (només artistes)"),
        ],
    )

    def get_context(self, value, parent_context=None):
        ctx = super().get_context(value, parent_context)
        source = (value.get("source") or "").strip()
        order = (value.get("order") or "").strip().lower()
        limit = value.get("limit") or 12

        # Per compatibilitzar amb la plantilla actual (que usava self.heading):
        # afegim una clau 'heading' a la StructValue.
        try:
            value["heading"] = value.get("section_title")
        except Exception:
            pass

        # Default: llista buida
        ctx["albums"] = []

        if source == "albums":
            from .models import CmsAlbum

            qs = CmsAlbum.objects.all()
            if value.get("artist_id"):
                qs = qs.filter(artist_ids__contains=[value["artist_id"]])

            # Ordenació
            if order == "release_desc":
                qs = qs.order_by(F("release_date").desc(nulls_last=True), "name")
            elif order == "release_asc":
                qs = qs.order_by(F("release_date").asc(nulls_last=True), "name")
            else:
                qs = qs.order_by(F("release_date").desc(nulls_last=True), "name")

            qs = qs[:limit]

            # Adaptem camps a la plantilla album_grid.html
            albums = []
            for a in qs:
                artist_name = getattr(a, "artist_names_str", None)
                if not artist_name and getattr(a, "artist_names", None):
                    try:
                        artist_name = ", ".join([x for x in a.artist_names if x])
                    except Exception:
                        artist_name = None
                albums.append(
                    {
                        "id": a.id,
                        "name": a.name,
                        "image_url": a.image_url,
                        "artist_name": artist_name,
                        "release_date": a.release_date,
                        "href": f"/music/albums/{a.id}/",
                    }
                )
            ctx["albums"] = albums

        elif source == "songs":
            # Reutilitza el grid d'àlbums per a mostrar cançons més populars
            from .models import CmsAlbum, CmsSong

            qs = CmsSong.objects.all()

            # Filtres opcionals
            artist_id = (value.get("artist_id") or "").strip()
            album_id = (value.get("album_id") or "").strip()
            if artist_id:
                qs = qs.filter(artist_ids__contains=[artist_id])
            if album_id:
                qs = qs.filter(album_id=album_id)

            # Ordenació: pop_desc (defecte), pop_asc, name_asc
            if order == "pop_asc":
                qs = qs.order_by(F("popularity").asc(nulls_last=True), "name")
            elif order == "name_asc":
                qs = qs.order_by("name")
            else:
                qs = qs.order_by(F("popularity").desc(nulls_last=True), "name")

            qs = qs[:limit]

            # Map de caràtules d'àlbum per a les cançons seleccionades
            album_ids = list({s.album_id for s in qs if s.album_id})
            album_map = {
                a.id: a.image_url for a in CmsAlbum.objects.filter(id__in=album_ids)
            }

            subtitle_kind = (value.get("subtitle_kind") or "").strip()
            albums = []
            for s in qs:
                # Subtítol segons configuració del bloc
                if subtitle_kind == "popularity":
                    artist_name = (
                        f"pop {s.popularity}" if s.popularity is not None else ""
                    )
                elif subtitle_kind == "artist_names":
                    artist_name = s.artist_names_str or ""
                else:
                    # per defecte: noms d'artista si n'hi ha
                    artist_name = s.artist_names_str or ""

                albums.append(
                    {
                        "id": s.id,
                        "name": s.name,  # el grid mostrarà el títol de la cançó
                        "image_url": album_map.get(s.album_id),  # caràtula de l'àlbum
                        "artist_name": artist_name,
                        "release_date": None,  # no s'usa per a cançons en el grid
                        "href": f"/music/songs/{s.id}/",
                    }
                )
            ctx["albums"] = albums

        elif source == "artists":
            # Opcional: carrusel d'artistes (usa el mateix grid)
            from .models import CmsArtista

            qs = CmsArtista.objects.filter(live=True)

            # Ordenació: followers_desc (defecte), followers_asc, pop_desc, pop_asc, name_asc
            if order == "followers_asc":
                qs = qs.order_by(F("followers").asc(nulls_last=True), "nom")
            elif order == "pop_desc":
                qs = qs.order_by(F("popularitat").desc(nulls_last=True), "nom")
            elif order == "pop_asc":
                qs = qs.order_by(F("popularitat").asc(nulls_last=True), "nom")
            elif order == "name_asc":
                qs = qs.order_by("nom")
            else:
                qs = qs.order_by(F("followers").desc(nulls_last=True), "nom")

            qs = qs[:limit]

            subtitle_kind = (value.get("subtitle_kind") or "").strip()
            albums = []
            for ar in qs:
                if subtitle_kind == "followers":
                    artist_name = str(ar.followers) if ar.followers is not None else ""
                else:
                    # per defecte: localitat (comarca) si està disponible
                    artist_name = (
                        f"{ar.localitat} ({ar.comarca})" if ar.localitat else ""
                    )

                albums.append(
                    {
                        "id": ar.id_spotify,
                        "name": ar.nom,
                        "image_url": ar.imatge_url,
                        "artist_name": artist_name,
                        "release_date": None,
                        "href": f"/music/artists/{ar.id_spotify}/",
                    }
                )
            ctx["albums"] = albums

        return ctx

    class Meta:
        template = "blocks/album_grid.html"
        icon = "placeholder"
        label = "Carrusel (Nadiu)"
