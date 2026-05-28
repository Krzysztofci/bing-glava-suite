# =============================================================================
# tests/test_colors_wallpaper.py
# Testy extract_colors_from_wallpaper i apply_colors_from_wallpaper.
# =============================================================================
import pytest
import os
import glob
import shutil

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def red_wallpaper(tmp_path):
    """Jednolicie czerwony obrazek 100x100."""
    try:
        from PIL import Image
        img = Image.new("RGB", (100, 100), color=(220, 30, 30))
        path = str(tmp_path / "red.jpg")
        img.save(path)
        return path
    except ImportError:
        pytest.skip("PIL nie jest zainstalowane")

@pytest.fixture
def tricolor_wallpaper(tmp_path):
    """
    Obrazek z trzema wyraźnymi kolorami — górna, środkowa, dolna trzecia.
    Czarny / szary / biały — łatwe do odróżnienia przez KMeans.
    """
    try:
        from PIL import Image
        img = Image.new("RGB", (300, 300))
        for y in range(300):
            for x in range(300):
                if y < 100:
                    img.putpixel((x, y), (10, 10, 10))     # prawie czarny
                elif y < 200:
                    img.putpixel((x, y), (128, 128, 128))  # szary
                else:
                    img.putpixel((x, y), (240, 240, 240))  # prawie biały
        path = str(tmp_path / "tricolor.jpg")
        img.save(path)
        return path
    except ImportError:
        pytest.skip("PIL nie jest zainstalowane")

@pytest.fixture
def frag_instance(tmp_path, monkeypatch):
    """
    GlavaInstance z szablonami kolorów i plikami GLSL.
    Wywołuje create() żeby zbudować pełną strukturę katalogów instancji,
    następnie kopiuje szablony kolorów do katalogu instancji.
    """
    from gui import instance as inst_mod, colors as colors_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))
    monkeypatch.setattr(colors_mod, "FLAG_RED",    str(tmp_path / "red.shift"))
    monkeypatch.setattr(colors_mod, "FLAG_MANUAL", str(tmp_path / "manual.shift"))

    # Przygotuj szablon ~/.config/glava z plikami GLSL
    glava_tmpl = tmp_path / ".config" / "glava"
    glava_tmpl.mkdir(parents=True)
    src_glsl = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    for f in glob.glob(os.path.join(src_glsl, "*.glsl")):
        shutil.copy2(f, str(glava_tmpl))

    # Utwórz instancję — create() skopiuje pliki z szablonu
    inst = inst_mod.GlavaInstance(0, home=str(tmp_path))
    inst.create()

    # Skopiuj szablony kolorów i utwórz katalogi shaderów
    src_config = os.path.join(os.path.dirname(__file__), '..', 'config')
    for mod in ("graph", "bars", "circle", "wave", "radial"):
        mod_dir = os.path.join(inst.glava_dir, mod)
        os.makedirs(mod_dir, exist_ok=True)
        tmpl = os.path.join(src_config, f"{mod}_colors.frag")
        if os.path.exists(tmpl):
            shutil.copy2(tmpl, os.path.join(inst.glava_dir, f"{mod}_colors.frag"))

    return inst


# ── extract_colors_from_wallpaper ─────────────────────────────────────────────

def test_extract_returns_dict(tricolor_wallpaper):
    from gui.colors import extract_colors_from_wallpaper
    result = extract_colors_from_wallpaper(tricolor_wallpaper)
    assert result is not None
    assert isinstance(result, dict)

def test_extract_has_three_keys(tricolor_wallpaper):
    from gui.colors import extract_colors_from_wallpaper
    result = extract_colors_from_wallpaper(tricolor_wallpaper)
    assert set(result.keys()) == {"top", "mid", "bottom"}

def test_extract_hex_format(tricolor_wallpaper):
    """Wszystkie wartości są w formacie #rrggbb."""
    from gui.colors import extract_colors_from_wallpaper
    result = extract_colors_from_wallpaper(tricolor_wallpaper)
    for key, val in result.items():
        assert val.startswith("#"), f"{key}: {val} nie zaczyna się od #"
        assert len(val) == 7, f"{key}: {val} ma złą długość"

def test_extract_three_distinct_colors(tricolor_wallpaper):
    """Trzy strefy kolorów dają trzy różne kolory."""
    from gui.colors import extract_colors_from_wallpaper
    result = extract_colors_from_wallpaper(tricolor_wallpaper)
    colors = list(result.values())
    assert len(set(colors)) == 3, f"Oczekiwano 3 różnych kolorów: {colors}"

def test_extract_missing_file():
    from gui.colors import extract_colors_from_wallpaper
    result = extract_colors_from_wallpaper("/nonexistent/path/wallpaper.jpg")
    assert result is None

def test_extract_invalid_file(tmp_path):
    """Uszkodzony plik zwraca None."""
    from gui.colors import extract_colors_from_wallpaper
    bad = str(tmp_path / "bad.jpg")
    with open(bad, "w") as f:
        f.write("not an image")
    result = extract_colors_from_wallpaper(bad)
    assert result is None

def test_extract_brightness_order(tricolor_wallpaper):
    """
    KMeans sortuje kolory po jasności — bottom najciemniejszy, top najjaśniejszy.
    """
    from gui.colors import extract_colors_from_wallpaper, hex_to_vec3
    result = extract_colors_from_wallpaper(tricolor_wallpaper)
    bottom_brightness = sum(hex_to_vec3(result["bottom"]))
    top_brightness    = sum(hex_to_vec3(result["top"]))
    assert bottom_brightness < top_brightness, \
        f"bottom ({result['bottom']}) powinien być ciemniejszy niż top ({result['top']})"


# ── apply_colors_from_wallpaper ───────────────────────────────────────────────

def test_apply_returns_colors_and_errors(tricolor_wallpaper, frag_instance,
                                         monkeypatch):
    """apply_colors_from_wallpaper zwraca (colors_dict, errors_list)."""
    from gui import glava as glava_mod
    monkeypatch.setattr(glava_mod, "glava_restart_instance",
                        lambda **kw: None)
    from gui.colors import apply_colors_from_wallpaper
    colors, errors = apply_colors_from_wallpaper(
        tricolor_wallpaper,
        instances={0: frag_instance},
        inst_modules={0: "graph"},
    )
    assert colors is not None
    assert isinstance(errors, list)

def test_apply_writes_colors_to_frag(tricolor_wallpaper, frag_instance,
                                      monkeypatch):
    """apply_colors_from_wallpaper zapisuje kolory do live frag modułu."""
    from gui import glava as glava_mod
    monkeypatch.setattr(glava_mod, "glava_restart_instance",
                        lambda **kw: None)
    from gui.colors import apply_colors_from_wallpaper, read_colors_from_frag
    apply_colors_from_wallpaper(
        tricolor_wallpaper,
        instances={0: frag_instance},
        inst_modules={0: "graph"},
    )
    live = frag_instance.module_frag("graph")
    result = read_colors_from_frag(live)
    assert result is not None
    assert set(result.keys()) == {"top", "mid", "bottom"}

def test_apply_calls_after_fn(tricolor_wallpaper, frag_instance, monkeypatch):
    """apply_colors_from_wallpaper wywołuje after_fn dla każdej instancji."""
    from gui import glava as glava_mod
    monkeypatch.setattr(glava_mod, "glava_restart_instance",
                        lambda **kw: None)
    called = []
    from gui.colors import apply_colors_from_wallpaper
    apply_colors_from_wallpaper(
        tricolor_wallpaper,
        instances={0: frag_instance},
        inst_modules={0: "graph"},
        after_fn=lambda iid, inst, mod: called.append(iid),
    )
    assert 0 in called

def test_apply_missing_wallpaper(frag_instance, monkeypatch):
    """Brak pliku tapety zwraca (None, [błąd])."""
    from gui.colors import apply_colors_from_wallpaper
    colors, errors = apply_colors_from_wallpaper(
        "/nonexistent/wallpaper.jpg",
        instances={0: frag_instance},
        inst_modules={0: "graph"},
    )
    assert colors is None
    assert len(errors) > 0

def test_apply_multiple_instances(tricolor_wallpaper, tmp_path, monkeypatch):
    """apply_colors_from_wallpaper obsługuje wiele instancji."""
    from gui import instance as inst_mod, colors as colors_mod, glava as glava_mod
    import glob
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))
    monkeypatch.setattr(colors_mod, "FLAG_RED",    str(tmp_path / "red.shift"))
    monkeypatch.setattr(colors_mod, "FLAG_MANUAL", str(tmp_path / "manual.shift"))
    monkeypatch.setattr(glava_mod, "glava_restart_instance", lambda **kw: None)

    # Przygotuj wspólny szablon ~/.config/glava
    glava_tmpl = tmp_path / ".config" / "glava"
    glava_tmpl.mkdir(parents=True)
    src_glsl = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    for f in glob.glob(os.path.join(src_glsl, "*.glsl")):
        shutil.copy2(f, str(glava_tmpl))
    src_c = os.path.join(os.path.dirname(__file__), '..', 'config')
    shutil.copy2(os.path.join(src_c, "graph_colors.frag"), str(glava_tmpl))

    # Utwórz dwie instancje przez create()
    instances = {}
    for iid in (0, 1):
        inst = inst_mod.GlavaInstance(iid, home=str(tmp_path))
        inst.create()
        os.makedirs(os.path.join(inst.glava_dir, "graph"), exist_ok=True)
        instances[iid] = inst

    from gui.colors import apply_colors_from_wallpaper
    called = []
    colors, errors = apply_colors_from_wallpaper(
        tricolor_wallpaper,
        instances=instances,
        inst_modules={0: "graph", 1: "graph"},
        after_fn=lambda iid, inst, mod: called.append(iid),
    )
    assert colors is not None
    assert set(called) == {0, 1}
    assert errors == []


# ── set_gradient_mode — linia 108 (plik bez HSV_MODE) ────────────────────────

def test_set_gradient_mode_skips_file_without_hsv(frag_instance, monkeypatch):
    """set_gradient_mode pomija plik który nie zawiera #define HSV_MODE."""
    from gui.colors import set_gradient_mode
    # Utwórz plik bez HSV_MODE
    path = os.path.join(frag_instance.glava_dir, "no_hsv.frag")
    with open(path, "w") as f:
        f.write("vec3 top = vec3(1.0, 0.0, 0.0);\n")
    before = open(path).read()
    set_gradient_mode("graph", "hsv",
                      live_path=path,
                      tmpl_path=frag_instance.module_tmpl("graph"))
    after = open(path).read()
    assert before == after


# ── apply_colors_from_wallpaper — linia 183-184 (błąd write) ─────────────────

def test_apply_colors_error_propagated(tricolor_wallpaper, frag_instance,
                                       monkeypatch):
    """apply_colors_from_wallpaper zbiera błędy gdy write_colors_to_frag failuje."""
    from gui import glava as glava_mod, colors as colors_mod
    monkeypatch.setattr(glava_mod, "glava_restart_instance", lambda **kw: None)
    monkeypatch.setattr(colors_mod, "write_colors_to_frag",
                        lambda *a, **kw: (False, "Brak szablonu"))
    colors, errors = colors_mod.apply_colors_from_wallpaper(
        tricolor_wallpaper,
        instances={0: frag_instance},
        inst_modules={0: "graph"},
    )
    assert len(errors) > 0
    assert "inst-0" in errors[0]
