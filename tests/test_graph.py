import os
import sys
import pytest
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import gui.modules.graph as graph_mod
import gui.modules.glsl_io as glsl_io


# ── Fakes ─────────────────────────────────────────────────────────────────────

class FakeT(dict):
    pass


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
    return graph_mod.GraphParamWidget(parent=None, app=fake_app, T=fake_app.T)


# ── _reset_shader — dialog gate ────────────────────────────────────────────────

def test_widget_reset_shader_aborts_if_user_declines_confirm(
        widget, fake_app, monkeypatch):
    """Gdy użytkownik odmawia w dialogu potwierdzenia, reset_shader()
    i restart NIE powinny być wołane wcale — bezpieczne bez mocka
    glava_restart, bo kod powinien wrócić wcześniej."""
    monkeypatch.setattr(graph_mod.messagebox, "askyesno", lambda *a, **kw: False)
    reset_calls = []
    monkeypatch.setattr(graph_mod, "reset_shader", lambda app: reset_calls.append(app))

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
    monkeypatch.setattr(graph_mod.messagebox, "askyesno", lambda *a, **kw: True)
    reset_calls = []
    monkeypatch.setattr(graph_mod, "reset_shader", lambda app: reset_calls.append(app))
    assert not hasattr(fake_app, "restart_active_instance")

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, **kw: restart_calls.append(module))

    widget._reset_shader()

    assert reset_calls == [fake_app]
    assert fake_app.rebuild_calls == 1
    assert restart_calls == ["graph"]


def test_widget_reset_shader_falls_back_to_legacy_glava_restart(
        widget, fake_app, monkeypatch):
    """Duplikat powyższego z naciskiem na samą ścieżkę fallbacku, zgodny
    ze wzorcem z test_bars.py / test_circle.py."""
    monkeypatch.setattr(graph_mod.messagebox, "askyesno", lambda *a, **kw: True)
    monkeypatch.setattr(graph_mod, "reset_shader", lambda app: None)
    assert not hasattr(fake_app, "restart_active_instance")

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, extra_flags=None, after_fn=None:
                         restart_calls.append(module))

    widget._reset_shader()

    assert restart_calls == ["graph"]


# ── _reset_shader — multi-instancja (Z restart_active_instance) ──────────────

def test_widget_reset_shader_uses_restart_active_instance_when_available(
        widget, fake_app, monkeypatch):
    """Gdy app MA restart_active_instance, _reset_shader powinno użyć go
    zamiast legacy glava_restart — gałąź hasattr=True."""
    monkeypatch.setattr(graph_mod.messagebox, "askyesno", lambda *a, **kw: True)
    monkeypatch.setattr(graph_mod, "reset_shader", lambda app: None)

    restart_calls = []
    fake_app.restart_active_instance = (
        lambda module=None, after_fn=None: restart_calls.append(module))

    widget._reset_shader()

    assert restart_calls == ["graph"]


# ── _write_flag ───────────────────────────────────────────────────────────────
#
# base.py (_schedule_restart) jest już w 100% pokryte przez testy bazowe —
# tutaj mockujemy _schedule_restart bezpośrednio na instancji, jako czarną
# skrzynkę. Zero ryzyka dotknięcia gui.glava.glava_restart.

class _FakeVar:
    """Lekki zamiennik tk.BooleanVar — bez potrzeby realnego Tk root."""
    def __init__(self, value):
        self._v = value

    def get(self):
        return self._v


def test_write_flag_normal_on_writes_one(widget, monkeypatch):
    write_calls = []
    monkeypatch.setattr(graph_mod.glsl_io, "write_flag_defines",
                         lambda path, values, params: write_calls.append(values))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    widget._write_flag("DRAW_OUTLINE", _FakeVar(True))

    assert write_calls == [{"DRAW_OUTLINE": 1}]


def test_write_flag_normal_off_writes_zero(widget, monkeypatch):
    write_calls = []
    monkeypatch.setattr(graph_mod.glsl_io, "write_flag_defines",
                         lambda path, values, params: write_calls.append(values))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    widget._write_flag("DRAW_OUTLINE", _FakeVar(False))

    assert write_calls == [{"DRAW_OUTLINE": 0}]


def test_write_flag_direction_off_writes_minus_one(widget, monkeypatch):
    """DIRECTION ma niestandardową semantykę: 1=włączony, -1=wyłączony."""
    write_calls = []
    monkeypatch.setattr(graph_mod.glsl_io, "write_flag_defines",
                         lambda path, values, params: write_calls.append(values))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    widget._write_flag("DIRECTION", _FakeVar(False))

    assert write_calls == [{"DIRECTION": -1}]


def test_write_flag_invert_calls_update_geometry(widget, monkeypatch):
    """key == INVERT i włączony -> musi wywołać _update_geometry_for_flip(True)."""
    monkeypatch.setattr(graph_mod.glsl_io, "write_flag_defines", lambda *a, **kw: None)
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    geometry_calls = []
    monkeypatch.setattr(widget, "_update_geometry_for_flip",
                         lambda flipped: geometry_calls.append(flipped))

    widget._write_flag("INVERT", _FakeVar(True))

    assert geometry_calls == [True]


def test_write_flag_non_invert_does_not_call_update_geometry(widget, monkeypatch):
    monkeypatch.setattr(graph_mod.glsl_io, "write_flag_defines", lambda *a, **kw: None)
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    geometry_calls = []
    monkeypatch.setattr(widget, "_update_geometry_for_flip",
                         lambda flipped: geometry_calls.append(flipped))

    widget._write_flag("JOIN_CHANNELS", _FakeVar(True))

    assert geometry_calls == []


# ── _update_geometry_for_flip ─────────────────────────────────────────────────
#
# Lokalny import 'from ..geometry import ...' wewnątrz funkcji — mockujemy
# moduł gui.geometry bezpośrednio, żeby NIE odpalać prawdziwego xrandr/lscpu
# (widzianych w oryginalnym syscall trace tego projektu).

def test_update_geometry_for_flip_writes_geometry(widget, monkeypatch):
    import gui.geometry as geometry_mod
    monkeypatch.setattr(geometry_mod, "get_screen_info",
                         lambda: (1600, 900, 860, 40, 0, 0, 0))
    monkeypatch.setattr(geometry_mod, "calc_geometry",
                         lambda *a, **kw: (10, 20, 300, 400))
    write_calls = []
    monkeypatch.setattr(geometry_mod, "write_geometry",
                         lambda rc_path, x, y, w, h: write_calls.append((x, y, w, h)))

    widget._update_geometry_for_flip(True)

    assert write_calls == [(10, 20, 300, 400)]


def test_update_geometry_for_flip_swallows_exceptions(widget, monkeypatch):
    """Błąd w detekcji ekranu (np. brak X w CI) nie powinien crashować —
    funkcja ma broad except Exception: pass."""
    import gui.geometry as geometry_mod
    monkeypatch.setattr(geometry_mod, "get_screen_info",
                         lambda: (_ for _ in ()).throw(RuntimeError("no display")))

    widget._update_geometry_for_flip(True)  # nie powinno podnieść wyjątku
