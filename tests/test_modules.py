# =============================================================================
# tests/test_modules.py
# Testy collect_params / apply_params dla wszystkich modułów GLava
# oraz konwersji kąta w circle i radial.
# =============================================================================
import pytest
import os
import glob
import shutil

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_instance(tmp_path):
    """
    Tworzy GlavaInstance z plikami GLSL z glava-config/.
    Zwraca instancję gotową do użycia w collect_params/apply_params.
    """
    from gui import instance as inst_mod
    glava_dir = tmp_path / ".config" / "glava"
    glava_dir.mkdir(parents=True)
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    for f in glob.glob(os.path.join(src, "*.glsl")):
        shutil.copy2(f, str(glava_dir))
    # Katalogi shaderów (bars/, circle/ itd.) — potrzebne dla module_frag
    for mod in ("bars", "circle", "graph", "wave", "radial"):
        (glava_dir / mod).mkdir(exist_ok=True)
    inst = inst_mod.GlavaInstance(0, home=str(tmp_path))
    return inst


class FakeApp:
    """Minimalna implementacja app wymagana przez collect/apply_params."""
    def __init__(self, inst):
        self.active_instance = inst


# ── collect_params — struktura zwracanego dict ────────────────────────────────

@pytest.mark.parametrize("mod_name", ["bars", "circle", "graph", "wave", "radial"])
def test_collect_params_returns_dict(fake_instance, mod_name):
    import importlib
    mod = importlib.import_module(f"gui.modules.{mod_name}")
    app = FakeApp(fake_instance)
    result = mod.collect_params(app)
    assert isinstance(result, dict)
    assert len(result) > 0

@pytest.mark.parametrize("mod_name", ["bars", "circle", "graph", "wave", "radial"])
def test_collect_params_has_shape_keys(fake_instance, mod_name):
    """collect_params zawiera klucze z SHAPE_PARAMS modułu."""
    import importlib
    mod = importlib.import_module(f"gui.modules.{mod_name}")
    app = FakeApp(fake_instance)
    result = mod.collect_params(app)
    shape_params = getattr(mod, "SHAPE_PARAMS", None)
    if shape_params:
        for p in shape_params:
            assert p[0] in result, f"Brak klucza {p[0]} w collect_params({mod_name})"

@pytest.mark.parametrize("mod_name", ["bars", "circle", "graph", "wave", "radial"])
def test_collect_params_has_smooth_keys(fake_instance, mod_name):
    """collect_params zawiera klucze z SMOOTH_PARAMS."""
    import importlib
    from gui.core import SMOOTH_PARAMS
    mod = importlib.import_module(f"gui.modules.{mod_name}")
    app = FakeApp(fake_instance)
    result = mod.collect_params(app)
    for p in SMOOTH_PARAMS:
        assert p[0] in result, f"Brak klucza smooth {p[0]} w collect_params({mod_name})"

# ── apply_params — roundtrip ──────────────────────────────────────────────────

@pytest.mark.parametrize("mod_name", ["bars", "circle", "graph", "wave"])
def test_apply_collect_roundtrip(fake_instance, mod_name):
    """
    apply_params nie crashuje i collect_params po nim zwraca dict
    z kluczami shape o prawidłowych typach i wartościach w zakresie.

    Pełny roundtrip wartości nie jest gwarantowany dla kluczy których
    nie ma w plikach GLSL (write_defines działa jako replace-only).
    Weryfikujemy że operacja jest bezpieczna i wyniki są spójne.
    """
    import importlib
    mod = importlib.import_module(f"gui.modules.{mod_name}")
    app = FakeApp(fake_instance)

    shape_params = getattr(mod, "SHAPE_PARAMS", None)
    if not shape_params:
        pytest.skip(f"{mod_name} nie ma SHAPE_PARAMS")

    original = mod.collect_params(app)

    # apply_params nie może crashować
    mod.apply_params(original, app)

    # collect_params po apply zwraca dict z kluczami shape
    result = mod.collect_params(app)
    for p in shape_params:
        key, vmin, vmax = p[0], p[2], p[3]
        assert key in result, f"{mod_name}: brak klucza {key} po apply_params"
        assert isinstance(result[key], (int, float)), \
            f"{mod_name}.{key}: typ {type(result[key])}, oczekiwano int/float"
        assert vmin <= result[key] <= vmax, \
            f"{mod_name}.{key}: wartość {result[key]} poza zakresem [{vmin},{vmax}]"

@pytest.mark.parametrize("mod_name", ["bars", "circle", "graph", "wave", "radial"])
def test_apply_params_does_not_crash(fake_instance, mod_name):
    """apply_params z domyślnymi wartościami nie crashuje."""
    import importlib
    mod = importlib.import_module(f"gui.modules.{mod_name}")
    app = FakeApp(fake_instance)
    params = mod.collect_params(app)
    mod.apply_params(params, app)

# ── Konwersje kąta — circle ───────────────────────────────────────────────────

def test_circle_rotate_to_deg_symbolic():
    from gui.modules.circle import _rotate_to_deg
    assert _rotate_to_deg("0")         == 0
    assert _rotate_to_deg("(PI / 2)")  == 90
    assert _rotate_to_deg("PI")        == 180
    assert _rotate_to_deg("(3 * PI / 2)") == 270

def test_circle_rotate_to_deg_float():
    """Wartość float w radianach jest poprawnie konwertowana."""
    from gui.modules.circle import _rotate_to_deg
    import math
    val = f"{math.pi / 4:.6f}"  # 45°
    result = _rotate_to_deg(val)
    assert abs(result - 45) <= 1

def test_circle_deg_to_rotate_zero():
    from gui.modules.circle import _deg_to_rotate
    result = _deg_to_rotate(0)
    assert float(result) == pytest.approx(0.0, abs=0.001)

def test_circle_deg_to_rotate_90():
    from gui.modules.circle import _deg_to_rotate
    import math
    result = _deg_to_rotate(90)
    assert float(result) == pytest.approx(math.pi / 2, abs=0.001)

def test_circle_deg_to_rotate_180():
    from gui.modules.circle import _deg_to_rotate
    import math
    result = _deg_to_rotate(180)
    assert float(result) == pytest.approx(math.pi, abs=0.001)

def test_circle_rotate_roundtrip():
    """_rotate_to_deg(_deg_to_rotate(deg)) == deg dla podstawowych kątów."""
    from gui.modules.circle import _rotate_to_deg, _deg_to_rotate
    for deg in (0, 45, 90, 135, 180, 270):
        raw = _deg_to_rotate(deg)
        result = _rotate_to_deg(raw)
        assert abs(result - deg) <= 1, f"deg={deg}: roundtrip={result}"

# ── Konwersje kąta — radial ───────────────────────────────────────────────────

def test_radial_rotate_to_deg_symbolic():
    from gui.modules.radial import _rotate_to_deg
    assert _rotate_to_deg("0")       == 0
    assert _rotate_to_deg("(PI/2)")  == 90
    assert _rotate_to_deg("PI")      == 180
    assert _rotate_to_deg("(3*PI/2)") == 270

def test_radial_rotate_to_deg_float():
    from gui.modules.radial import _rotate_to_deg
    import math
    val = f"{math.pi / 2:.6f}"  # 90°
    assert _rotate_to_deg(val) == 90

def test_radial_rotate_to_deg_unknown():
    """Nieznana wartość zwraca 90 (fallback)."""
    from gui.modules.radial import _rotate_to_deg
    assert _rotate_to_deg("invalid_val") == 90

def test_radial_deg_to_rotate_90():
    from gui.modules.radial import _deg_to_rotate
    import math
    result = _deg_to_rotate(90)
    assert float(result) == pytest.approx(math.pi / 2, abs=0.001)

def test_radial_rotate_roundtrip():
    from gui.modules.radial import _rotate_to_deg, _deg_to_rotate
    for deg in (0, 90, 180, 270):
        raw = _deg_to_rotate(deg)
        result = _rotate_to_deg(raw)
        assert abs(result - deg) <= 1, f"deg={deg}: roundtrip={result}"

# ── SHAPE_PARAMS / FLAG_PARAMS — struktura ────────────────────────────────────

@pytest.mark.parametrize("mod_name", ["bars", "circle", "graph", "wave"])
def test_shape_params_structure(mod_name):
    """Każdy wpis SHAPE_PARAMS ma co najmniej 7 elementów: key,label,min,max,default,unit,tooltip."""
    import importlib
    mod = importlib.import_module(f"gui.modules.{mod_name}")
    shape_params = getattr(mod, "SHAPE_PARAMS", None)
    if shape_params is None:
        pytest.skip(f"{mod_name} nie ma SHAPE_PARAMS")
    for p in shape_params:
        assert len(p) >= 7, f"{mod_name} SHAPE_PARAMS wpis {p[0]} ma {len(p)} elementów"
        key, label, vmin, vmax, default, unit, tooltip = p[0], p[1], p[2], p[3], p[4], p[5], p[6]
        assert isinstance(key, str)
        assert vmin <= default <= vmax, f"{mod_name}.{key}: default {default} poza [{vmin},{vmax}]"

@pytest.mark.parametrize("mod_name", ["bars", "circle", "graph", "wave", "radial"])
def test_flag_params_structure(mod_name):
    """
    Każdy wpis FLAG_PARAMS ma co najmniej 3 elementy.
    bars/circle/wave: 3-krotka (key, label, tooltip)
    graph: 4-krotka (key, label, default_val, tooltip)
    radial: 4-krotka (key, label, i18n_key, tooltip)
    Wspólny wymagany format: key=str, label=str, ostatni element=str (tooltip).
    """
    import importlib
    mod = importlib.import_module(f"gui.modules.{mod_name}")
    flag_params = getattr(mod, "FLAG_PARAMS", None)
    if flag_params is None:
        pytest.skip(f"{mod_name} nie ma FLAG_PARAMS")
    for p in flag_params:
        assert len(p) >= 3, \
            f"{mod_name} FLAG_PARAMS wpis {p[0]} ma {len(p)} elementów, oczekiwano min 3"
        assert isinstance(p[0], str), f"{mod_name} FLAG_PARAMS: key musi być str"
        assert isinstance(p[1], str), f"{mod_name} FLAG_PARAMS: label musi być str"
        assert isinstance(p[-1], str), f"{mod_name} FLAG_PARAMS: tooltip (ostatni) musi być str"

# ── radial — SHAPE_INT_PARAMS / SHAPE_FLOAT_PARAMS ───────────────────────────

def test_radial_shape_int_params_structure():
    """SHAPE_INT_PARAMS: 7-krotka (key, label, min, max, default, unit, tooltip)."""
    from gui.modules.radial import SHAPE_INT_PARAMS
    for p in SHAPE_INT_PARAMS:
        assert len(p) == 7, f"SHAPE_INT_PARAMS wpis {p[0]} ma {len(p)} elementów, oczekiwano 7"
        key, label, vmin, vmax, default, unit, tooltip = p
        assert isinstance(key, str)
        assert vmin <= default <= vmax, \
            f"radial int {key}: default {default} poza [{vmin},{vmax}]"

def test_radial_shape_float_params_structure():
    """SHAPE_FLOAT_PARAMS: 7-krotka (key, label, min, max, default, step, tooltip)."""
    from gui.modules.radial import SHAPE_FLOAT_PARAMS
    for p in SHAPE_FLOAT_PARAMS:
        assert len(p) == 7, f"SHAPE_FLOAT_PARAMS wpis {p[0]} ma {len(p)} elementów, oczekiwano 7"
        key, label, vmin, vmax, default, step, tooltip = p
        assert isinstance(key, str)
        assert step > 0, f"radial float {key}: step musi być > 0"
        assert vmin <= default <= vmax, \
            f"radial float {key}: default {default} poza [{vmin},{vmax}]"

def test_radial_collect_params_has_int_keys(fake_instance):
    """collect_params zawiera klucze z SHAPE_INT_PARAMS."""
    from gui.modules import radial
    from gui.modules.radial import SHAPE_INT_PARAMS
    app = FakeApp(fake_instance)
    result = radial.collect_params(app)
    for p in SHAPE_INT_PARAMS:
        assert p[0] in result, f"Brak klucza int {p[0]} w radial.collect_params"

def test_radial_collect_params_has_float_keys(fake_instance):
    """collect_params zawiera klucze z SHAPE_FLOAT_PARAMS."""
    from gui.modules import radial
    from gui.modules.radial import SHAPE_FLOAT_PARAMS
    app = FakeApp(fake_instance)
    result = radial.collect_params(app)
    for p in SHAPE_FLOAT_PARAMS:
        assert p[0] in result, f"Brak klucza float {p[0]} w radial.collect_params"

def test_radial_apply_params_does_not_crash(fake_instance):
    from gui.modules import radial
    app = FakeApp(fake_instance)
    params = radial.collect_params(app)
    radial.apply_params(params, app)

def test_radial_collect_after_apply_int_in_range(fake_instance):
    """Po apply_params wartości int są w zakresie [vmin, vmax]."""
    from gui.modules import radial
    from gui.modules.radial import SHAPE_INT_PARAMS
    app = FakeApp(fake_instance)
    params = radial.collect_params(app)
    radial.apply_params(params, app)
    result = radial.collect_params(app)
    for p in SHAPE_INT_PARAMS:
        key, vmin, vmax = p[0], p[2], p[3]
        assert isinstance(result[key], (int, float)), \
            f"radial.{key}: typ {type(result[key])}"
        assert vmin <= result[key] <= vmax, \
            f"radial.{key}: {result[key]} poza [{vmin},{vmax}]"

def test_radial_collect_after_apply_float_in_range(fake_instance):
    """Po apply_params wartości float są w zakresie [vmin, vmax]."""
    from gui.modules import radial
    from gui.modules.radial import SHAPE_FLOAT_PARAMS
    app = FakeApp(fake_instance)
    params = radial.collect_params(app)
    radial.apply_params(params, app)
    result = radial.collect_params(app)
    for p in SHAPE_FLOAT_PARAMS:
        key, vmin, vmax = p[0], p[2], p[3]
        assert isinstance(result[key], (int, float)), \
            f"radial.{key}: typ {type(result[key])}"
        assert vmin <= result[key] <= vmax, \
            f"radial.{key}: {result[key]} poza [{vmin},{vmax}]"
