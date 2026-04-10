from unittest.mock import patch, MagicMock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from music.models import Album, Artista, Canco, Territori
from ranking.models import ConfiguracioGlobal


@pytest.fixture(autouse=True)
def territoris():
    """Create the 3 standard territories for all tests."""
    Territori.objects.get_or_create(codi="CAT", defaults={"nom": "Catalunya"})
    Territori.objects.get_or_create(codi="VAL", defaults={"nom": "País Valencià"})
    Territori.objects.get_or_create(codi="BAL", defaults={"nom": "Illes Balears"})


def _make_legacy_artista(**kwargs):
    """Create a mock LegacyArtista object."""
    defaults = {
        "id_spotify": "spotify_123",
        "nom": "Txarango",
        "nom_spotify": "Txarango",
        "territori": "Catalunya",
        "status": "go",
        "catala": True,
        "localitat": "Navàs",
        "comarca": "Bages",
        "id_viasona": None,
        "font_dades": "spotify",
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_legacy_canco(**kwargs):
    """Create a mock LegacyCanco object."""
    defaults = {
        "id_canco": "track_abc",
        "territori": "cat",
        "titol": "Benvolguts",
        "artista_basat": "spotify_123",
        "album_id": "album_xyz",
        "album_titol": "De mica en mica",
        "album_data": None,
        "album_caratula_url": "https://example.com/cover.jpg",
        "exclosa": False,
    }
    defaults.update(kwargs)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class FakeLegacyQuerySet:
    """Minimal mock for a Django QuerySet used in iterator-based import."""

    def __init__(self, items):
        self._items = items

    def all(self):
        return self

    def filter(self, **kwargs):
        result = self._items
        if "exclosa" in kwargs:
            result = [i for i in result if getattr(i, "exclosa") == kwargs["exclosa"]]
        return FakeLegacyQuerySet(result)

    def count(self):
        return len(self._items)

    def iterator(self):
        return iter(self._items)


@pytest.mark.django_db
class TestImportarLegacyArtistes:
    @patch("ingesta.management.commands.importar_legacy.LegacyArtista")
    def test_territory_mapping(self, mock_model):
        """Catalunya, País Valencià, Balears map to CAT, VAL, BAL."""
        artistes = [
            _make_legacy_artista(id_spotify="sp1", nom="A1", territori="Catalunya"),
            _make_legacy_artista(id_spotify="sp2", nom="A2", territori="País Valencià"),
            _make_legacy_artista(id_spotify="sp3", nom="A3", territori="Balears"),
            _make_legacy_artista(id_spotify="sp4", nom="A4", territori="Illes"),
        ]
        mock_model.objects.all.return_value = FakeLegacyQuerySet(artistes)

        call_command("importar_legacy", "--artistes")

        # Check territory assignments via M2M
        a1 = Artista.objects.get(spotify_id="sp1")
        assert list(a1.territoris.values_list("codi", flat=True)) == ["CAT"]

        a2 = Artista.objects.get(spotify_id="sp2")
        assert list(a2.territoris.values_list("codi", flat=True)) == ["VAL"]

        a3 = Artista.objects.get(spotify_id="sp3")
        assert list(a3.territoris.values_list("codi", flat=True)) == ["BAL"]

        a4 = Artista.objects.get(spotify_id="sp4")
        assert list(a4.territoris.values_list("codi", flat=True)) == ["BAL"]

    @patch("ingesta.management.commands.importar_legacy.LegacyArtista")
    def test_status_mapping(self, mock_model):
        """Only status='go' artists are imported as active."""
        artistes = [
            _make_legacy_artista(id_spotify="sp1", nom="Active", status="go"),
            _make_legacy_artista(id_spotify="sp2", nom="Stopped", status="stop"),
            _make_legacy_artista(id_spotify="sp3", nom="Pending", status="pending"),
        ]
        mock_model.objects.all.return_value = FakeLegacyQuerySet(artistes)

        call_command("importar_legacy", "--artistes")

        assert Artista.objects.count() == 1
        a = Artista.objects.first()
        assert a.nom == "Active"
        assert a.actiu is True
        assert a.aprovat is True

    @patch("ingesta.management.commands.importar_legacy.LegacyArtista")
    def test_skip_altres_territory(self, mock_model):
        """Artists with territori='Altres' are skipped."""
        artistes = [
            _make_legacy_artista(id_spotify="sp1", nom="A1", territori="Altres"),
            _make_legacy_artista(id_spotify="sp2", nom="A2", territori="Catalunya"),
        ]
        mock_model.objects.all.return_value = FakeLegacyQuerySet(artistes)

        call_command("importar_legacy", "--artistes")

        assert Artista.objects.count() == 1
        assert Artista.objects.first().nom == "A2"

    @patch("ingesta.management.commands.importar_legacy.LegacyArtista")
    def test_lastfm_nom_defaults_to_nom(self, mock_model):
        """lastfm_nom is set to nom initially."""
        artistes = [
            _make_legacy_artista(id_spotify="sp1", nom="Zoo"),
        ]
        mock_model.objects.all.return_value = FakeLegacyQuerySet(artistes)

        call_command("importar_legacy", "--artistes")

        a = Artista.objects.first()
        assert a.lastfm_nom == "Zoo"

    @patch("ingesta.management.commands.importar_legacy.LegacyArtista")
    def test_idempotent(self, mock_model):
        """Running twice does not duplicate artists."""
        artistes = [
            _make_legacy_artista(id_spotify="sp1", nom="Zoo"),
        ]
        mock_model.objects.all.return_value = FakeLegacyQuerySet(artistes)

        call_command("importar_legacy", "--artistes")
        call_command("importar_legacy", "--artistes")

        assert Artista.objects.count() == 1

    @patch("ingesta.management.commands.importar_legacy.LegacyArtista")
    def test_dry_run_no_writes(self, mock_model):
        """Dry run does not create any records."""
        artistes = [
            _make_legacy_artista(id_spotify="sp1", nom="Zoo"),
        ]
        mock_model.objects.all.return_value = FakeLegacyQuerySet(artistes)

        call_command("importar_legacy", "--artistes", "--dry-run")

        assert Artista.objects.count() == 0


@pytest.mark.django_db
class TestImportarLegacyCancons:
    def _setup_artista(self):
        """Create a pre-existing artist for track imports."""
        a = Artista.objects.create(
            spotify_id="spotify_123",
            nom="Txarango",
            lastfm_nom="Txarango",
            font_descoberta="legacy",
        )
        a.territoris.set([Territori.objects.get(codi="CAT")])
        return a

    @patch("ingesta.management.commands.importar_legacy.LegacyCanco")
    def test_deduplication(self, mock_model):
        """Same id_canco in 3 territories produces 1 Canco."""
        self._setup_artista()
        cancons = [
            _make_legacy_canco(id_canco="track_1", territori="cat"),
            _make_legacy_canco(id_canco="track_1", territori="pv"),
            _make_legacy_canco(id_canco="track_1", territori="ib"),
        ]
        mock_model.objects.filter.return_value = FakeLegacyQuerySet(cancons)

        call_command("importar_legacy", "--cancons")

        assert Canco.objects.count() == 1

    @patch("ingesta.management.commands.importar_legacy.LegacyCanco")
    def test_skip_no_matching_artist(self, mock_model):
        """Tracks with unknown artista_basat are skipped."""
        self._setup_artista()
        cancons = [
            _make_legacy_canco(id_canco="t1", artista_basat="spotify_123"),
            _make_legacy_canco(id_canco="t2", artista_basat="unknown_artist"),
        ]
        mock_model.objects.filter.return_value = FakeLegacyQuerySet(cancons)

        call_command("importar_legacy", "--cancons")

        assert Canco.objects.count() == 1

    @patch("ingesta.management.commands.importar_legacy.LegacyCanco")
    def test_album_created(self, mock_model):
        """Albums are created from track metadata."""
        self._setup_artista()
        cancons = [
            _make_legacy_canco(
                id_canco="t1",
                album_id="alb_1",
                album_titol="El disc",
            ),
        ]
        mock_model.objects.filter.return_value = FakeLegacyQuerySet(cancons)

        call_command("importar_legacy", "--cancons")

        assert Album.objects.count() == 1
        album = Album.objects.first()
        assert album.nom == "El disc"
        assert album.spotify_id == "alb_1"

    @patch("ingesta.management.commands.importar_legacy.LegacyCanco")
    def test_tracks_from_same_album_share_album(self, mock_model):
        """Two tracks from the same album produce 1 Album."""
        self._setup_artista()
        cancons = [
            _make_legacy_canco(id_canco="t1", album_id="alb_1", album_titol="Disc"),
            _make_legacy_canco(id_canco="t2", album_id="alb_1", album_titol="Disc"),
        ]
        mock_model.objects.filter.return_value = FakeLegacyQuerySet(cancons)

        call_command("importar_legacy", "--cancons")

        assert Album.objects.count() == 1
        assert Canco.objects.count() == 2

    @patch("ingesta.management.commands.importar_legacy.LegacyCanco")
    def test_requires_artistes_first(self, mock_model):
        """Raises CommandError if no legacy artists have been imported."""
        cancons = [_make_legacy_canco()]
        mock_model.objects.filter.return_value = FakeLegacyQuerySet(cancons)

        with pytest.raises(CommandError, match="No artists found"):
            call_command("importar_legacy", "--cancons")


@pytest.mark.django_db
class TestImportarLegacyConfiguracio:
    def test_configuracio_created_with_defaults(self):
        """ConfiguracioGlobal is created with default values."""
        call_command("importar_legacy", "--configuracio")

        config = ConfiguracioGlobal.load()
        assert config.dia_setmana_ranking == 6
        assert float(config.penalitzacio_descens) == 0.025
        assert float(config.suavitat) == 5.0
