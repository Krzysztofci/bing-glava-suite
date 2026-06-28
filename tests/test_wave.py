import os
import sys
import pytest
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import gui.modules.wave as wave_mod
import gui.modules.glsl_io as glsl_io


# ── Fakes ─────────────────────────────────────────────────────────────────────

class FakeT(dict):
    pass


class _FakeVar:
    """Lekki zamiennik tk.IntVar/BooleanVar/SimpleSlider (.get/.set) —
    bez potrzeby realnego Tk root."""
    def __init__(self, value):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class FakeInstance:
    def __init__(self, base_dir, name="inst"):
        self.base_dir = base_dir
        self.name = name
        self.smooth_glsl = os.path.join(base_dir, f"{name}_smooth.glsl")

    def module_glsl(self, module):
        return os.path.join(self.base_dir, f"{self.name}_{module}.glsl")

    def module_tmpl(self, module):
        return os.path.join(self.base_dir, f"{self.name}_{module}_tmpl.frag")

    def module_frag(self, module):
        return os.path.join(self.base_dir, f"{self.name}_{module}_live.frag")


class FakeApp:
    def __init__(self, tmp_path):
        self.T = FakeT()
        self.root = type("FakeRoot", (), {
            "after": staticmethod(lambda delay, fn: fn()),
            "after_cancel": staticmethod(lambda job: None),
        })()
        self.active_instance = FakeInstance(str(tmp_path), "inst0")
        self.update_status_calls = 0
        self.rebuild_calls = 0

    def update_status(self):
        self.update_status_calls += 1

    def rebuild_module_tab(self):
        self.rebuild_calls += 1


@pytest.fixture
def fake_app(tmp_path):
    return FakeApp(tmp_path)


@pytest.fixture
def widget(fake_app):
    return wave_mod.WaveParamWidget(parent=None, app=fake_app, T=fake_app.T)


# ── _reset_shader — dialog gate ────────────────────────────────────────────────

def test_widget_reset_shader_aborts_if_user_declines_confirm(
        widget, fake_app, monkeypatch):
    monkeypatch.setattr(wave_mod.messagebox, "askyesno", lambda *a, **kw: False)
    reset_calls = []
    monkeypatch.setattr(wave_mod, "reset_shader", lambda app: reset_calls.append(app))

    widget._reset_shader()

    assert reset_calls == []
    assert fake_app.rebuild_calls == 0


# ── _reset_shader — legacy fallback (BEZ restart_active_instance) ────────────

def test_widget_reset_shader_calls_module_reset_and_rebuilds(
        widget, fake_app, monkeypatch):
    """fake_app NIE ma restart_active_instance -> kod spada na legacy
    glava_restart (hasattr-check w _reset_shader). MUSI być zamockowane
    explicite, inaczej trafia w prawdziwy gui.glava.glava_restart() i
    startuje realny proces glava --desktop (patrz: incydent w bars.py)."""
    monkeypatch.setattr(wave_mod.messagebox, "askyesno", lambda *a, **kw: True)
    reset_calls = []
    monkeypatch.setattr(wave_mod, "reset_shader", lambda app: reset_calls.append(app))
    assert not hasattr(fake_app, "restart_active_instance")

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, **kw: restart_calls.append(module))

    widget._reset_shader()

    assert reset_calls == [fake_app]
    assert fake_app.rebuild_calls == 1
    assert restart_calls == ["wave"]


def test_widget_reset_shader_falls_back_to_legacy_glava_restart(
        widget, fake_app, monkeypatch):
    monkeypatch.setattr(wave_mod.messagebox, "askyesno", lambda *a, **kw: True)
    monkeypatch.setattr(wave_mod, "reset_shader", lambda app: None)
    assert not hasattr(fake_app, "restart_active_instance")

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, extra_flags=None, after_fn=None:
                         restart_calls.append(module))

    widget._reset_shader()

    assert restart_calls == ["wave"]


# ── _reset_shader — multi-instancja (Z restart_active_instance) ──────────────

def test_widget_reset_shader_uses_restart_active_instance_when_available(
        widget, fake_app, monkeypatch):
    monkeypatch.setattr(wave_mod.messagebox, "askyesno", lambda *a, **kw: True)
    monkeypatch.setattr(wave_mod, "reset_shader", lambda app: None)

    restart_calls = []
    fake_app.restart_active_instance = (
        lambda module=None, after_fn=None: restart_calls.append(module))

    widget._reset_shader()

    assert restart_calls == ["wave"]


# ── _on_offset / _write_shape ────────────────────────────────────────────────
#
# base.py (_schedule_restart) jest już w 100% pokryte przez testy bazowe —
# tutaj mockujemy _schedule_restart bezpośrednio na instancji, jako czarną
# skrzynkę. Zero ryzyka dotknięcia gui.glava.glava_restart.

def test_on_offset_writes_define_int_and_schedules_restart(widget, monkeypatch):
    write_calls = []
    monkeypatch.setattr(wave_mod.glsl_io, "write_define_int",
                         lambda path, key, val: write_calls.append((key, val)))
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    widget._on_offset("CENTER_OFFSET_X", 42)

    assert write_calls == [("CENTER_OFFSET_X", 42)]
    assert restart_calls == [True]


def test_write_shape_writes_defines_and_schedules_restart(widget, monkeypatch):
    write_calls = []
    monkeypatch.setattr(wave_mod.glsl_io, "write_defines",
                         lambda path, values, params: write_calls.append(values))
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    widget._write_shape("MIN_THICKNESS", 5)

    assert write_calls == [{"MIN_THICKNESS": 5}]
    assert restart_calls == [True]


# ── _init_extra — fallback gdy get_screen_info() rzuca ──────────────────────

def test_init_extra_falls_back_to_default_diag_and_half_sizes_on_exception(
        fake_app, monkeypatch):
    """from ..geometry import get_screen_info -> import LOKALNY wewnątrz
    _init_extra -> patchujemy na ŹRÓDLE (gui.geometry), nie na wave_mod."""
    import gui.geometry as geometry_mod
    monkeypatch.setattr(
        geometry_mod, "get_screen_info",
        lambda: (_ for _ in ()).throw(RuntimeError("brak X display")))

    w = wave_mod.WaveParamWidget(parent=None, app=fake_app, T=fake_app.T)

    assert w._diag == 1920
    assert w._half_x == 800
    assert w._half_y == 450


# ── _on_unlock_toggle — rozszerzanie/ograniczanie zakresów sliderów ─────────

def test_on_unlock_toggle_unlocked_expands_ranges(widget):
    calls = {}

    class _FakeSlider:
        def __init__(self, name):
            self.name = name

        def set_range(self, lo, hi):
            calls[self.name] = (lo, hi)

    widget._diag = 1000
    widget._half_x = 400
    widget._half_y = 300
    widget._unlock_var = _FakeVar(True)
    widget._accel_sliders = {
        "WAVE_LENGTH": _FakeSlider("WAVE_LENGTH"),
        "CENTER_OFFSET_X": _FakeSlider("CENTER_OFFSET_X"),
        "CENTER_OFFSET_Y": _FakeSlider("CENTER_OFFSET_Y"),
    }

    widget._on_unlock_toggle()

    assert calls["WAVE_LENGTH"] == (0, 3000)
    assert calls["CENTER_OFFSET_X"] == (-1000, 1000)
    assert calls["CENTER_OFFSET_Y"] == (-1000, 1000)


def test_on_unlock_toggle_locked_restricts_ranges(widget):
    calls = {}

    class _FakeSlider:
        def __init__(self, name):
            self.name = name

        def set_range(self, lo, hi):
            calls[self.name] = (lo, hi)

    widget._diag = 1000
    widget._half_x = 400
    widget._half_y = 300
    widget._unlock_var = _FakeVar(False)
    widget._accel_sliders = {
        "WAVE_LENGTH": _FakeSlider("WAVE_LENGTH"),
        "CENTER_OFFSET_X": _FakeSlider("CENTER_OFFSET_X"),
        "CENTER_OFFSET_Y": _FakeSlider("CENTER_OFFSET_Y"),
    }

    widget._on_unlock_toggle()

    assert calls["WAVE_LENGTH"] == (0, 1000)
    assert calls["CENTER_OFFSET_X"] == (-400, 400)
    assert calls["CENTER_OFFSET_Y"] == (-300, 300)


def test_on_unlock_toggle_missing_sliders_are_safely_skipped(widget):
    """Gdy _accel_sliders nie ma jeszcze danego klucza (np. wywołane przed
    pełnym build()), guard 'if s:'/'if sx:'/'if sy:' musi to bezpiecznie
    pominąć, bez crashu."""
    widget._diag = 1000
    widget._half_x = 400
    widget._half_y = 300
    widget._unlock_var = _FakeVar(True)
    widget._accel_sliders = {}

    widget._on_unlock_toggle()  # nie powinno podnieść wyjątku


# ── _clamp_thickness — wzajemne ograniczanie MIN/MAX_THICKNESS ─────────────

def test_clamp_thickness_min_raises_max_when_below(widget, monkeypatch):
    widget.vars["MIN_THICKNESS"] = _FakeVar(5)
    widget.vars["MAX_THICKNESS"] = _FakeVar(3)
    fake_max_slider = _FakeVar(3)
    widget._accel_sliders = {"MAX_THICKNESS": fake_max_slider}
    write_calls = []
    monkeypatch.setattr(wave_mod.glsl_io, "write_defines",
                         lambda path, values, params: write_calls.append(values))

    result = widget._clamp_thickness("MIN_THICKNESS", 5)

    assert widget.vars["MAX_THICKNESS"].get() == 5
    assert fake_max_slider.get() == 5
    assert write_calls == [{"MAX_THICKNESS": 5}]
    assert result == 5


def test_clamp_thickness_max_raises_min_when_above(widget, monkeypatch):
    widget.vars["MIN_THICKNESS"] = _FakeVar(5)
    widget.vars["MAX_THICKNESS"] = _FakeVar(10)
    fake_min_slider = _FakeVar(5)
    widget._accel_sliders = {"MIN_THICKNESS": fake_min_slider}
    write_calls = []
    monkeypatch.setattr(wave_mod.glsl_io, "write_defines",
                         lambda path, values, params: write_calls.append(values))

    result = widget._clamp_thickness("MAX_THICKNESS", 2)

    assert widget.vars["MIN_THICKNESS"].get() == 2
    assert fake_min_slider.get() == 2
    assert write_calls == [{"MIN_THICKNESS": 2}]
    assert result == 2


def test_clamp_thickness_no_adjustment_needed(widget, monkeypatch):
    widget.vars["MIN_THICKNESS"] = _FakeVar(2)
    widget.vars["MAX_THICKNESS"] = _FakeVar(10)
    write_calls = []
    monkeypatch.setattr(wave_mod.glsl_io, "write_defines",
                         lambda path, values, params: write_calls.append(values))

    result = widget._clamp_thickness("MIN_THICKNESS", 5)  # 5 <= 10 -> bez zmian

    assert write_calls == []
    assert result == 5


def test_clamp_thickness_skips_safely_when_counterpart_var_missing(widget, monkeypatch):
    """Brak MAX_THICKNESS w self.vars -> guard 'and \"MAX_THICKNESS\" in
    self.vars' musi to bezpiecznie pominąć, bez KeyError."""
    widget.vars.pop("MAX_THICKNESS", None)
    write_calls = []
    monkeypatch.setattr(wave_mod.glsl_io, "write_defines",
                         lambda path, values, params: write_calls.append(values))

    result = widget._clamp_thickness("MIN_THICKNESS", 5)  # nie powinno podnieść wyjątku

    assert write_calls == []
    assert result == 5
