import os
import sys
import pytest
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import gui.modules.radial as radial_mod
import gui.modules.glsl_io as glsl_io


# ── Fakes ─────────────────────────────────────────────────────────────────────

class FakeT(dict):
    pass


class _FakeVar:
    """Lekki zamiennik tk.IntVar/BooleanVar — bez potrzeby realnego Tk root."""
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
    return radial_mod.RadialParamWidget(parent=None, app=fake_app, T=fake_app.T)


# ── _reset_shader — dialog gate ────────────────────────────────────────────────

def test_widget_reset_shader_aborts_if_user_declines_confirm(
        widget, fake_app, monkeypatch):
    monkeypatch.setattr(radial_mod.messagebox, "askyesno", lambda *a, **kw: False)
    reset_calls = []
    monkeypatch.setattr(radial_mod, "reset_shader", lambda app: reset_calls.append(app))

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
    monkeypatch.setattr(radial_mod.messagebox, "askyesno", lambda *a, **kw: True)
    reset_calls = []
    monkeypatch.setattr(radial_mod, "reset_shader", lambda app: reset_calls.append(app))
    assert not hasattr(fake_app, "restart_active_instance")

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, **kw: restart_calls.append(module))

    widget._reset_shader()

    assert reset_calls == [fake_app]
    assert fake_app.rebuild_calls == 1
    assert restart_calls == ["radial"]


def test_widget_reset_shader_falls_back_to_legacy_glava_restart(
        widget, fake_app, monkeypatch):
    monkeypatch.setattr(radial_mod.messagebox, "askyesno", lambda *a, **kw: True)
    monkeypatch.setattr(radial_mod, "reset_shader", lambda app: None)
    assert not hasattr(fake_app, "restart_active_instance")

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, extra_flags=None, after_fn=None:
                         restart_calls.append(module))

    widget._reset_shader()

    assert restart_calls == ["radial"]


# ── _reset_shader — multi-instancja (Z restart_active_instance) ──────────────

def test_widget_reset_shader_uses_restart_active_instance_when_available(
        widget, fake_app, monkeypatch):
    monkeypatch.setattr(radial_mod.messagebox, "askyesno", lambda *a, **kw: True)
    monkeypatch.setattr(radial_mod, "reset_shader", lambda app: None)

    restart_calls = []
    fake_app.restart_active_instance = (
        lambda module=None, after_fn=None: restart_calls.append(module))

    widget._reset_shader()

    assert restart_calls == ["radial"]


# ── _write_rotate / _write_flag ──────────────────────────────────────────────
#
# base.py (_schedule_restart) jest już w 100% pokryte przez testy bazowe —
# tutaj mockujemy _schedule_restart bezpośrednio na instancji, jako czarną
# skrzynkę. Zero ryzyka dotknięcia gui.glava.glava_restart.

def test_write_rotate_writes_define_and_schedules_restart(widget, monkeypatch):
    widget.rotate_var = _FakeVar(270)
    write_calls = []
    monkeypatch.setattr(radial_mod.glsl_io, "write_define_raw",
                         lambda path, key, val: write_calls.append((key, val)))
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    widget._write_rotate()

    assert write_calls == [("ROTATE", radial_mod._deg_to_rotate(270))]
    assert restart_calls == [True]


def test_write_flag_on_writes_one(widget, monkeypatch):
    """radial._write_flag używa write_define_int, NIE write_flag_defines
    (inny mechanizm niż circle/graph) — uwaga przy mockowaniu."""
    write_calls = []
    monkeypatch.setattr(radial_mod.glsl_io, "write_define_int",
                         lambda path, key, val: write_calls.append((key, val)))
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    widget._write_flag("INVERT", _FakeVar(True))

    assert write_calls == [("INVERT", 1)]
    assert restart_calls == [True]


def test_write_flag_off_writes_zero(widget, monkeypatch):
    write_calls = []
    monkeypatch.setattr(radial_mod.glsl_io, "write_define_int",
                         lambda path, key, val: write_calls.append((key, val)))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    widget._write_flag("INVERT", _FakeVar(False))

    assert write_calls == [("INVERT", 0)]


# ── Helpers rotacji (czyste funkcje) ──────────────────────────────────────────

@pytest.mark.parametrize("raw,expected_deg", [
    ("0", 0),
    ("(PI/2)", 90),
    ("PI", 180),
    ("(3*PI/2)", 270),
], ids=["zero", "half_pi", "pi", "three_half_pi"])
def test_rotate_to_deg_known_symbols(raw, expected_deg):
    assert radial_mod._rotate_to_deg(raw) == expected_deg


def test_rotate_to_deg_strips_internal_spaces():
    """radial._rotate_to_deg robi .replace(' ', '') — różni się od circle."""
    assert radial_mod._rotate_to_deg("( PI / 2 )") == 90


def test_rotate_to_deg_invalid_falls_back_to_90():
    assert radial_mod._rotate_to_deg("not_a_number") == 90


def test_deg_to_rotate_roundtrip():
    raw = radial_mod._deg_to_rotate(90)
    assert radial_mod._rotate_to_deg(raw) == 90


# ── _init_extra — fallback gdy get_screen_info() rzuca ──────────────────────

def test_init_extra_falls_back_to_default_screen_size_on_exception(
        fake_app, monkeypatch):
    """get_screen_info importowane na TOP-LEVEL (from ..geometry import
    get_screen_info) -> patchujemy na module-pod-testem (radial_mod), nie
    na źródle, w przeciwieństwie do circle.py gdzie import jest lokalny."""
    monkeypatch.setattr(
        radial_mod, "get_screen_info",
        lambda: (_ for _ in ()).throw(RuntimeError("brak X display")))

    w = radial_mod.RadialParamWidget(parent=None, app=fake_app, T=fake_app.T)

    assert (w._sw, w._sh) == (1600, 900)
