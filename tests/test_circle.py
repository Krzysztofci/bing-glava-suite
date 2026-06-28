import os
import sys
import pytest
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import gui.modules.circle as circle_mod
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
    return circle_mod.CircleParamWidget(parent=None, app=fake_app, T=fake_app.T)


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def _find_widgets_of_type(root_widget, cls):
    """Rekurencyjnie szuka widgetów danego typu w drzewie — potrzebne, bo
    SimpleSlider tworzony w _build_position nie jest przechowywany jako
    self.X, tylko lokalnie w pętli."""
    found = []
    for child in root_widget.winfo_children():
        if isinstance(child, cls):
            found.append(child)
        found.extend(_find_widgets_of_type(child, cls))
    return found


# ── _reset_shader — dialog gate ────────────────────────────────────────────────

def test_widget_reset_shader_aborts_if_user_declines_confirm(
        widget, fake_app, monkeypatch):
    """Gdy użytkownik odmawia w dialogu potwierdzenia, reset_shader()
    i restart NIE powinny być wołane wcale — bezpieczne bez mocka
    glava_restart, bo kod powinien wrócić wcześniej."""
    monkeypatch.setattr(circle_mod.messagebox, "askyesno", lambda *a, **kw: False)
    reset_calls = []
    monkeypatch.setattr(circle_mod, "reset_shader", lambda app: reset_calls.append(app))

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
    monkeypatch.setattr(circle_mod.messagebox, "askyesno", lambda *a, **kw: True)
    reset_calls = []
    monkeypatch.setattr(circle_mod, "reset_shader", lambda app: reset_calls.append(app))
    assert not hasattr(fake_app, "restart_active_instance")

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, **kw: restart_calls.append(module))

    widget._reset_shader()

    assert reset_calls == [fake_app]
    assert fake_app.rebuild_calls == 1
    assert restart_calls == ["circle"]


def test_widget_reset_shader_falls_back_to_legacy_glava_restart(
        widget, fake_app, monkeypatch):
    """Duplikat powyższego z innym naciskiem — explicit test na samą
    ścieżkę fallbacku, zgodny ze wzorcem z test_bars.py."""
    monkeypatch.setattr(circle_mod.messagebox, "askyesno", lambda *a, **kw: True)
    monkeypatch.setattr(circle_mod, "reset_shader", lambda app: None)
    assert not hasattr(fake_app, "restart_active_instance")

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, extra_flags=None, after_fn=None:
                         restart_calls.append(module))

    widget._reset_shader()

    assert restart_calls == ["circle"]


# ── _reset_shader — multi-instancja (Z restart_active_instance) ──────────────

def test_widget_reset_shader_uses_restart_active_instance_when_available(
        widget, fake_app, monkeypatch):
    """Gdy app MA restart_active_instance, _reset_shader powinno użyć go
    zamiast legacy glava_restart — gałąź hasattr=True."""
    monkeypatch.setattr(circle_mod.messagebox, "askyesno", lambda *a, **kw: True)
    monkeypatch.setattr(circle_mod, "reset_shader", lambda app: None)

    restart_calls = []
    fake_app.restart_active_instance = (
        lambda module=None, after_fn=None: restart_calls.append(module))

    widget._reset_shader()

    assert restart_calls == ["circle"]


# ── Helpers rotacji (czyste funkcje, zero mocków potrzebnych) ────────────────

@pytest.mark.parametrize("raw,expected_deg", [
    ("0", 0),
    ("(PI / 2)", 90),
    ("PI", 180),
    ("(3 * PI / 2)", 270),
], ids=["zero", "half_pi", "pi", "three_half_pi"])
def test_rotate_to_deg_known_symbols(raw, expected_deg):
    assert circle_mod._rotate_to_deg(raw) == expected_deg


def test_rotate_to_deg_numeric_radians():
    import math
    assert circle_mod._rotate_to_deg(str(math.pi)) == 180


def test_rotate_to_deg_invalid_falls_back_to_90():
    assert circle_mod._rotate_to_deg("not_a_number") == 90


def test_deg_to_rotate_roundtrip():
    raw = circle_mod._deg_to_rotate(90)
    assert circle_mod._rotate_to_deg(raw) == 90


def test_deg_to_rotate_zero():
    raw = circle_mod._deg_to_rotate(0)
    assert circle_mod._rotate_to_deg(raw) == 0


# ── _write_rotate / _write_flag ──────────────────────────────────────────────
#
# base.py (_schedule_restart) jest już w 100% pokryte przez testy bazowe —
# tutaj NIE testujemy jego wewnętrznych gałęzi hasattr/else ponownie.
# Mockujemy _schedule_restart bezpośrednio na instancji widgetu jako czarną
# skrzynkę: zero ryzyka dotknięcia gui.glava.glava_restart, zero potrzeby
# znać szczegóły root.after.

def test_write_rotate_writes_define_and_schedules_restart(widget, monkeypatch):
    widget.rotate_var = _FakeVar(180)
    write_calls = []
    monkeypatch.setattr(circle_mod.glsl_io, "write_define_raw",
                         lambda path, key, val: write_calls.append((key, val)))
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    widget._write_rotate()

    assert write_calls == [("ROTATE", circle_mod._deg_to_rotate(180))]
    assert restart_calls == [True]


def test_write_flag_writes_flag_defines_and_schedules_restart(widget, monkeypatch):
    write_calls = []
    monkeypatch.setattr(circle_mod.glsl_io, "write_flag_defines",
                         lambda path, values, params: write_calls.append(values))
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    widget._write_flag("C_FILL", _FakeVar(True))

    assert write_calls == [{"C_FILL": 1}]
    assert restart_calls == [True]


def test_write_flag_off_writes_zero(widget, monkeypatch):
    write_calls = []
    monkeypatch.setattr(circle_mod.glsl_io, "write_flag_defines",
                         lambda path, values, params: write_calls.append(values))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    widget._write_flag("INVERT", _FakeVar(False))

    assert write_calls == [{"INVERT": 0}]


# ── _init_extra — fallback gdy get_screen_info() rzuca ──────────────────────

def test_init_extra_falls_back_to_default_screen_size_on_exception(
        fake_app, monkeypatch):
    """from ..geometry import get_screen_info -> import lokalny, patchujemy
    na ŹRÓDLE (gui.geometry), nie na circle_mod."""
    import gui.geometry as geometry_mod
    monkeypatch.setattr(
        geometry_mod, "get_screen_info",
        lambda: (_ for _ in ()).throw(RuntimeError("brak X display")))

    w = circle_mod.CircleParamWidget(parent=None, app=fake_app, T=fake_app.T)

    assert (w._sw, w._sh) == (1600, 900)


# ── _build_position — on_offset (domknięcie przekazane do SimpleSlider) ─────
#
# k/sv w on_offset to argumenty DOMYŚLNE (k=key, sv=var), nie zmienne
# domknięcia — __closure__/co_freevars złapałoby tylko 'self'. Właściwą
# wartość 'key' wyciągamy z on_offset.__defaults__[0].

def test_build_position_on_offset_rounds_updates_var_and_debounces(
        widget, root, monkeypatch):
    frame = tk.Frame(root)
    debounce_calls = []
    monkeypatch.setattr(widget, "_debounce_int",
                         lambda k, v: debounce_calls.append((k, v)))

    widget._build_position(frame, {})

    sliders = _find_widgets_of_type(frame, circle_mod.SimpleSlider)
    target = next(s for s in sliders
                   if s.on_change.__defaults__[0] == "CENTER_OFFSET_X")

    target.on_change(37.6)  # round(37.6) == 38

    assert widget.vars["CENTER_OFFSET_X"].get() == 38
    assert debounce_calls == [("CENTER_OFFSET_X", 38)]


def test_build_position_on_offset_for_y_axis(widget, root, monkeypatch):
    frame = tk.Frame(root)
    debounce_calls = []
    monkeypatch.setattr(widget, "_debounce_int",
                         lambda k, v: debounce_calls.append((k, v)))

    widget._build_position(frame, {})

    sliders = _find_widgets_of_type(frame, circle_mod.SimpleSlider)
    target = next(s for s in sliders
                   if s.on_change.__defaults__[0] == "CENTER_OFFSET_Y")

    target.on_change(-10.4)  # round(-10.4) == -10

    assert widget.vars["CENTER_OFFSET_Y"].get() == -10
    assert debounce_calls == [("CENTER_OFFSET_Y", -10)]


# ── _debounce_int — dwie gałęzie zapisu ──────────────────────────────────────

def test_debounce_int_offset_keys_write_define_raw(widget, monkeypatch):
    write_calls = []
    monkeypatch.setattr(circle_mod.glsl_io, "write_define_raw",
                         lambda path, key, val: write_calls.append((key, val)))
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    widget._debounce_int("CENTER_OFFSET_X", 42)

    assert write_calls == [("CENTER_OFFSET_X", 42)]
    assert restart_calls == [True]


def test_debounce_int_other_keys_write_defines(widget, monkeypatch):
    write_calls = []
    monkeypatch.setattr(circle_mod.glsl_io, "write_defines",
                         lambda path, values, params: write_calls.append(values))
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    widget._debounce_int("C_RADIUS", 200)

    assert write_calls == [{"C_RADIUS": 200}]
    assert restart_calls == [True]
