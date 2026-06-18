# =============================================================================
# tests/test_geometry.py
# Testy jednostkowe dla gui/geometry.py
# Pokrywa: calc_geometry (wszystkie 4 tryby), read_geometry, write_geometry,
#          _get_screen_size_xrandr (fallback), get_strut_reserved (fallback)
# Środowiskowo neutralny — subprocess mockowany.
# =============================================================================

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from gui.geometry import (
    calc_geometry,
    read_geometry,
    write_geometry,
    _get_screen_size_xrandr,
    get_strut_reserved,
    MODULES_BOTTOM,
    MODULES_CENTERED,
)

W, H = 1920, 1080


# ---------------------------------------------------------------------------
# calc_geometry — MODULES_BOTTOM (bars, graph)
# ---------------------------------------------------------------------------

class TestCalcGeometryBottom:
    """Tryby dla bars/graph: kombinacje flipped × mirror_yx."""

    def test_default_bottom(self):
        """mirror_yx=False, flipped=False → dół ekranu."""
        x, y, w, h = calc_geometry("bars", W, H, bottom_reserved=40, top_reserved=30)
        assert x == 0
        assert y == -40
        assert w == W
        assert h == H

    def test_flipped_top(self):
        """mirror_yx=False, flipped=True → góra ekranu."""
        x, y, w, h = calc_geometry("bars", W, H,
                                    bottom_reserved=40, top_reserved=30,
                                    flipped=True)
        assert x == 0
        assert y == 30
        assert w == W
        assert h == H

    def test_mirror_yx_left(self):
        """mirror_yx=True, flipped=False → lewa strona."""
        x, y, w, h = calc_geometry("bars", W, H,
                                    bottom_reserved=0, top_reserved=0,
                                    mirror_yx=True,
                                    left_reserved=60, right_reserved=0)
        assert x == 60
        assert y == 0
        assert w == W
        assert h == H

    def test_mirror_yx_flipped_right(self):
        """mirror_yx=True, flipped=True → prawa strona."""
        x, y, w, h = calc_geometry("bars", W, H,
                                    bottom_reserved=0, top_reserved=0,
                                    mirror_yx=True, flipped=True,
                                    left_reserved=0, right_reserved=60)
        assert x == -60
        assert y == 0
        assert w == W
        assert h == H

    def test_graph_same_as_bars(self):
        """graph i bars używają tej samej logiki."""
        bars = calc_geometry("bars",  W, H, 40, 30)
        graph = calc_geometry("graph", W, H, 40, 30)
        assert bars == graph

    def test_zero_reserved(self):
        """Brak pasków → y=0."""
        x, y, w, h = calc_geometry("bars", W, H, bottom_reserved=0, top_reserved=0)
        assert y == 0


# ---------------------------------------------------------------------------
# calc_geometry — MODULES_CENTERED (circle, radial, wave)
# ---------------------------------------------------------------------------

class TestCalcGeometryCentered:
    """Moduły centrowane ignorują flipped i mirror_yx."""

    def test_wave_ignores_flags(self):
        x, y, w, h = calc_geometry("wave", W, H,
                                    bottom_reserved=40, top_reserved=30,
                                    flipped=True, mirror_yx=True)
        assert x == 0
        assert y == -40
        assert w == W
        assert h == H

    def test_circle_centered(self):
        x, y, w, h = calc_geometry("circle", W, H, bottom_reserved=50)
        assert x == 0
        assert y == -50
        assert w == W
        assert h == H

    def test_radial_centered(self):
        x, y, w, h = calc_geometry("radial", W, H, bottom_reserved=0)
        assert y == 0

    def test_unknown_module_treated_as_centered(self):
        """Nieznany moduł trafia do gałęzi 'not in MODULES_BOTTOM'."""
        x, y, w, h = calc_geometry("unknown", W, H, bottom_reserved=30)
        assert x == 0
        assert y == -30


# ---------------------------------------------------------------------------
# Klasyfikacja modułów
# ---------------------------------------------------------------------------

class TestModuleClassification:
    def test_bottom_modules(self):
        assert "bars"  in MODULES_BOTTOM
        assert "graph" in MODULES_BOTTOM

    def test_centered_modules(self):
        assert "circle" in MODULES_CENTERED
        assert "radial" in MODULES_CENTERED
        assert "wave"   in MODULES_CENTERED

    def test_no_overlap(self):
        assert MODULES_BOTTOM & MODULES_CENTERED == set()


# ---------------------------------------------------------------------------
# read_geometry / write_geometry
# ---------------------------------------------------------------------------

@pytest.fixture
def rc_file(tmp_path):
    def _make(content):
        p = tmp_path / "rc.glsl"
        p.write_text(content)
        return str(p)
    return _make


class TestReadGeometry:
    def test_reads_positive_values(self, rc_file):
        path = rc_file("#request setgeometry 0 -40 1920 1080\n")
        result = read_geometry(path)
        assert result == (0, -40, 1920, 1080)

    def test_reads_negative_y(self, rc_file):
        path = rc_file("#request setgeometry 0 -50 1920 1080\n")
        x, y, w, h = read_geometry(path)
        assert y == -50

    def test_reads_negative_x(self, rc_file):
        path = rc_file("#request setgeometry -60 0 1920 1080\n")
        x, y, w, h = read_geometry(path)
        assert x == -60

    def test_returns_none_when_missing(self, rc_file):
        path = rc_file("// brak geometrii\n")
        assert read_geometry(path) is None

    def test_returns_none_on_missing_file(self, tmp_path):
        assert read_geometry(str(tmp_path / "missing.glsl")) is None


class TestWriteGeometry:
    def test_writes_geometry(self, rc_file):
        path = rc_file("#request setgeometry 0 0 1920 1080\n")
        result = write_geometry(path, 0, -40, 1920, 1080)
        assert result is True
        assert read_geometry(path) == (0, -40, 1920, 1080)

    def test_roundtrip(self, rc_file):
        path = rc_file("#request setgeometry 0 0 1920 1080\n")
        write_geometry(path, -60, 30, 1920, 1080)
        assert read_geometry(path) == (-60, 30, 1920, 1080)

    def test_returns_false_on_missing_file(self, tmp_path):
        result = write_geometry(str(tmp_path / "missing.glsl"), 0, 0, 1920, 1080)
        assert result is False

    def test_preserves_other_content(self, rc_file):
        path = rc_file(
            "#request mod bars\n"
            "#request setgeometry 0 0 1920 1080\n"
            "#define SOME_FLAG 1\n"
        )
        write_geometry(path, 0, -40, 1920, 1080)
        content = open(path).read()
        assert "#request mod bars" in content
        assert "#define SOME_FLAG 1" in content

    def test_write_then_read_negative_coords(self, rc_file):
        path = rc_file("#request setgeometry 0 0 1920 1080\n")
        write_geometry(path, -60, -40, 1920, 1080)
        assert read_geometry(path) == (-60, -40, 1920, 1080)


# ---------------------------------------------------------------------------
# _get_screen_size_xrandr — fallback gdy xrandr niedostępny
# ---------------------------------------------------------------------------

class TestGetScreenSizeXrandr:
    def test_returns_fallback_on_exception(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            w, h = _get_screen_size_xrandr()
        assert w == 1600
        assert h == 900

    def test_parses_xrandr_output(self):
        mock = MagicMock()
        mock.stdout = "Screen 0: minimum 8 x 8, current 1920 x 1080, maximum 32767 x 32767"
        with patch("subprocess.run", return_value=mock):
            w, h = _get_screen_size_xrandr()
        assert w == 1920
        assert h == 1080

    def test_returns_fallback_on_no_match(self):
        mock = MagicMock()
        mock.stdout = "no resolution here"
        with patch("subprocess.run", return_value=mock):
            w, h = _get_screen_size_xrandr()
        assert (w, h) == (1600, 900)


# ---------------------------------------------------------------------------
# get_strut_reserved — fallback gdy xprop niedostępny
# ---------------------------------------------------------------------------

class TestGetStrutReserved:
    def test_returns_zeros_on_exception(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = get_strut_reserved()
        assert result == (0, 0, 0, 0)

    def test_returns_zeros_on_empty_client_list(self):
        mock = MagicMock()
        mock.stdout = "_NET_CLIENT_LIST: not set"
        with patch("subprocess.run", return_value=mock):
            result = get_strut_reserved()
        assert result == (0, 0, 0, 0)

    def test_parses_strut_partial(self):
        """Symuluje jedno okno z paskiem 30px na górze."""
        client_list = MagicMock()
        client_list.stdout = "_NET_CLIENT_LIST(WINDOW): 0x1234"

        strut = MagicMock()
        # left=0, right=0, top=30, bottom=0, ...
        strut.stdout = "_NET_WM_STRUT_PARTIAL(CARDINAL) = 0, 0, 30, 0, 0, 0, 0, 0, 0, 1920, 0, 0"

        with patch("subprocess.run", side_effect=[client_list, strut]):
            top, bottom, left, right = get_strut_reserved()

        assert top    == 30
        assert bottom == 0
        assert left   == 0
        assert right  == 0
