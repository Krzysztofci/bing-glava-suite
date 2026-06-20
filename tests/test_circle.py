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
