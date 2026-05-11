import pytest
import tkinter as tk
import os
import sys

# ── Fake app ──────────────────────────────────────────────────────────────────

class FakeApp:
    def __init__(self, root, glava_dir):
        self.root = root
        self.expert_mode = tk.BooleanVar(value=False)
        self.extra_flags = "--desktop"
        self._glava_dir = glava_dir

    def update_status(self, *a): pass
    def rebuild_module_tab(self): pass

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()

@pytest.fixture
def fake_app(root, tmp_glava_dir):
    return FakeApp(root, tmp_glava_dir)

@pytest.fixture
def bars_widget(fake_app, tmp_glava_dir, monkeypatch):
    import gui.modules.bars as bars_mod
    import gui.modules.base as base_mod
    import gui.core as core
    monkeypatch.setattr(core, "GLAVA_DIR", tmp_glava_dir)
    monkeypatch.setattr(bars_mod, "GLAVA_DIR", tmp_glava_dir)
    monkeypatch.setattr(base_mod, "GLAVA_DIR", tmp_glava_dir)
    T = core.load_lang("pl")
    frame = tk.Frame(fake_app.root)
    w = bars_mod.BarsParamWidget(frame, fake_app, T)
    return w

# ── _module_glsl / _smooth_glsl ───────────────────────────────────────────────

def test_module_glsl_path(bars_widget, tmp_glava_dir):
    expected = os.path.join(tmp_glava_dir, "bars.glsl")
    assert bars_widget._module_glsl == expected

def test_smooth_glsl_path(bars_widget, tmp_glava_dir):
    expected = os.path.join(tmp_glava_dir, "smooth_parameters.glsl")
    assert bars_widget._smooth_glsl == expected

# ── SHAPE_PARAMS ──────────────────────────────────────────────────────────────

def test_shape_params_not_none(bars_widget):
    assert bars_widget.SHAPE_PARAMS is not None
    assert len(bars_widget.SHAPE_PARAMS) > 0

# ── _debounce target="module" ─────────────────────────────────────────────────

def test_debounce_module_writes_to_file(bars_widget, tmp_glava_dir, monkeypatch):
    """_debounce z target='module' zapisuje wartość do pliku GLSL."""
    monkeypatch.setattr(bars_widget.app.root, "after",
                        lambda ms, fn, *a: None)  # blokuj restart
    key = bars_widget.SHAPE_PARAMS[0][0]
    new_val = int(bars_widget.SHAPE_PARAMS[0][3])  # vmax
    bars_widget._debounce(key, new_val, "module")
    from gui.modules import glsl_io
    result = glsl_io.read_raw(bars_widget._module_glsl)
    assert str(new_val) in str(result.get(key, ""))

def test_debounce_smooth_writes_to_file(bars_widget, tmp_glava_dir, monkeypatch):
    """_debounce z target='smooth' zapisuje wartość do smooth_parameters.glsl."""
    monkeypatch.setattr(bars_widget.app.root, "after",
                        lambda ms, fn, *a: None)
    from gui.core import SMOOTH_PARAMS
    key = SMOOTH_PARAMS[0][0]
    step = SMOOTH_PARAMS[0][6]
    new_val = SMOOTH_PARAMS[0][4] + step  # default + step
    bars_widget._debounce(key, new_val, "smooth")
    from gui.modules import glsl_io
    result = glsl_io.read_smooth(bars_widget._smooth_glsl, SMOOTH_PARAMS)
    assert abs(result[key] - new_val) < step * 0.01

# ── MODULE_NAME ───────────────────────────────────────────────────────────────

def test_module_name(bars_widget):
    assert bars_widget.MODULE_NAME == "bars"
