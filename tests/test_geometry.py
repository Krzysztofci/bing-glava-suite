import pytest
from gui.geometry import calc_geometry

SW, SH = 1600, 900
BOTTOM, TOP = 40, 0

def test_bars_default_width():
    """bars — pełna szerokość ekranu."""
    x, y, w, h = calc_geometry("bars", SW, SH, BOTTOM, TOP)
    assert w == SW
    assert x == 0

def test_bars_default_height():
    """bars — pełna wysokość ekranu (GLava sam przycina)."""
    x, y, w, h = calc_geometry("bars", SW, SH, BOTTOM, TOP)
    assert h == SH

def test_bars_y_offset():
    """bars — y = -bottom_reserved (korekcja dla GLava fullscreen)."""
    x, y, w, h = calc_geometry("bars", SW, SH, BOTTOM, TOP)
    assert y == -BOTTOM

def test_bars_flipped_y():
    """bars z flip=True — y = TOP (góra ekranu)."""
    x, y, w, h = calc_geometry("bars", SW, SH, BOTTOM, TOP, flipped=True)
    assert y == TOP

def test_graph_default():
    x, y, w, h = calc_geometry("graph", SW, SH, BOTTOM, TOP)
    assert w == SW
    assert x == 0

def test_wave_default():
    x, y, w, h = calc_geometry("wave", SW, SH, BOTTOM, TOP)
    assert w == SW

def test_all_modules_positive_dimensions():
    """Wszystkie moduły zwracają dodatnie wymiary."""
    for mod in ("bars", "circle", "graph", "wave", "radial"):
        x, y, w, h = calc_geometry(mod, SW, SH, BOTTOM, TOP)
        assert w > 0, f"{mod}: w={w}"
        assert h > 0, f"{mod}: h={h}"

def test_all_modules_consistent_size():
    """Wszystkie moduły zwracają ten sam rozmiar (fullscreen z korekcją Y)."""
    results = {}
    for mod in ("bars", "circle", "graph", "wave", "radial"):
        results[mod] = calc_geometry(mod, SW, SH, BOTTOM, TOP)
    w0, h0 = results["bars"][2], results["bars"][3]
    for mod, (x, y, w, h) in results.items():
        assert w == w0, f"{mod}: w={w} != bars w={w0}"
        assert h == h0, f"{mod}: h={h} != bars h={h0}"
