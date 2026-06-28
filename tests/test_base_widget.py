import pytest
import tkinter as tk
import tkinter.ttk as ttk
import os
import sys
# ── Fake app ──────────────────────────────────────────────────────────────────
class FakeApp:
    def __init__(self, root, glava_dir):
        self.root = root
        self.expert_mode = tk.BooleanVar(value=False)
        self.extra_flags = "--desktop"
        self._glava_dir = glava_dir
        from gui.instance import GlavaInstance
        inst = GlavaInstance.__new__(GlavaInstance)
        inst.inst_id   = 0
        inst.xdg_dir   = os.path.dirname(glava_dir)
        inst.glava_dir = glava_dir
        inst.conf_dir  = glava_dir
        self.active_instance = inst
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
# ── build() ───────────────────────────────────────────────────────────────────
def test_build_creates_widgets(bars_widget):
    """build() nie crashuje i tworzy widgety w frame."""
    bars_widget.build()
    children = bars_widget.parent.winfo_children()
    assert len(children) > 0
def test_build_populates_vars(bars_widget):
    """build() wypełnia self.vars kluczami z SHAPE_PARAMS."""
    bars_widget.build()
    for p in bars_widget.SHAPE_PARAMS:
        assert p[0] in bars_widget.vars, f"Brak klucza {p[0]} w vars"
# ── _slider_row ───────────────────────────────────────────────────────────────
def test_slider_row_creates_var(bars_widget):
    """_slider_row tworzy IntVar w self.vars."""
    from gui.modules import glsl_io
    current = glsl_io.read_raw(bars_widget._module_glsl)
    p = bars_widget.SHAPE_PARAMS[0]
    frame = tk.Frame(bars_widget.app.root)
    bars_widget._slider_row(frame, tuple(p), current, 0)
    assert p[0] in bars_widget.vars
def test_slider_row_initial_value(bars_widget):
    """_slider_row ustawia wartość z current."""
    from gui.modules import glsl_io
    current = glsl_io.read_raw(bars_widget._module_glsl)
    p = bars_widget.SHAPE_PARAMS[0]
    key, vmin, vmax, default = p[0], p[2], p[3], p[4]
    frame = tk.Frame(bars_widget.app.root)
    bars_widget._slider_row(frame, tuple(p), current, 0)
    val = bars_widget.vars[key].get()
    assert vmin <= val <= vmax
# ── _float_slider_row ─────────────────────────────────────────────────────────
def test_float_slider_row_creates_var(bars_widget):
    """_float_slider_row tworzy DoubleVar w self.vars."""
    from gui.core import SMOOTH_PARAMS
    from gui.modules import glsl_io
    current = glsl_io.read_smooth(bars_widget._smooth_glsl, SMOOTH_PARAMS)
    p = SMOOTH_PARAMS[0]
    frame = tk.Frame(bars_widget.app.root)
    bars_widget._float_slider_row(frame, tuple(p), current, 0)
    assert p[0] in bars_widget.vars


# ── _slider_row / _float_slider_row callbacks (on_change / on_entry) ────────
#
# on_change/on_entry są domknięciami lokalnymi wewnątrz _slider_row/
# _float_slider_row — nie są przechowywane jako atrybuty widgetu. Jedyny
# dostęp do nich to przechwycenie w miejscu rejestracji: on_change trafia
# do ttk.Scale(command=...), on_entry do entry.bind("<Return>"/"<FocusOut>").
# Wzorzec analogiczny do "podsłuchu tk.Misc.bind() po func.__name__" używanego
# dla zagnieżdżonych callbacków w tab_advanced.py — tu rozszerzony też na
# przechwycenie kwargu command przy konstrukcji ttk.Scale.

def _capture_row_callbacks(monkeypatch):
    captured = {}
    orig_bind = tk.Misc.bind
    def fake_bind(self, sequence=None, func=None, add=None):
        if func is not None and getattr(func, "__name__", None) == "on_entry":
            captured["on_entry"] = func
        return orig_bind(self, sequence, func, add)
    monkeypatch.setattr(tk.Misc, "bind", fake_bind)

    orig_scale_init = ttk.Scale.__init__
    def fake_scale_init(self, *args, **kwargs):
        cmd = kwargs.get("command")
        if cmd is not None and getattr(cmd, "__name__", None) == "on_change":
            captured["on_change"] = cmd
        return orig_scale_init(self, *args, **kwargs)
    monkeypatch.setattr(ttk.Scale, "__init__", fake_scale_init)
    return captured


def _closure_var(func, name):
    """Wyciąga zmienną domknięcia (np. entry_var) z lokalnego callbacku."""
    return dict(zip(func.__code__.co_freevars,
                     (c.cell_contents for c in func.__closure__)))[name]


def test_slider_row_on_change_clamps_to_vmax_and_debounces(
        bars_widget, monkeypatch):
    from gui.modules import glsl_io
    captured = _capture_row_callbacks(monkeypatch)
    current = glsl_io.read_raw(bars_widget._module_glsl)
    p = bars_widget.SHAPE_PARAMS[0]   # BAR_WIDTH: vmin=1, vmax=40
    key, vmin, vmax = p[0], p[2], p[3]
    frame = tk.Frame(bars_widget.app.root)
    debounce_calls = []
    monkeypatch.setattr(bars_widget, "_debounce",
                         lambda k, v, t: debounce_calls.append((k, v, t)))

    bars_widget._slider_row(frame, tuple(p), current, 0)
    on_change = captured["on_change"]

    on_change(str(vmax + 50))  # poza zakresem -> clamp do vmax

    assert bars_widget.vars[key].get() == vmax
    assert debounce_calls == [(key, vmax, "module")]


def test_slider_row_on_change_clamps_to_vmin(bars_widget, monkeypatch):
    from gui.modules import glsl_io
    captured = _capture_row_callbacks(monkeypatch)
    current = glsl_io.read_raw(bars_widget._module_glsl)
    p = bars_widget.SHAPE_PARAMS[0]
    key, vmin, vmax = p[0], p[2], p[3]
    frame = tk.Frame(bars_widget.app.root)
    debounce_calls = []
    monkeypatch.setattr(bars_widget, "_debounce",
                         lambda k, v, t: debounce_calls.append((k, v, t)))

    bars_widget._slider_row(frame, tuple(p), current, 0)
    on_change = captured["on_change"]

    on_change(str(vmin - 50))  # poniżej zakresu -> clamp do vmin

    assert bars_widget.vars[key].get() == vmin
    assert debounce_calls == [(key, vmin, "module")]


def test_slider_row_on_entry_valid_value_updates_and_debounces(
        bars_widget, monkeypatch):
    from gui.modules import glsl_io
    captured = _capture_row_callbacks(monkeypatch)
    current = glsl_io.read_raw(bars_widget._module_glsl)
    p = bars_widget.SHAPE_PARAMS[0]
    key, vmin, vmax = p[0], p[2], p[3]
    frame = tk.Frame(bars_widget.app.root)
    debounce_calls = []
    monkeypatch.setattr(bars_widget, "_debounce",
                         lambda k, v, t: debounce_calls.append((k, v, t)))

    bars_widget._slider_row(frame, tuple(p), current, 0)
    on_entry = captured["on_entry"]
    entry_var = _closure_var(on_entry, "entry_var")

    target_val = min(vmax, vmin + 3)
    entry_var.set(str(target_val))
    on_entry(None)

    assert bars_widget.vars[key].get() == target_val
    assert entry_var.get() == str(target_val)
    assert debounce_calls == [(key, target_val, "module")]


def test_slider_row_on_entry_clamps_out_of_range_value(bars_widget, monkeypatch):
    from gui.modules import glsl_io
    captured = _capture_row_callbacks(monkeypatch)
    current = glsl_io.read_raw(bars_widget._module_glsl)
    p = bars_widget.SHAPE_PARAMS[0]
    key, vmin, vmax = p[0], p[2], p[3]
    frame = tk.Frame(bars_widget.app.root)
    debounce_calls = []
    monkeypatch.setattr(bars_widget, "_debounce",
                         lambda k, v, t: debounce_calls.append((k, v, t)))

    bars_widget._slider_row(frame, tuple(p), current, 0)
    on_entry = captured["on_entry"]
    entry_var = _closure_var(on_entry, "entry_var")

    entry_var.set(str(vmax + 100))
    on_entry(None)

    assert bars_widget.vars[key].get() == vmax
    assert debounce_calls == [(key, vmax, "module")]


def test_slider_row_on_entry_invalid_value_reverts_without_debounce(
        bars_widget, monkeypatch):
    from gui.modules import glsl_io
    captured = _capture_row_callbacks(monkeypatch)
    current = glsl_io.read_raw(bars_widget._module_glsl)
    p = bars_widget.SHAPE_PARAMS[0]
    key = p[0]
    frame = tk.Frame(bars_widget.app.root)
    debounce_calls = []
    monkeypatch.setattr(bars_widget, "_debounce",
                         lambda k, v, t: debounce_calls.append((k, v, t)))

    bars_widget._slider_row(frame, tuple(p), current, 0)
    on_entry = captured["on_entry"]
    entry_var = _closure_var(on_entry, "entry_var")

    current_var_value = bars_widget.vars[key].get()
    entry_var.set("not-a-number")
    on_entry(None)

    assert entry_var.get() == str(current_var_value)
    assert debounce_calls == []


def test_float_slider_row_on_change_snaps_value_to_step(bars_widget, monkeypatch):
    from gui.core import SMOOTH_PARAMS
    from gui.modules import glsl_io
    captured = _capture_row_callbacks(monkeypatch)
    current = glsl_io.read_smooth(bars_widget._smooth_glsl, SMOOTH_PARAMS)
    p = SMOOTH_PARAMS[0]   # setgravitystep: vmin=0.1, vmax=20.0, step=0.1
    key = p[0]
    frame = tk.Frame(bars_widget.app.root)
    debounce_calls = []
    monkeypatch.setattr(bars_widget, "_debounce",
                         lambda k, v, t: debounce_calls.append((k, v, t)))

    bars_widget._float_slider_row(frame, tuple(p), current, 0)
    on_change = captured["on_change"]

    on_change("4.23")  # krok 0.1 -> przyciągnięcie do 4.2

    assert bars_widget.vars[key].get() == pytest.approx(4.2)
    assert debounce_calls == [(key, pytest.approx(4.2), "smooth")]


def test_float_slider_row_on_change_clamps_to_vmax(bars_widget, monkeypatch):
    from gui.core import SMOOTH_PARAMS
    from gui.modules import glsl_io
    captured = _capture_row_callbacks(monkeypatch)
    current = glsl_io.read_smooth(bars_widget._smooth_glsl, SMOOTH_PARAMS)
    p = SMOOTH_PARAMS[0]
    key, vmax = p[0], p[3]
    frame = tk.Frame(bars_widget.app.root)
    debounce_calls = []
    monkeypatch.setattr(bars_widget, "_debounce",
                         lambda k, v, t: debounce_calls.append((k, v, t)))

    bars_widget._float_slider_row(frame, tuple(p), current, 0)
    on_change = captured["on_change"]

    on_change(str(vmax + 5))  # poza zakresem -> clamp do vmax

    assert bars_widget.vars[key].get() == vmax
    assert debounce_calls == [(key, vmax, "smooth")]


def test_float_slider_row_on_entry_valid_value_updates_and_debounces(
        bars_widget, monkeypatch):
    from gui.core import SMOOTH_PARAMS
    from gui.modules import glsl_io
    captured = _capture_row_callbacks(monkeypatch)
    current = glsl_io.read_smooth(bars_widget._smooth_glsl, SMOOTH_PARAMS)
    p = SMOOTH_PARAMS[0]
    key, vmin, vmax = p[0], p[2], p[3]
    frame = tk.Frame(bars_widget.app.root)
    debounce_calls = []
    monkeypatch.setattr(bars_widget, "_debounce",
                         lambda k, v, t: debounce_calls.append((k, v, t)))

    bars_widget._float_slider_row(frame, tuple(p), current, 0)
    on_entry = captured["on_entry"]
    entry_var = _closure_var(on_entry, "entry_var")

    target_val = min(vmax, vmin + 1.0)
    entry_var.set(str(target_val))
    on_entry(None)

    assert bars_widget.vars[key].get() == pytest.approx(target_val)
    assert debounce_calls
    assert debounce_calls[0][0] == key
    assert debounce_calls[0][1] == pytest.approx(target_val)
    assert debounce_calls[0][2] == "smooth"


def test_float_slider_row_on_entry_invalid_value_reverts_without_debounce(
        bars_widget, monkeypatch):
    from gui.core import SMOOTH_PARAMS
    from gui.modules import glsl_io
    captured = _capture_row_callbacks(monkeypatch)
    current = glsl_io.read_smooth(bars_widget._smooth_glsl, SMOOTH_PARAMS)
    p = SMOOTH_PARAMS[0]
    key, step = p[0], p[6]
    dec = glsl_io.decimals(step)
    frame = tk.Frame(bars_widget.app.root)
    debounce_calls = []
    monkeypatch.setattr(bars_widget, "_debounce",
                         lambda k, v, t: debounce_calls.append((k, v, t)))

    bars_widget._float_slider_row(frame, tuple(p), current, 0)
    on_entry = captured["on_entry"]
    entry_var = _closure_var(on_entry, "entry_var")

    current_var_value = bars_widget.vars[key].get()
    entry_var.set("not-a-float")
    on_entry(None)

    assert debounce_calls == []
    assert entry_var.get() == f"{current_var_value:.{dec}f}"


# ── active_instance integration ───────────────────────────────────────────────
def test_module_glsl_uses_active_instance(bars_widget, tmp_glava_dir):
    """_module_glsl zwraca ścieżkę z active_instance."""
    assert bars_widget._module_glsl == bars_widget.app.active_instance.module_glsl("bars")
def test_smooth_glsl_uses_active_instance(bars_widget, tmp_glava_dir):
    """_smooth_glsl zwraca ścieżkę z active_instance."""
    assert bars_widget._smooth_glsl == bars_widget.app.active_instance.smooth_glsl
# ── Detached panel instance routing (RC3 fix) ─────────────────────────────────

def _make_instance(tmp_path, inst_id, glava_dir=None):
    """Helper — tworzy GlavaInstance bez systemu plików."""
    from gui.instance import GlavaInstance
    inst = GlavaInstance.__new__(GlavaInstance)
    inst.inst_id   = inst_id
    d = glava_dir or str(tmp_path / f"glava-inst-{inst_id}" / "glava")
    os.makedirs(d, exist_ok=True)
    inst.glava_dir = d
    inst.xdg_dir   = os.path.dirname(d)
    inst.conf_dir  = d
    return inst


def test_frozen_instance_glsl_path(fake_app, tmp_glava_dir, tmp_path, monkeypatch):
    """Widget z zamrożoną instancją używa jej ścieżek GLSL, nie active_instance."""
    import gui.modules.bars as bars_mod
    import gui.core as core
    monkeypatch.setattr(core, "GLAVA_DIR", tmp_glava_dir)
    T = core.load_lang("pl")

    frozen = _make_instance(tmp_path, inst_id=2)

    frame = tk.Frame(fake_app.root)
    widget = bars_mod.BarsParamWidget(frame, fake_app, T, instance=frozen)

    # active_instance wskazuje na inst_id=0 (z FakeApp)
    assert fake_app.active_instance.inst_id == 0

    # Widget powinien używać ścieżek zamrożonej instancji (inst_id=2)
    assert widget._module_glsl == frozen.module_glsl("bars")
    assert widget._smooth_glsl == frozen.smooth_glsl


def test_frozen_instance_debounce_writes_to_correct_file(
        fake_app, tmp_glava_dir, tmp_path, monkeypatch):
    """_debounce zapisuje do pliku zamrożonej instancji, nie active_instance.

    Symuluje scenariusz: odpięty panel Radial (inst=2) przy aktywnej karcie
    Bars (inst=1, czyli active_instance). Zapis musi trafić do inst=2.
    """
    import shutil
    import gui.modules.bars as bars_mod
    import gui.core as core
    from gui.modules import glsl_io
    monkeypatch.setattr(core, "GLAVA_DIR", tmp_glava_dir)
    monkeypatch.setattr(fake_app.root, "after", lambda ms, fn, *a: None)
    T = core.load_lang("pl")

    src_glsl = os.path.join(tmp_glava_dir, "bars.glsl")

    # Instancja zamrożona (inst=2) — osobny katalog, kopia bars.glsl
    frozen = _make_instance(tmp_path, inst_id=2)
    if os.path.exists(src_glsl):
        shutil.copy2(src_glsl, frozen.module_glsl("bars"))

    # active_instance (inst=0) musi mieć WŁASNY katalog oddzielony od tmp_glava_dir,
    # inaczej active_glsl == src_glsl i shutil.copy2 rzuca SameFileError.
    active = _make_instance(tmp_path, inst_id=0)
    active_glsl = active.module_glsl("bars")
    if os.path.exists(src_glsl):
        shutil.copy2(src_glsl, active_glsl)
    fake_app.active_instance = active

    frame = tk.Frame(fake_app.root)
    widget = bars_mod.BarsParamWidget(frame, fake_app, T, instance=frozen)

    key     = bars_mod.SHAPE_PARAMS[0][0]   # "BAR_WIDTH"
    new_val = int(bars_mod.SHAPE_PARAMS[0][3])  # vmax

    widget._debounce(key, new_val, "module")

    # Zapis musi być w pliku zamrożonej instancji
    frozen_result = glsl_io.read_raw(frozen.module_glsl("bars"))
    assert str(new_val) in str(frozen_result.get(key, "")), \
        "Zapis nie trafił do zamrożonej instancji"

    # Plik active_instance NIE może być zmodyfikowany
    active_result = glsl_io.read_raw(active_glsl)
    assert str(new_val) not in str(active_result.get(key, "")), \
        "Zapis błędnie trafił do active_instance"


def test_frozen_instance_schedule_restart_passes_instance(
        fake_app, tmp_glava_dir, tmp_path, monkeypatch):
    """_schedule_restart przekazuje zamrożoną instancję do restart_active_instance.

    Symuluje: odpięty panel inst=2, active_instance zmieniona na inst=1.
    restart_active_instance musi dostać instance=frozen (inst=2), nie active.
    """
    import gui.modules.bars as bars_mod
    import gui.core as core
    monkeypatch.setattr(core, "GLAVA_DIR", tmp_glava_dir)
    T = core.load_lang("pl")

    frozen = _make_instance(tmp_path, inst_id=2)

    frame  = tk.Frame(fake_app.root)
    widget = bars_mod.BarsParamWidget(frame, fake_app, T, instance=frozen)

    received = {}

    def fake_restart(module=None, instance=None, after_fn=None):
        received["instance"] = instance
        received["module"]   = module

    fake_app.restart_active_instance = fake_restart

    # Symuluj zmianę aktywnej karty na inną instancję
    other = _make_instance(tmp_path, inst_id=1)
    fake_app.active_instance = other

    # after() wywołujemy synchronicznie
    monkeypatch.setattr(fake_app.root, "after",
                        lambda ms, fn, *a: fn())

    widget._schedule_restart()

    assert received.get("instance") is frozen, \
        f"restart dostał instance={received.get('instance')}, oczekiwano frozen (inst=2)"
    assert received.get("module") == "bars"
