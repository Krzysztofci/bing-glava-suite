# =============================================================================
# tests/test_reset_shader.py
# Testy reset_shader dla wszystkich modułów oraz glava_restart (legacy).
# =============================================================================
import pytest
import os
import glob
import shutil
import time
import subprocess

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_app(tmp_path, monkeypatch):
    """
    Minimalny app z active_instance gotową do reset_shader.
    Instancja ma pełną strukturę: *.glsl + *_colors.frag + mod/1.frag
    """
    from gui import instance as inst_mod, colors as colors_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))
    monkeypatch.setattr(colors_mod, "FLAG_RED",    str(tmp_path / "red.shift"))
    monkeypatch.setattr(colors_mod, "FLAG_MANUAL", str(tmp_path / "manual.shift"))

    # Szablon
    glava_tmpl = tmp_path / ".config" / "glava"
    glava_tmpl.mkdir(parents=True)
    src_glsl = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    for f in glob.glob(os.path.join(src_glsl, "*.glsl")):
        shutil.copy2(f, str(glava_tmpl))
    src_cfg = os.path.join(os.path.dirname(__file__), '..', 'config')
    for mod in ("bars", "circle", "graph", "wave", "radial"):
        shutil.copy2(os.path.join(src_cfg, f"{mod}_colors.frag"), str(glava_tmpl))

    inst = inst_mod.GlavaInstance(0, home=str(tmp_path))
    inst.create()

    # Katalogi shaderów i live fragi
    for mod in ("bars", "circle", "graph", "wave", "radial"):
        mod_dir = os.path.join(inst.glava_dir, mod)
        os.makedirs(mod_dir, exist_ok=True)

    class App:
        def __init__(self, inst):
            self.active_instance = inst
    return App(inst)


# ── reset_shader — bars ───────────────────────────────────────────────────────

def test_reset_shader_bars_copies_template(fake_app):
    """reset_shader kopiuje szablon do live frag."""
    from gui.modules.bars import reset_shader
    reset_shader(fake_app)
    live = fake_app.active_instance.module_frag("bars")
    assert os.path.exists(live)

def test_reset_shader_bars_writes_defaults(fake_app):
    """reset_shader zapisuje domyślne wartości SHAPE_PARAMS do bars.glsl."""
    from gui.modules.bars import reset_shader, SHAPE_PARAMS
    from gui.modules import glsl_io
    # Najpierw zmień wartość
    glsl_io.write_define_int(
        fake_app.active_instance.module_glsl("bars"), "BAR_WIDTH", 99)
    reset_shader(fake_app)
    result = glsl_io.read_defines(
        fake_app.active_instance.module_glsl("bars"), SHAPE_PARAMS)
    default = next(p[4] for p in SHAPE_PARAMS if p[0] == "BAR_WIDTH")
    assert result["BAR_WIDTH"] == default

def test_reset_shader_bars_clears_flags(fake_app):
    """reset_shader zeruje wszystkie flagi FLAG_PARAMS."""
    from gui.modules.bars import reset_shader, FLAG_PARAMS
    from gui.modules import glsl_io
    # Ustaw flagę
    glsl_io.write_flag_defines(
        fake_app.active_instance.module_glsl("bars"),
        {FLAG_PARAMS[0][0]: 1}, FLAG_PARAMS)
    reset_shader(fake_app)
    result = glsl_io.read_flag_defines(
        fake_app.active_instance.module_glsl("bars"), FLAG_PARAMS)
    for p in FLAG_PARAMS:
        assert result[p[0]] == 0, f"Flaga {p[0]} powinna być 0 po reset"


# ── reset_shader — wszystkie moduły ──────────────────────────────────────────

@pytest.mark.parametrize("mod_name", ["bars", "circle", "graph", "wave", "radial"])
def test_reset_shader_does_not_crash(fake_app, mod_name):
    """reset_shader nie crashuje dla żadnego modułu."""
    import importlib
    mod = importlib.import_module(f"gui.modules.{mod_name}")
    mod.reset_shader(fake_app)

@pytest.mark.parametrize("mod_name", ["bars", "circle", "graph", "wave", "radial"])
def test_reset_shader_creates_live_frag(fake_app, mod_name):
    """reset_shader tworzy plik live frag jeśli szablon istnieje."""
    import importlib
    mod = importlib.import_module(f"gui.modules.{mod_name}")
    mod.reset_shader(fake_app)
    live = fake_app.active_instance.module_frag(mod_name)
    tmpl = fake_app.active_instance.module_tmpl(mod_name)
    if os.path.exists(tmpl):
        assert os.path.exists(live), \
            f"{mod_name}: live frag nie istnieje po reset_shader"

@pytest.mark.parametrize("mod_name", ["bars", "circle", "graph", "wave"])
def test_reset_shader_restores_shape_defaults(fake_app, mod_name):
    """reset_shader przywraca domyślne wartości SHAPE_PARAMS."""
    import importlib
    from gui.modules import glsl_io
    mod = importlib.import_module(f"gui.modules.{mod_name}")
    shape_params = getattr(mod, "SHAPE_PARAMS", None)
    if not shape_params:
        pytest.skip(f"{mod_name} nie ma SHAPE_PARAMS")
    # Zmień pierwszy parametr
    key, default = shape_params[0][0], shape_params[0][4]
    glsl_io.write_define_int(
        fake_app.active_instance.module_glsl(mod_name), key, default + 10)
    mod.reset_shader(fake_app)
    result = glsl_io.read_defines(
        fake_app.active_instance.module_glsl(mod_name), shape_params)
    assert result[key] == default, \
        f"{mod_name}.{key}: po reset oczekiwano {default}, got {result[key]}"


# ── glava_restart (legacy) ────────────────────────────────────────────────────

@pytest.fixture
def rc_file(tmp_path):
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config', 'rc.glsl')
    dst = str(tmp_path / "rc.glsl")
    shutil.copy2(src, dst)
    return dst

@pytest.fixture
def legacy_env(tmp_path, monkeypatch, rc_file):
    from gui import glava as glava_mod
    monkeypatch.setattr(glava_mod, "_PID_DIR", str(tmp_path / "pids"))
    monkeypatch.setattr(glava_mod, "RC_GLSL", rc_file)
    os.makedirs(str(tmp_path / "pids"))
    # Mock glava_stop_all — nie robimy pkill w testach
    monkeypatch.setattr(glava_mod, "glava_stop_all", lambda: None)
    return rc_file

def test_glava_restart_writes_module(legacy_env, monkeypatch):
    """glava_restart zapisuje moduł do rc.glsl przed startem."""
    from gui import glava as glava_mod
    monkeypatch.setattr(glava_mod, "glava_start", lambda *a, **kw: None)
    monkeypatch.setattr(glava_mod, "RC_GLSL", legacy_env)
    from gui.glava import glava_restart, read_rc_module
    glava_restart("circle", delay_ms=50)
    time.sleep(0.15)
    assert read_rc_module(rc_path=legacy_env) == "circle"

def test_glava_restart_calls_after_fn(legacy_env, monkeypatch):
    """glava_restart wywołuje after_fn po starcie."""
    from gui import glava as glava_mod
    monkeypatch.setattr(glava_mod, "glava_start", lambda *a, **kw: None)
    called = []
    from gui.glava import glava_restart
    glava_restart("bars", delay_ms=50, after_fn=lambda: called.append(True))
    time.sleep(0.15)
    assert called == [True]

def test_glava_restart_calls_stop_all(legacy_env, monkeypatch):
    """glava_restart wywołuje glava_stop_all przed startem."""
    from gui import glava as glava_mod
    stopped = []
    monkeypatch.setattr(glava_mod, "glava_stop_all", lambda: stopped.append(True))
    monkeypatch.setattr(glava_mod, "glava_start", lambda *a, **kw: None)
    from gui.glava import glava_restart
    glava_restart("wave", delay_ms=50)
    time.sleep(0.15)
    assert stopped == [True]
