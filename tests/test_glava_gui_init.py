# =============================================================================
# tests/test_glava_gui_init.py
#
# Testy dla GlavaGUI.__init__ i _setup_window — JEDYNE miejsce w testach
# glava-gui.py, gdzie wołamy PRAWDZIWY __init__ (wszystkie inne testy w
# projekcie używają GlavaGUI.__new__() właśnie żeby tego uniknąć, bo __init__
# buduje całe okno Tk). Wymaga realnego tk.Tk() — pod Xvfb w CI/headless.
#
# UWAGA: __init__ samo nie robi żadnych lokalnych importów, ale woła
# _load_saved_instances(), która ma swój WŁASNY lokalny import
# (from gui.instance import load_instances) — to jest już przetestowane
# osobno w test_glava_gui_instances.py, więc tutaj _load_saved_instances
# jest zaślepiana (monkeypatch na klasie), nie wołana naprawdę.
# =============================================================================

import importlib.util
import os
import sys

import pytest
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'glava-gui.py')


def _load_glava_gui_module():
    spec = importlib.util.spec_from_file_location("glava_gui_under_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gg():
    return _load_glava_gui_module()


@pytest.fixture
def tk_root():
    """Świeży, realny tk.Tk() per test — __init__/_setup_window mutują
    geometrię/protocol/bind na rootcie, więc izolujemy między testami."""
    root = tk.Tk()
    yield root
    root.destroy()


def _stub_build_methods(gg, monkeypatch, calls=None):
    """Zaślepia _build_header/_build_notebook/_build_statusbar/
    _schedule_status_update na klasie — to czysty GUI-layout/scheduling,
    pomijany w tym projekcie (patrz konwencja z tab_main.py/tab_advanced.py).
    Jeśli podano `calls`, każde wywołanie jest tam logowane (do testu
    porządku wywołań)."""
    names = ("_build_header", "_build_notebook", "_build_statusbar",
             "_schedule_status_update")
    for name in names:
        def make_stub(n):
            def stub(self):
                if calls is not None:
                    calls.append(n)
            return stub
        monkeypatch.setattr(gg.GlavaGUI, name, make_stub(name))


def _stub_loaders(gg, monkeypatch, settings=None, lang=None, langs=None,
                   active_module="bars", gui_conf=None):
    monkeypatch.setattr(gg, "load_settings", lambda: settings or {"lang": "pl"})
    monkeypatch.setattr(gg, "load_lang", lambda code: lang if lang is not None else {})
    monkeypatch.setattr(gg, "available_langs", lambda: langs or {"pl": "Polski", "en": "English"})
    monkeypatch.setattr(gg, "read_active_module", lambda: active_module)
    monkeypatch.setattr(gg, "load_gui_conf", lambda: gui_conf if gui_conf is not None else {})


# ── __init__ ──────────────────────────────────────────────────────────────────

def test_init_wires_settings_lang_module_and_conf_from_loaders(gg, monkeypatch, tk_root):
    _stub_loaders(gg, monkeypatch,
                  settings={"lang": "en"}, lang={"ok": "OK"}, langs={"en": "English"},
                  active_module="wave", gui_conf={"width": 900})
    _stub_build_methods(gg, monkeypatch)
    monkeypatch.setattr(gg.GlavaGUI, "_load_saved_instances", lambda self: None)

    gui = gg.GlavaGUI(tk_root)

    assert gui.settings == {"lang": "en"}
    assert gui.T == {"ok": "OK"}
    assert gui.langs == {"en": "English"}
    assert gui.active_module == "wave"
    assert gui.gui_conf == {"width": 900}


def test_init_sets_active_instance_from_first_loaded_instance(gg, monkeypatch, tk_root):
    """_load_saved_instances() (zaślepione) symuluje wczytanie 2 instancji —
    __init__ musi wybrać PIERWSZĄ z self.instances jako aktywną."""
    _stub_loaders(gg, monkeypatch)
    _stub_build_methods(gg, monkeypatch)

    inst5, inst9 = object(), object()

    def fake_load(self):
        self.instances = {5: inst5, 9: inst9}
        self.processes = {5: None, 9: None}
        self._inst_modules = {5: "bars", 9: "wave"}
    monkeypatch.setattr(gg.GlavaGUI, "_load_saved_instances", fake_load)

    gui = gg.GlavaGUI(tk_root)

    assert gui._active_inst_id == 5
    assert gui.active_instance is inst5


def test_init_leaves_active_instance_none_when_no_saved_instances(gg, monkeypatch, tk_root):
    """Świeży install / wszystkie instancje sprzątnięte — brak crashu,
    active_instance/_active_inst_id pozostają None."""
    _stub_loaders(gg, monkeypatch)
    _stub_build_methods(gg, monkeypatch)

    def fake_load(self):
        self.instances = {}
        self.processes = {}
        self._inst_modules = {}
    monkeypatch.setattr(gg.GlavaGUI, "_load_saved_instances", fake_load)

    gui = gg.GlavaGUI(tk_root)

    assert gui._active_inst_id is None
    assert gui.active_instance is None


def test_init_binds_close_protocol_and_configure_handler(gg, monkeypatch, tk_root):
    _stub_loaders(gg, monkeypatch)
    _stub_build_methods(gg, monkeypatch)
    monkeypatch.setattr(gg.GlavaGUI, "_load_saved_instances", lambda self: None)

    gui = gg.GlavaGUI(tk_root)

    # query-only wywołanie .protocol()/.bind() (bez func) zwraca aktualne
    # wiązanie — realna weryfikacja przez Tk, nie przez podsłuch wywołania.
    assert tk_root.protocol("WM_DELETE_WINDOW") != ""
    assert tk_root.bind("<Configure>") != ""
    assert gui._resize_after is None


def test_init_calls_setup_and_build_methods_in_expected_order(gg, monkeypatch, tk_root):
    _stub_loaders(gg, monkeypatch)
    monkeypatch.setattr(gg.GlavaGUI, "_load_saved_instances", lambda self: None)

    calls = []
    _stub_build_methods(gg, monkeypatch, calls=calls)
    monkeypatch.setattr(gg.GlavaGUI, "_setup_window",
                         lambda self: calls.append("_setup_window"))

    gg.GlavaGUI(tk_root)

    assert calls == ["_setup_window", "_build_header", "_build_notebook",
                      "_build_statusbar", "_schedule_status_update"]


# ── _setup_window ─────────────────────────────────────────────────────────────
# Wołane przez __new__() bypass + ręcznie wstrzyknięty root/gui_conf, zgodnie
# z konwencją resztу testów GlavaGUI. Asercje liczone DYNAMICZNIE z realnego
# winfo_screenwidth()/winfo_screenheight() — niezależnie od rozdzielczości
# Xvfb na danej maszynie/CI, zamiast zakładać konkretne 1280x1024.

def _make_gui(gg, tk_root, gui_conf):
    gui = gg.GlavaGUI.__new__(gg.GlavaGUI)
    gui.root = tk_root
    gui.gui_conf = gui_conf
    return gui


def _screen_size(tk_root):
    tk_root.update_idletasks()
    return tk_root.winfo_screenwidth(), tk_root.winfo_screenheight()


def test_setup_window_centers_when_no_saved_position(gg, tk_root):
    sw, sh = _screen_size(tk_root)
    gui = _make_gui(gg, tk_root, {"width": 1040, "height": 768})

    gui._setup_window()

    tk_root.update_idletasks()
    assert tk_root.winfo_width() == 1040
    assert tk_root.winfo_height() == 768
    assert tk_root.winfo_x() == (sw - 1040) // 2
    assert tk_root.winfo_y() == (sh - 768) // 2


def test_setup_window_uses_saved_position_when_within_screen_bounds(gg, tk_root):
    """Rozmiar = WIN_W_MIN/WIN_H_MIN (600x460), nie domyślny 1040x768 —
    1040 bywa SZERSZE niż realny ekran headless (np. Xvfb 1024x768 w CI
    tego projektu), co fałszywie wpadało w clamp przy x=10. 600x460 + małe
    x/y to bezpieczne 'w granicach' na każdym sensownym ekranie."""
    gui = _make_gui(gg, tk_root, {"width": 600, "height": 460, "x": 10, "y": 10})

    gui._setup_window()

    tk_root.update_idletasks()
    assert tk_root.winfo_x() == 10
    assert tk_root.winfo_y() == 10


def test_setup_window_clamps_negative_saved_position_to_zero(gg, tk_root):
    gui = _make_gui(gg, tk_root, {"width": 1040, "height": 768, "x": -500, "y": -500})

    gui._setup_window()

    tk_root.update_idletasks()
    assert tk_root.winfo_x() == 0
    assert tk_root.winfo_y() == 0


def test_setup_window_clamps_oversized_saved_position_to_screen_edge(gg, tk_root):
    """Rozmiar = WIN_W_MIN/WIN_H_MIN, z tej samej przyczyny co wyżej:
    realna formuła w źródle to max(0, min(x, sw - w)) — przy w większym
    od ekranu (sw - w < 0) oczekiwana wartość to 0, NIE samo (sw - w)
    wzięte bez clampu (to był błąd w tym teście, nie w kodzie)."""
    sw, sh = _screen_size(tk_root)
    gui = _make_gui(gg, tk_root, {"width": 600, "height": 460, "x": 999999, "y": 999999})

    gui._setup_window()

    tk_root.update_idletasks()
    assert tk_root.winfo_x() == max(0, sw - 600)
    assert tk_root.winfo_y() == max(0, sh - 460)


def test_setup_window_clamps_width_height_to_minimum(gg, tk_root):
    """gui.conf z wymiarami poniżej WIN_W_MIN/WIN_H_MIN (np. ręcznie
    zepsuty plik konfiguracyjny) — realny rozmiar nie może zejść poniżej
    minimum, niezależnie od zapisanej wartości."""
    sw, sh = _screen_size(tk_root)
    gui = _make_gui(gg, tk_root, {"width": 100, "height": 50})

    gui._setup_window()

    tk_root.update_idletasks()
    assert tk_root.winfo_width()  >= 600   # WIN_W_MIN
    assert tk_root.winfo_height() >= 460   # WIN_H_MIN
    assert tk_root.winfo_x() == (sw - tk_root.winfo_width())  // 2
    assert tk_root.winfo_y() == (sh - tk_root.winfo_height()) // 2


def test_setup_window_loads_icon_when_file_exists(gg, monkeypatch, tk_root, tmp_path):
    """Tk sniffuje format z nagłówka, nie z rozszerzenia — wystarczy
    realny obrazek (tu GIF) pod nazwą glava-gui.png, żeby PhotoImage
    realnie się załadował, bez mockowania tk.PhotoImage."""
    icon_dir = tmp_path / "icon"
    icon_dir.mkdir()
    icon_path = icon_dir / "glava-gui.png"
    placeholder = tk.PhotoImage(width=2, height=2)
    placeholder.write(str(icon_path), format="gif")

    monkeypatch.setattr(gg, "_SCRIPT_DIR", str(tmp_path))
    gui = _make_gui(gg, tk_root, {"width": 1040, "height": 768})

    gui._setup_window()

    assert hasattr(tk_root, "_icon")


def test_setup_window_skips_icon_silently_when_file_missing(gg, monkeypatch, tk_root, tmp_path):
    monkeypatch.setattr(gg, "_SCRIPT_DIR", str(tmp_path))  # icon/glava-gui.png nie istnieje
    gui = _make_gui(gg, tk_root, {"width": 1040, "height": 768})

    gui._setup_window()  # nie powinno podnieść wyjątku

    assert not hasattr(tk_root, "_icon")


def test_setup_window_swallows_exception_when_icon_file_corrupt(gg, monkeypatch, tk_root, tmp_path):
    icon_dir = tmp_path / "icon"
    icon_dir.mkdir()
    (icon_dir / "glava-gui.png").write_text("to nie jest obrazek")

    monkeypatch.setattr(gg, "_SCRIPT_DIR", str(tmp_path))
    gui = _make_gui(gg, tk_root, {"width": 1040, "height": 768})

    gui._setup_window()  # TclError z PhotoImage musi być wyciszony

    assert not hasattr(tk_root, "_icon")
