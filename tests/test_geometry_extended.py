import pytest
import os
import shutil

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def rc_file(tmp_path):
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config', 'rc.glsl')
    dst = str(tmp_path / "rc.glsl")
    shutil.copy2(src, dst)
    return dst

# ── calc_geometry — MODULES_BOTTOM (bars, graph) ──────────────────────────────

def test_bars_bottom_default():
    """bars domyślnie: dół ekranu, y=-bottom_reserved."""
    from gui.geometry import calc_geometry
    x, y, w, h = calc_geometry("bars", 1600, 900, bottom_reserved=40)
    assert x == 0
    assert y == -40
    assert w == 1600
    assert h == 900

def test_bars_flipped():
    """bars flipped=True: góra ekranu, y=top_reserved."""
    from gui.geometry import calc_geometry
    x, y, w, h = calc_geometry("bars", 1600, 900, bottom_reserved=40,
                                top_reserved=30, flipped=True)
    assert x == 0
    assert y == 30
    assert w == 1600
    assert h == 900

def test_bars_mirror_yx_left():
    """bars mirror_yx=True: lewa strona, x=left_reserved."""
    from gui.geometry import calc_geometry
    x, y, w, h = calc_geometry("bars", 1600, 900, bottom_reserved=0,
                                mirror_yx=True, left_reserved=10)
    assert x == 10
    assert y == 0
    assert w == 1600
    assert h == 900

def test_bars_mirror_yx_flipped_right():
    """bars mirror_yx=True, flipped=True: prawa strona, x=-right_reserved."""
    from gui.geometry import calc_geometry
    x, y, w, h = calc_geometry("bars", 1600, 900, bottom_reserved=0,
                                mirror_yx=True, flipped=True, right_reserved=10)
    assert x == -10
    assert y == 0
    assert w == 1600
    assert h == 900

def test_graph_same_as_bars():
    """graph zachowuje się identycznie jak bars."""
    from gui.geometry import calc_geometry
    bars = calc_geometry("bars",  1600, 900, bottom_reserved=40)
    graph = calc_geometry("graph", 1600, 900, bottom_reserved=40)
    assert bars == graph

def test_bars_zero_reserved():
    """Brak pasków: y=0."""
    from gui.geometry import calc_geometry
    x, y, w, h = calc_geometry("bars", 1600, 900, bottom_reserved=0)
    assert y == 0

# ── calc_geometry — MODULES_CENTERED ─────────────────────────────────────────

def test_circle_ignores_flipped():
    """circle ignoruje flipped — zawsze y=-bottom_reserved."""
    from gui.geometry import calc_geometry
    normal  = calc_geometry("circle", 1600, 900, bottom_reserved=40)
    flipped = calc_geometry("circle", 1600, 900, bottom_reserved=40, flipped=True)
    assert normal == flipped

def test_circle_ignores_mirror_yx():
    """circle ignoruje mirror_yx."""
    from gui.geometry import calc_geometry
    normal   = calc_geometry("circle", 1600, 900, bottom_reserved=40)
    mirrored = calc_geometry("circle", 1600, 900, bottom_reserved=40, mirror_yx=True)
    assert normal == mirrored

def test_wave_bottom_reserved():
    from gui.geometry import calc_geometry
    x, y, w, h = calc_geometry("wave", 1600, 900, bottom_reserved=40)
    assert y == -40
    assert w == 1600
    assert h == 900

def test_radial_centered():
    from gui.geometry import calc_geometry
    x, y, w, h = calc_geometry("radial", 1600, 900, bottom_reserved=0)
    assert x == 0
    assert y == 0

def test_all_modules_return_full_width():
    """Wszystkie moduły zwracają w=screen_w."""
    from gui.geometry import calc_geometry
    from gui.core import GLAVA_MODULES
    for mod in GLAVA_MODULES:
        x, y, w, h = calc_geometry(mod, 1920, 1080, bottom_reserved=40)
        assert w == 1920, f"Moduł {mod}: w={w}, oczekiwano 1920"

def test_all_modules_return_full_height():
    """Wszystkie moduły zwracają h=screen_h."""
    from gui.geometry import calc_geometry
    from gui.core import GLAVA_MODULES
    for mod in GLAVA_MODULES:
        x, y, w, h = calc_geometry(mod, 1920, 1080, bottom_reserved=40)
        assert h == 1080, f"Moduł {mod}: h={h}, oczekiwano 1080"

def test_unknown_module_treated_as_centered():
    """Nieznany moduł traktowany jak MODULES_CENTERED (nie BOTTOM)."""
    from gui.geometry import calc_geometry
    x, y, w, h = calc_geometry("unknown_module", 1600, 900, bottom_reserved=40)
    assert y == -40

# ── read_geometry / write_geometry ────────────────────────────────────────────

def test_read_geometry_from_rc(rc_file):
    """rc.glsl zawiera linię setgeometry — read_geometry zwraca 4-krotkę."""
    from gui.geometry import read_geometry
    result = read_geometry(rc_file)
    assert result is not None
    x, y, w, h = result
    assert isinstance(x, int)
    assert isinstance(y, int)
    assert w > 0
    assert h > 0

def test_write_geometry_roundtrip(rc_file):
    """Zapis i odczyt geometrii daje te same wartości."""
    from gui.geometry import write_geometry, read_geometry
    write_geometry(rc_file, 10, -40, 1600, 900)
    result = read_geometry(rc_file)
    assert result == (10, -40, 1600, 900)

def test_write_geometry_negative_values(rc_file):
    """write_geometry obsługuje ujemne wartości x/y."""
    from gui.geometry import write_geometry, read_geometry
    write_geometry(rc_file, -10, -40, 1600, 900)
    result = read_geometry(rc_file)
    assert result == (-10, -40, 1600, 900)

def test_write_geometry_overwrites(rc_file):
    """Dwukrotny zapis nie duplikuje linii."""
    from gui.geometry import write_geometry, read_geometry
    write_geometry(rc_file, 0, -40, 1600, 900)
    write_geometry(rc_file, 0, -30, 1920, 1080)
    with open(rc_file) as f:
        content = f.read()
    assert content.count("setgeometry") == 1
    assert read_geometry(rc_file) == (0, -30, 1920, 1080)

def test_write_geometry_missing_file(tmp_path):
    """write_geometry zwraca False dla nieistniejącego pliku."""
    from gui.geometry import write_geometry
    result = write_geometry(str(tmp_path / "nonexistent.glsl"), 0, 0, 1600, 900)
    assert result == False

def test_read_geometry_missing_file(tmp_path):
    """read_geometry zwraca None dla nieistniejącego pliku."""
    from gui.geometry import read_geometry
    assert read_geometry(str(tmp_path / "nonexistent.glsl")) is None

def test_read_geometry_no_setgeometry(tmp_path):
    """read_geometry zwraca None gdy brak linii setgeometry."""
    from gui.geometry import read_geometry
    path = str(tmp_path / "rc.glsl")
    with open(path, "w") as f:
        f.write("#request setframerate 60\n")
    assert read_geometry(path) is None

def test_write_read_all_combinations(rc_file):
    """Test różnych kombinacji geometrii dla wszystkich modułów."""
    from gui.geometry import calc_geometry, write_geometry, read_geometry
    from gui.core import GLAVA_MODULES
    screen_w, screen_h = 1600, 900
    bottom_reserved = 40
    for mod in GLAVA_MODULES:
        x, y, w, h = calc_geometry(mod, screen_w, screen_h, bottom_reserved)
        write_geometry(rc_file, x, y, w, h)
        result = read_geometry(rc_file)
        assert result == (x, y, w, h), f"Moduł {mod}: {result} != {(x, y, w, h)}"
