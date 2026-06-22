import os
import sys

import pytest
import tkinter as tk
import tkinter.ttk as ttk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from gui import widgets as widgets_mod
from gui.widgets import SimpleSlider


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Brak dostępnego displaya X (Xvfb?) — pomijam testy SimpleSlider")
    r.withdraw()  # nie pokazuj realnego okna
    yield r
    r.destroy()


# =============================================================================
# get() / set() / set_range() — TO są jedyne fragmenty tego pliku sklasyfi-
# kowane przez logic-cov jako "Logic" (11-44, 101-102, 104-108, 110-116).
# __init__/_fmt/_on_cmd/_on_release/_on_entry są klasyfikowane jako GUI —
# testujemy je też niżej dla bezpieczeństwa, ale to nie przesunie liczby
# w raporcie logic-cov.
# =============================================================================

def test_get_returns_initial_value(root):
    s = SimpleSlider(root, vmin=0, vmax=100, value=42)
    assert s.get() == 42


def test_set_clamps_to_upper_bound(root):
    s = SimpleSlider(root, vmin=0, vmax=10, value=5)
    s.set(999)
    assert s.get() == 10


def test_set_clamps_to_lower_bound(root):
    s = SimpleSlider(root, vmin=0, vmax=10, value=5)
    s.set(-50)
    assert s.get() == 0


def test_set_updates_entry_text(root):
    s = SimpleSlider(root, vmin=0, vmax=10, value=0, is_float=True, decimals=2)
    s.set(3.14159)
    assert s._entry_var.get() == "3.14"


def test_set_range_clamps_current_value_to_new_bounds(root):
    s = SimpleSlider(root, vmin=0, vmax=100, value=80)
    s.set_range(0, 50)
    assert s.get() == 50
    assert s.vmin == 0
    assert s.vmax == 50


def test_set_range_updates_bounds_without_clamping_when_in_range(root):
    s = SimpleSlider(root, vmin=0, vmax=100, value=30)
    s.set_range(10, 200)
    assert s.get() == 30
    assert s.vmin == 10
    assert s.vmax == 200


def test_set_range_clamps_to_new_lower_bound(root):
    s = SimpleSlider(root, vmin=-10, vmax=100, value=-5)
    s.set_range(0, 100)
    assert s.get() == 0


# =============================================================================
# _ensure_shift_style — guard przed podwójnym tworzeniem + fallback gdy
# pliki PNG tematu nie istnieją (a w vanilla Tk bez forest-ttk-theme
# załadowanego, naturalnie nie istnieją -> ćwiczy except Exception: za darmo).
# =============================================================================

def test_ensure_shift_style_does_not_raise_when_theme_pngs_missing(root):
    """Z domyślnym (nie-forest) tematem Tk pliki PNG nie istnieją -> funkcja
    powinna trafić w except Exception: i bezpiecznie skonfigurować fallback
    styl, bez crashowania."""
    widgets_mod._ensure_shift_style(root)  # nie powinno podnieść wyjątku


def test_ensure_shift_style_sets_guard_flag(root):
    widgets_mod._ensure_shift_style(root)
    theme_name = ttk.Style(root).theme_use()
    assert getattr(root, f"_shift_style_created_{theme_name}", False) is True


def test_ensure_shift_style_skips_second_call_for_same_theme(root):
    widgets_mod._ensure_shift_style(root)
    # Druga wywołanie dla tego samego motywu powinno wrócić od razu przez
    # early-return (key już ustawiony) — nie powinno podnieść wyjątku
    # nawet jeśli coś w środku by się zepsuło.
    widgets_mod._ensure_shift_style(root)


# =============================================================================
# __init__ / _fmt / _on_cmd / _on_release / _on_entry — klasyfikowane jako
# GUI przez logic-cov (nie przesuwają %), ale to prawdziwa logika biznesowa
# (zaokrąglanie do step, clamp do zakresu, walidacja entry) — testujemy dla
# bezpieczeństwa/regresji, niezależnie od wpływu na raport.
# =============================================================================

def test_fmt_integer_rounds_not_truncates(root):
    s = SimpleSlider(root, vmin=0, vmax=100, value=7, is_float=False)
    assert s._fmt(7.6) == "8"


def test_fmt_float_respects_decimals(root):
    s = SimpleSlider(root, vmin=0, vmax=10, value=1, is_float=True, decimals=2)
    assert s._fmt(3.14159) == "3.14"


def test_on_cmd_rounds_to_step(root):
    s = SimpleSlider(root, vmin=0, vmax=100, value=0, step=5)
    s._on_cmd("13")
    assert s.get() == 15  # zaokrąglone do najbliższego wielokrotności step=5


def test_on_cmd_clamps_to_range(root):
    s = SimpleSlider(root, vmin=0, vmax=20, value=0, step=1)
    s._on_cmd("999")
    assert s.get() == 20


def test_on_cmd_no_step_rounding_when_step_zero(root):
    s = SimpleSlider(root, vmin=0, vmax=100, value=0, step=0)
    s._on_cmd("37.4")
    assert s.get() == 37.4


def test_on_release_calls_on_change_with_current_value(root):
    calls = []
    s = SimpleSlider(root, vmin=0, vmax=100, value=50,
                      on_change=lambda v: calls.append(v))
    s._on_cmd("77")
    s._on_release(None)
    assert calls == [77]


def test_on_release_without_on_change_does_not_raise(root):
    s = SimpleSlider(root, vmin=0, vmax=100, value=50, on_change=None)
    s._on_release(None)


def test_on_entry_valid_value_updates_and_calls_on_change(root):
    calls = []
    s = SimpleSlider(root, vmin=0, vmax=100, value=0,
                      on_change=lambda v: calls.append(v))
    s._entry_var.set("88")
    s._on_entry(None)
    assert s.get() == 88
    assert calls == [88]


def test_on_entry_invalid_value_reverts_to_previous(root):
    s = SimpleSlider(root, vmin=0, vmax=100, value=42)
    s._entry_var.set("not a number")
    s._on_entry(None)
    assert s.get() == 42
    assert s._entry_var.get() == "42"


def test_on_entry_clamps_to_range(root):
    s = SimpleSlider(root, vmin=0, vmax=10, value=5)
    s._entry_var.set("500")
    s._on_entry(None)
    assert s.get() == 10
