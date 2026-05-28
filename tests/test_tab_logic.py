# =============================================================================
# tests/test_tab_logic.py
# Testy logiki biznesowej TabMain i TabAdvanced bez uruchamiania GUI.
# Testowane są metody operujące na plikach i obliczeniach —
# bez tworzenia widgetów Tkinter.
# =============================================================================
import pytest
import os
import glob
import shutil

# ── Fake app ──────────────────────────────────────────────────────────────────

class FakeInst:
    def __init__(self, glava_dir):
        self.glava_dir = glava_dir
        self.xdg_dir   = glava_dir
        self.conf_dir  = glava_dir
    def module_frag(self, mod): return os.path.join(self.glava_dir, mod, "1.frag")
    def module_tmpl(self, mod): return os.path.join(self.glava_dir, f"{mod}_colors.frag")
    @property
    def rc_glsl(self): return os.path.join(self.glava_dir, "rc.glsl")


class FakeBoolVar:
    def __init__(self, val=False): self._v = val
    def get(self): return self._v
    def set(self, v): self._v = v


class FakeApp:
    def __init__(self, inst, rc_path, settings=None):
        self.active_instance  = inst
        self.active_module    = "bars"
        self._active_inst_id  = 0
        self.instances        = {0: inst}
        self._inst_modules    = {0: "bars"}
        self.expert_mode      = FakeBoolVar(False)
        self.settings         = settings or {"gradient_mode": "rgb"}
        self._rc_path         = rc_path
        self._restart_calls   = []
        self._after_jobs      = {}
        self._job_counter     = 0

    def get_active_rc_glsl(self):  return self._rc_path
    def get_active_glava_dir(self): return self.active_instance.glava_dir
    def update_status(self): pass
    def rebuild_module_tab(self): pass

    def restart_active_instance(self, module=None, after_fn=None):
        self._restart_calls.append(module)
        if after_fn:
            after_fn()

    class _FakeRoot:
        def after(self, ms, fn, *a): fn(*a); return 0
        def after_cancel(self, jid): pass

    root = _FakeRoot()


@pytest.fixture
def env(tmp_path):
    """Pełne środowisko: instancja z plikami GLSL + szablonami kolorów."""
    glava_dir = str(tmp_path / "glava")
    os.makedirs(glava_dir)
    src_glsl = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    for f in glob.glob(os.path.join(src_glsl, "*.glsl")):
        shutil.copy2(f, glava_dir)
    src_cfg = os.path.join(os.path.dirname(__file__), '..', 'config')
    for mod in ("bars", "circle", "graph", "wave", "radial"):
        os.makedirs(os.path.join(glava_dir, mod), exist_ok=True)
        tmpl = os.path.join(src_cfg, f"{mod}_colors.frag")
        if os.path.exists(tmpl):
            shutil.copy2(tmpl, glava_dir)
    inst = FakeInst(glava_dir)
    rc   = os.path.join(glava_dir, "rc.glsl")
    app  = FakeApp(inst, rc)
    return app, inst, glava_dir, rc


# =============================================================================
# TabMain — logika bez GUI
# =============================================================================

def _make_tab_main(app, T=None):
    """
    Tworzy obiekt z metodami TabMain bez uruchamiania Tkinter.
    Import TabMain opóźniony do momentu wywołania — unika błędu collection.
    """
    from gui.tab_main import TabMain as _TM
    obj = object.__new__(_TM.__class__.__bases__[0] if _TM.__class__.__bases__ else object)
    # Tworzymy prosty namespace
    class _Bare:
        pass
    b = _Bare()
    b.app = app
    b.T   = T or {}
    b.current_colors = {"top": "#ff0000", "mid": "#00ff00", "bottom": "#0000ff"}
    b.presets = {}
    b.gradient_mode = "rgb"
    b.color_btns = {}
    # Bindujemy metody
    import types
    for name in ("_live_frag", "_tmpl_frag", "_load_colors_from_live",
                 "_contrast_fg", "_update_geometry_for_module",
                 "_change_gradient", "_inst"):
        fn = getattr(_TM, name)
        setattr(b, name, types.MethodType(fn, b))
    return b


# Alias dla czytelności testów
BareTabMain = _make_tab_main


# ── _live_frag / _tmpl_frag ───────────────────────────────────────────────────

def test_live_frag_with_instance(env):
    app, inst, glava_dir, rc = env
    t = BareTabMain(app)
    result = t._live_frag("bars")
    assert result == inst.module_frag("bars")
    assert result.endswith("bars/1.frag")

def test_tmpl_frag_with_instance(env):
    app, inst, glava_dir, rc = env
    t = BareTabMain(app)
    result = t._tmpl_frag("graph")
    assert result == inst.module_tmpl("graph")
    assert result.endswith("graph_colors.frag")

def test_live_frag_uses_active_module(env):
    app, inst, glava_dir, rc = env
    app.active_module = "circle"
    t = BareTabMain(app)
    result = t._live_frag()
    assert "circle" in result

def test_tmpl_frag_uses_active_module(env):
    app, inst, glava_dir, rc = env
    app.active_module = "wave"
    t = BareTabMain(app)
    result = t._tmpl_frag()
    assert "wave" in result

def test_live_frag_fallback_no_instance(env, monkeypatch):
    """Bez instancji używa get_live_frag z core."""
    from gui import tab_main as tm
    app, inst, glava_dir, rc = env
    app.active_instance = None
    t = BareTabMain(app)
    result = t._live_frag("bars")
    assert result.endswith("1.frag")


# ── _contrast_fg ──────────────────────────────────────────────────────────────

def test_contrast_fg_dark_color(env):
    """Ciemny kolor → biały tekst."""
    app, *_ = env
    t = BareTabMain(app)
    assert t._contrast_fg("#000000") == "#ffffff"
    assert t._contrast_fg("#1a1a2e") == "#ffffff"
    assert t._contrast_fg("#0000ff") == "#ffffff"

def test_contrast_fg_light_color(env):
    """Jasny kolor → czarny tekst."""
    app, *_ = env
    t = BareTabMain(app)
    assert t._contrast_fg("#ffffff") == "#000000"
    assert t._contrast_fg("#ffff00") == "#000000"

def test_contrast_fg_mid_gray(env):
    """Szary (~50% luminancji) — białe lub czarne."""
    app, *_ = env
    t = BareTabMain(app)
    result = t._contrast_fg("#808080")
    assert result in ("#000000", "#ffffff")

def test_contrast_fg_invalid(env):
    """Nieprawidłowy kolor zwraca #ffffff."""
    app, *_ = env
    t = BareTabMain(app)
    assert t._contrast_fg("invalid") == "#ffffff"
    assert t._contrast_fg("") == "#ffffff"


# ── _load_colors_from_live ────────────────────────────────────────────────────

def test_load_colors_from_live_reads_frag(env, monkeypatch):
    """_load_colors_from_live ustawia current_colors z live frag."""
    from gui import colors as colors_mod
    app, inst, glava_dir, rc = env
    # Napisz live frag z kolorami
    colors_mod.write_colors_to_frag(
        "graph",
        {"top": "#aa0000", "mid": "#00aa00", "bottom": "#0000aa"},
        tmpl_path=inst.module_tmpl("graph"),
        live_path=inst.module_frag("graph"),
    )
    app.active_module = "graph"
    t = BareTabMain(app)
    t._load_colors_from_live()
    assert t.current_colors["top"] == "#aa0000"

def test_load_colors_from_live_prefers_last_session(env, monkeypatch):
    """_load_colors_from_live preferuje LAST_SESSION z presets nad live frag."""
    from gui import colors as colors_mod
    app, inst, glava_dir, rc = env
    colors_mod.write_colors_to_frag(
        "graph",
        {"top": "#aa0000", "mid": "#00aa00", "bottom": "#0000aa"},
        tmpl_path=inst.module_tmpl("graph"),
        live_path=inst.module_frag("graph"),
    )
    app.active_module = "graph"
    t = BareTabMain(app)
    t.presets["LAST_SESSION"] = {"top": "#112233", "mid": "#445566", "bottom": "#778899"}
    t._load_colors_from_live()
    assert t.current_colors["top"] == "#112233"


# ── _update_geometry_for_module ───────────────────────────────────────────────

def test_update_geometry_bars_writes_rc(env, monkeypatch):
    """_update_geometry_for_module zapisuje geometrię do rc.glsl dla bars."""
    from gui import geometry as geo
    app, inst, glava_dir, rc = env
    monkeypatch.setattr(geo, "get_screen_info",
                        lambda: (1600, 900, 860, 0, 40, 0, 0))
    t = BareTabMain(app)
    t._update_geometry_for_module("bars")
    from gui.geometry import read_geometry
    result = read_geometry(rc)
    assert result is not None
    x, y, w, h = result
    assert w == 1600
    assert h == 900

def test_update_geometry_all_modules_no_crash(env, monkeypatch):
    """_update_geometry_for_module nie crashuje dla żadnego modułu."""
    from gui import geometry as geo
    from gui.core import GLAVA_MODULES
    app, inst, glava_dir, rc = env
    monkeypatch.setattr(geo, "get_screen_info",
                        lambda: (1600, 900, 860, 0, 40, 0, 0))
    t = BareTabMain(app)
    for mod in GLAVA_MODULES:
        t._update_geometry_for_module(mod)

def test_update_geometry_reads_flip_flag(env, monkeypatch):
    """_update_geometry_for_module czyta FLIP z bars.glsl."""
    from gui import geometry as geo
    from gui.modules import glsl_io
    from gui.modules.bars import SHAPE_PARAMS, FLAG_PARAMS
    app, inst, glava_dir, rc = env
    monkeypatch.setattr(geo, "get_screen_info",
                        lambda: (1600, 900, 860, 0, 40, 0, 0))
    bars_glsl = os.path.join(glava_dir, "bars.glsl")
    glsl_io.write_flag_defines(bars_glsl, {"FLIP": 1}, FLAG_PARAMS)
    t = BareTabMain(app)
    t._update_geometry_for_module("bars")
    from gui.geometry import read_geometry
    result = read_geometry(rc)
    assert result is not None
    # Z FLIP=1 y powinien być >= 0 (top)
    x, y, w, h = result
    assert y >= 0


# =============================================================================
# TabAdvanced — logika bez GUI
# =============================================================================

def _make_tab_advanced(app, T=None):
    """
    Tworzy obiekt z metodami TabAdvanced bez uruchamiania Tkinter.
    """
    from gui.tab_advanced import TabAdvanced as _TA
    import types
    class _Bare:
        pass
    b = _Bare()
    b.app = app
    b.T   = T or {}
    for name in ("_rc_glsl", "_expert", "_read_request_bool",
                 "_read_request_int", "_write_request_to", "_write_request"):
        fn = getattr(_TA, name)
        setattr(b, name, types.MethodType(fn, b))
    return b


BareTabAdvanced = _make_tab_advanced


# ── _rc_glsl ──────────────────────────────────────────────────────────────────

def test_rc_glsl_from_app(env):
    app, inst, glava_dir, rc = env
    t = BareTabAdvanced(app)
    assert t._rc_glsl() == rc

def test_rc_glsl_fallback(tmp_path, monkeypatch):
    """Bez get_active_rc_glsl używa RC_GLSL z tab_advanced."""
    from gui import tab_advanced as ta_mod
    import glob, shutil
    glava_dir = str(tmp_path / "glava")
    os.makedirs(glava_dir)
    src_glsl = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    for f in glob.glob(os.path.join(src_glsl, "*.glsl")):
        shutil.copy2(f, glava_dir)
    rc = os.path.join(glava_dir, "rc.glsl")

    # Aplikacja bez metody get_active_rc_glsl — osobna klasa, nie modyfikujemy FakeApp
    class AppWithoutRcMethod:
        active_instance = FakeInst(glava_dir)
        expert_mode = FakeBoolVar(False)
        def get_active_rc_glsl(self): return None  # zwraca None → fallback do RC_GLSL

    monkeypatch.setattr(ta_mod, "RC_GLSL", rc)
    app = AppWithoutRcMethod()
    t = BareTabAdvanced(app)
    assert t._rc_glsl() == rc


# ── _expert ───────────────────────────────────────────────────────────────────

def test_expert_false_by_default(env):
    app, *_ = env
    t = BareTabAdvanced(app)
    assert t._expert() == False

def test_expert_true_when_set(env):
    app, *_ = env
    app.expert_mode.set(True)
    t = BareTabAdvanced(app)
    assert t._expert() == True

def test_expert_false_without_attr(env):
    app, *_ = env
    del app.expert_mode
    t = BareTabAdvanced(app)
    assert t._expert() == False


# ── _read_request_bool ────────────────────────────────────────────────────────

def test_read_request_bool_true(tmp_path, monkeypatch):
    """_read_request_bool czyta true z rc.glsl przez glsl_io bezpośrednio."""
    from gui.modules.glsl_io import read_bool_req
    rc = str(tmp_path / "rc.glsl")
    with open(rc, "w") as f:
        f.write("#request setfloating true\n")
    result = read_bool_req(rc, "setfloating")
    assert result["setfloating"] == True

def test_read_request_bool_false(tmp_path):
    """_read_request_bool czyta false z rc.glsl."""
    from gui.modules.glsl_io import read_bool_req
    rc = str(tmp_path / "rc.glsl")
    with open(rc, "w") as f:
        f.write("#request setfloating false\n")
    result = read_bool_req(rc, "setfloating")
    assert result["setfloating"] == False

def test_read_request_bool_missing_key(tmp_path):
    """read_bool_req zwraca False gdy klucz nie istnieje."""
    from gui.modules.glsl_io import read_bool_req
    rc = str(tmp_path / "rc.glsl")
    with open(rc, "w") as f:
        f.write("#request setframerate 60\n")
    result = read_bool_req(rc, "nonexistent_key_xyz")
    assert result["nonexistent_key_xyz"] == False

def test_read_request_bool_missing_file(tmp_path):
    """read_bool_req zwraca False gdy plik nie istnieje."""
    from gui.modules.glsl_io import read_bool_req
    result = read_bool_req(str(tmp_path / "nonexistent.glsl"), "setfloating")
    assert result["setfloating"] == False

def test_tab_advanced_read_bool_via_rc_glsl(env):
    """_read_request_bool TabAdvanced czyta przez _rc_glsl() = app._rc_path."""
    from gui.modules.glsl_io import write_bool_req
    app, inst, glava_dir, rc = env
    write_bool_req(rc, "setfloating", True)
    t = BareTabAdvanced(app)
    assert t._read_request_bool("setfloating") == True

def test_tab_advanced_read_bool_false(env):
    """_read_request_bool czyta false — używa setfocused (inny klucz niż poprzedni test)."""
    from gui.modules.glsl_io import write_bool_req
    app, inst, glava_dir, rc = env
    write_bool_req(rc, "setfocused", False)
    t = BareTabAdvanced(app)
    assert t._read_request_bool("setfocused") == False


# ── _read_request_int ─────────────────────────────────────────────────────────

def test_read_request_int_existing(tmp_path):
    """read_int_req czyta wartość int z rc.glsl."""
    from gui.modules.glsl_io import read_int_req
    rc = str(tmp_path / "rc.glsl")
    with open(rc, "w") as f:
        f.write("#request setframerate 30\n")
    result = read_int_req(rc, "setframerate", 60)
    assert result["setframerate"] == 30

def test_read_request_int_default(tmp_path):
    """read_int_req zwraca default gdy klucz nie istnieje."""
    from gui.modules.glsl_io import read_int_req
    rc = str(tmp_path / "rc.glsl")
    with open(rc, "w") as f:
        f.write("#request setfloating true\n")
    result = read_int_req(rc, "nonexistent_key_xyz", 42)
    assert result["nonexistent_key_xyz"] == 42

def test_read_request_int_missing_file(tmp_path):
    """read_int_req zwraca default gdy plik nie istnieje."""
    from gui.modules.glsl_io import read_int_req
    result = read_int_req(str(tmp_path / "nonexistent.glsl"), "setframerate", 60)
    assert result["setframerate"] == 60

def test_tab_advanced_read_int_via_rc_glsl(env):
    """_read_request_int TabAdvanced czyta przez _rc_glsl() = app._rc_path."""
    from gui.modules.glsl_io import write_int_req
    app, inst, glava_dir, rc = env
    write_int_req(rc, "setshaderversion", 330)
    t = BareTabAdvanced(app)
    assert t._read_request_int("setshaderversion", 0) == 330


# ── _write_request_to ─────────────────────────────────────────────────────────

def test_write_request_to_existing_key(env):
    app, inst, glava_dir, rc = env
    t = BareTabAdvanced(app)
    t._write_request_to(rc, "setframerate", 120)
    with open(rc) as f:
        content = f.read()
    assert "#request setframerate 120" in content

def test_write_request_to_appends_new_key(env, tmp_path):
    app, inst, glava_dir, rc = env
    new_rc = str(tmp_path / "new_rc.glsl")
    with open(new_rc, "w") as f:
        f.write("// empty\n")
    t = BareTabAdvanced(app)
    t._write_request_to(new_rc, "newkey", "newval")
    with open(new_rc) as f:
        content = f.read()
    assert "#request newkey newval" in content

def test_write_request_to_no_duplicate(env):
    app, inst, glava_dir, rc = env
    t = BareTabAdvanced(app)
    t._write_request_to(rc, "setframerate", 30)
    t._write_request_to(rc, "setframerate", 60)
    with open(rc) as f:
        content = f.read()
    assert content.count("setframerate") == 1
    assert "#request setframerate 60" in content

def test_write_request_to_missing_file(env, tmp_path):
    """_write_request_to nie crashuje gdy plik nie istnieje."""
    app, *_ = env
    t = BareTabAdvanced(app)
    t._write_request_to(str(tmp_path / "nonexistent.glsl"), "key", "val")


# ── _write_request (wszystkie instancje) ──────────────────────────────────────

def test_write_request_writes_to_all_instances(env, tmp_path):
    """_write_request zapisuje do rc.glsl WSZYSTKICH instancji."""
    app, inst, glava_dir, rc = env
    # Dodaj drugą instancję
    glava_dir2 = str(tmp_path / "glava2")
    os.makedirs(glava_dir2)
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config', 'rc.glsl')
    shutil.copy2(src, os.path.join(glava_dir2, "rc.glsl"))
    inst2 = FakeInst(glava_dir2)
    app.instances[1] = inst2
    t = BareTabAdvanced(app)
    t._write_request("setframerate", 45)
    # Sprawdź obie instancje
    with open(rc) as f:
        assert "#request setframerate 45" in f.read()
    with open(inst2.rc_glsl) as f:
        assert "#request setframerate 45" in f.read()

def test_write_request_fallback_single_rc(env, monkeypatch):
    """Bez app.instances zapisuje do pojedynczego rc.glsl."""
    from gui import tab_advanced as ta_mod
    app, inst, glava_dir, rc = env
    del app.instances
    monkeypatch.setattr(ta_mod, "RC_GLSL", rc)
    t = BareTabAdvanced(app)
    t._write_request("setframerate", 99)
    with open(rc) as f:
        assert "#request setframerate 99" in f.read()
