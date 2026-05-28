import pytest
import os
import shutil

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def frag_dir(tmp_path, monkeypatch):
    """
    Tworzy strukturę katalogów z szablonami kolorów z config/.
    tmp_path/
      glava/
        graph_colors.frag   (szablon)
        bars_colors.frag
        graph/1.frag        (live frag — tworzony przez write_colors_to_frag)
        bars/1.frag
    Patchuje FLAG_RED i FLAG_MANUAL na ścieżki w tmp_path — w testach
    ~/.config/glava/ nie istnieje (nie wymagamy środowiska produkcyjnego).
    """
    from gui import colors as colors_mod
    glava_dir = tmp_path / "glava"
    glava_dir.mkdir()
    # Patch flag files na tmp_path
    monkeypatch.setattr(colors_mod, "FLAG_RED",    str(tmp_path / "red.shift"))
    monkeypatch.setattr(colors_mod, "FLAG_MANUAL", str(tmp_path / "manual.shift"))
    config_src = os.path.join(os.path.dirname(__file__), '..', 'config')
    for mod in ("graph", "bars", "circle", "wave", "radial"):
        tmpl = os.path.join(config_src, f"{mod}_colors.frag")
        if os.path.exists(tmpl):
            shutil.copy2(tmpl, str(glava_dir / f"{mod}_colors.frag"))
        (glava_dir / mod).mkdir(exist_ok=True)
    return glava_dir

def tmpl_path(frag_dir, mod):
    return str(frag_dir / f"{mod}_colors.frag")

def live_path(frag_dir, mod):
    return str(frag_dir / mod / "1.frag")

COLORS_RGB = {
    "top":    "#ff0000",
    "mid":    "#00ff00",
    "bottom": "#0000ff",
}

# ── hex_to_vec3 / vec3_to_hex ─────────────────────────────────────────────────

def test_hex_to_vec3_black():
    from gui.colors import hex_to_vec3
    assert hex_to_vec3("#000000") == (0.0, 0.0, 0.0)

def test_hex_to_vec3_white():
    from gui.colors import hex_to_vec3
    r, g, b = hex_to_vec3("#ffffff")
    assert abs(r - 1.0) < 0.01
    assert abs(g - 1.0) < 0.01
    assert abs(b - 1.0) < 0.01

def test_hex_to_vec3_red():
    from gui.colors import hex_to_vec3
    r, g, b = hex_to_vec3("#ff0000")
    assert abs(r - 1.0) < 0.01
    assert g == 0.0
    assert b == 0.0

def test_vec3_to_hex_black():
    from gui.colors import vec3_to_hex
    assert vec3_to_hex(0.0, 0.0, 0.0) == "#000000"

def test_vec3_to_hex_white():
    from gui.colors import vec3_to_hex
    assert vec3_to_hex(1.0, 1.0, 1.0) == "#ffffff"

def test_hex_vec3_roundtrip():
    from gui.colors import hex_to_vec3, vec3_to_hex
    for color in ("#ff0000", "#00ff00", "#0000ff", "#aabbcc", "#123456"):
        r, g, b = hex_to_vec3(color)
        result = vec3_to_hex(r, g, b)
        assert result == color, f"{color} → {result}"

# ── read_colors_from_frag ─────────────────────────────────────────────────────

def test_read_colors_from_frag_basic(frag_dir):
    from gui.colors import read_colors_from_frag
    result = read_colors_from_frag(tmpl_path(frag_dir, "graph"))
    assert result is not None
    assert "top" in result
    assert "mid" in result
    assert "bottom" in result

def test_read_colors_from_frag_hex_format(frag_dir):
    from gui.colors import read_colors_from_frag
    result = read_colors_from_frag(tmpl_path(frag_dir, "graph"))
    for key in ("top", "mid", "bottom"):
        assert result[key].startswith("#")
        assert len(result[key]) == 7

def test_read_colors_from_frag_missing_file(tmp_path):
    from gui.colors import read_colors_from_frag
    assert read_colors_from_frag(str(tmp_path / "nonexistent.frag")) is None

def test_read_colors_from_frag_incomplete(tmp_path):
    """Plik z tylko dwoma kolorami zwraca None."""
    from gui.colors import read_colors_from_frag
    path = str(tmp_path / "partial.frag")
    with open(path, "w") as f:
        f.write("vec3 top = vec3(1.0, 0.0, 0.0);\n")
        f.write("vec3 mid = vec3(0.0, 1.0, 0.0);\n")
        # brak bottom
    assert read_colors_from_frag(path) is None

# ── write_colors_to_frag ──────────────────────────────────────────────────────

def test_write_colors_creates_live_frag(frag_dir):
    from gui.colors import write_colors_to_frag
    ok, err = write_colors_to_frag(
        "graph", COLORS_RGB,
        tmpl_path=tmpl_path(frag_dir, "graph"),
        live_path=live_path(frag_dir, "graph"),
    )
    assert ok == True
    assert err == ""
    assert os.path.exists(live_path(frag_dir, "graph"))

def test_write_colors_roundtrip(frag_dir):
    """Zapis i odczyt kolorów daje te same wartości."""
    from gui.colors import write_colors_to_frag, read_colors_from_frag
    write_colors_to_frag(
        "graph", COLORS_RGB,
        tmpl_path=tmpl_path(frag_dir, "graph"),
        live_path=live_path(frag_dir, "graph"),
    )
    result = read_colors_from_frag(live_path(frag_dir, "graph"))
    assert result is not None
    assert result["top"]    == COLORS_RGB["top"]
    assert result["mid"]    == COLORS_RGB["mid"]
    assert result["bottom"] == COLORS_RGB["bottom"]

def test_write_colors_missing_template(frag_dir):
    from gui.colors import write_colors_to_frag
    ok, err = write_colors_to_frag(
        "graph", COLORS_RGB,
        tmpl_path=str(frag_dir / "nonexistent_colors.frag"),
        live_path=live_path(frag_dir, "graph"),
    )
    assert ok == False
    assert "Brak szablonu" in err

def test_write_colors_all_modules(frag_dir):
    """write_colors_to_frag działa dla wszystkich modułów które mają szablon."""
    from gui.colors import write_colors_to_frag, read_colors_from_frag
    from gui.core import GLAVA_MODULES
    for mod in GLAVA_MODULES:
        tp = tmpl_path(frag_dir, mod)
        lp = live_path(frag_dir, mod)
        if not os.path.exists(tp):
            continue
        ok, err = write_colors_to_frag(mod, COLORS_RGB, tmpl_path=tp, live_path=lp)
        assert ok == True, f"Moduł {mod}: {err}"
        result = read_colors_from_frag(lp)
        assert result is not None, f"Moduł {mod}: brak kolorów w live frag"

# ── shader_supports_hsv ───────────────────────────────────────────────────────

def test_shader_supports_hsv_graph(frag_dir):
    """graph_colors.frag zawiera #define HSV_MODE."""
    from gui.colors import shader_supports_hsv
    assert shader_supports_hsv(
        "graph",
        tmpl_path=tmpl_path(frag_dir, "graph"),
        live_path=live_path(frag_dir, "graph"),
    ) == True

def test_shader_supports_hsv_missing_file(tmp_path):
    from gui.colors import shader_supports_hsv
    assert shader_supports_hsv(
        "graph",
        live_path=str(tmp_path / "nonexistent.frag"),
        tmpl_path=str(tmp_path / "nonexistent_tmpl.frag"),
    ) == False

def test_shader_supports_hsv_no_define(tmp_path):
    from gui.colors import shader_supports_hsv
    path = str(tmp_path / "test.frag")
    with open(path, "w") as f:
        f.write("vec3 top = vec3(1.0, 0.0, 0.0);\n")
    assert shader_supports_hsv("graph", live_path=path, tmpl_path=path) == False

# ── set_gradient_mode ─────────────────────────────────────────────────────────

def test_set_gradient_mode_hsv(frag_dir):
    from gui.colors import write_colors_to_frag, set_gradient_mode
    lp = live_path(frag_dir, "graph")
    tp = tmpl_path(frag_dir, "graph")
    write_colors_to_frag("graph", COLORS_RGB, tmpl_path=tp, live_path=lp)
    set_gradient_mode("graph", "hsv", live_path=lp, tmpl_path=tp)
    with open(lp) as f:
        content = f.read()
    assert "#define HSV_MODE 1" in content

def test_set_gradient_mode_rgb(frag_dir):
    from gui.colors import write_colors_to_frag, set_gradient_mode
    lp = live_path(frag_dir, "graph")
    tp = tmpl_path(frag_dir, "graph")
    write_colors_to_frag("graph", COLORS_RGB, tmpl_path=tp, live_path=lp)
    set_gradient_mode("graph", "rgb", live_path=lp, tmpl_path=tp)
    with open(lp) as f:
        content = f.read()
    assert "#define HSV_MODE 0" in content

def test_set_gradient_mode_missing_file(tmp_path):
    """set_gradient_mode nie crashuje przy brakującym pliku."""
    from gui.colors import set_gradient_mode
    set_gradient_mode(
        "graph", "hsv",
        live_path=str(tmp_path / "nonexistent.frag"),
        tmpl_path=str(tmp_path / "nonexistent_tmpl.frag"),
    )

def test_write_colors_sets_hsv_mode(frag_dir):
    from gui.colors import write_colors_to_frag
    lp = live_path(frag_dir, "graph")
    tp = tmpl_path(frag_dir, "graph")
    write_colors_to_frag("graph", COLORS_RGB, gradient_mode="hsv", tmpl_path=tp, live_path=lp)
    with open(lp) as f:
        content = f.read()
    assert "#define HSV_MODE 1" in content

def test_write_colors_sets_rgb_mode(frag_dir):
    from gui.colors import write_colors_to_frag
    lp = live_path(frag_dir, "graph")
    tp = tmpl_path(frag_dir, "graph")
    write_colors_to_frag("graph", COLORS_RGB, gradient_mode="rgb", tmpl_path=tp, live_path=lp)
    with open(lp) as f:
        content = f.read()
    assert "#define HSV_MODE 0" in content
