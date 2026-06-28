# =============================================================================
# tests/test_glava_gui_workspace.py
#
# Testy dla _save_workspace / _load_workspace / _save_window_state.
#
# _save_workspace i _load_workspace to modalne dialogi (tk.Toplevel +
# dlg.wait_window() — BLOKUJĄCY event loop). Realne zdarzenia X
# (entry.event_generate) NIE działają w headless Xvfb bez WM (ustalone
# wcześniej w projekcie przy testach SimpleSlider/_slider_row) — więc
# zamiast tego podstawiamy tk.Toplevel.wait_window samo: funkcja-zastępnik
# odnajduje Entry/Listbox dialogu, wypełnia je, i klika OK/Cancel przez
# button.invoke() (woła Python-callback bezpośrednio, bez przechodzenia
# przez serwer X) — w pełni synchronicznie, zero ryzyka zawieszenia testu.
#
# UWAGA — _save_workspace jest sklasyfikowane przez logic-cov jako GUI
# (gui=18, logic=12 — przewaga GUI mimo realnej logiki wewnątrz), więc
# NIE pojawia się w oficjalnym raporcie "Missing Logic" (892-1010 to tylko
# _load_workspace [MIXED] + _save_window_state [MIXED]). Testujemy je tu
# i tak — to realna logika (odczyt kolorów/geometrii/GLSL, zapis JSON na
# dysk), wysokiego ryzyka (utrata workspace usera przy buggu), niezależnie
# od tego że narzędzie jej nie liczy do %.
# =============================================================================

import importlib.util
import json
import os
import sys

import pytest
import tkinter as tk
from tkinter import ttk

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
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


class FakeT(dict):
    pass


class _FakeVar:
    def __init__(self, value):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class _FakeWsInstance:
    """Podmienia gui.instance.GlavaInstance — interfejs zgodny z realną
    klasą (inst_id, glava_dir, rc_glsl, smooth_glsl, module_frag/tmpl)."""
    def __init__(self, inst_id, glava_dir):
        self.inst_id     = inst_id
        self.glava_dir   = glava_dir
        self.rc_glsl     = os.path.join(glava_dir, "rc.glsl")
        self.smooth_glsl = os.path.join(glava_dir, "smooth_parameters.glsl")
        self.xdg_dir     = f"/tmp/xdg-{inst_id}"

    def module_frag(self, module):
        return os.path.join(self.glava_dir, f"{module}_live.frag")

    def module_tmpl(self, module):
        return os.path.join(self.glava_dir, f"{module}_tmpl.frag")

    def exists(self):
        return True

    def create(self, source=None):
        pass

    def destroy(self):
        pass


def _make_gui(gg, tk_root):
    app = gg.GlavaGUI.__new__(gg.GlavaGUI)
    app.root     = tk_root
    app.T        = FakeT()
    app.settings = {}
    return app


def _redirect_home(gg, monkeypatch, home_path):
    """_save_workspace/_load_workspace liczą ws_dir z os.path.expanduser('~')
    w momencie wywołania — przekierowujemy TYLKO '~', inne wywołania
    (np. wewnątrz coverage/pytest) idą do realnego os.path.expanduser."""
    real_expanduser = os.path.expanduser
    monkeypatch.setattr(
        gg.os.path, "expanduser",
        lambda p: str(home_path) if p == "~" else real_expanduser(p))


def _find_widgets(root_widget, types):
    found = []
    for child in root_widget.winfo_children():
        if isinstance(child, types):
            found.append(child)
        found.extend(_find_widgets(child, types))
    return found


def _find_button(dlg, text):
    for btn in _find_widgets(dlg, (tk.Button, ttk.Button)):
        if btn.cget("text") == text:
            return btn
    return None


def _make_fake_wait_window(entry_text=None, listbox_index=None, click="ok"):
    """Podstawia Toplevel.wait_window(self) — self TO dlg (wait_window jest
    metodą Misc, dlg.wait_window() wywołuje ją z self=dlg). Wypełnia
    Entry/Listbox i klika OK/Cancel przez .invoke(), zamiast wchodzić w
    realny blocking event loop czekający na zdarzenia X."""
    def fake(self, window=None):
        if entry_text is not None:
            entries = _find_widgets(self, (tk.Entry, ttk.Entry))
            if entries:
                entries[0].delete(0, "end")
                entries[0].insert(0, entry_text)
        if listbox_index is not None:
            lbs = _find_widgets(self, tk.Listbox)
            if lbs:
                lbs[0].selection_clear(0, "end")
                lbs[0].selection_set(listbox_index)
        if click == "ok":
            btn = _find_button(self, "OK")
        else:
            buttons = _find_widgets(self, (tk.Button, ttk.Button))
            btn = next((b for b in buttons if b.cget("text") != "OK"), None)
        if btn is not None:
            btn.invoke()
    return fake


# =============================================================================
# _save_workspace
# =============================================================================

def test_save_workspace_cancel_does_nothing(gg, tk_root, monkeypatch, tmp_path):
    app = _make_gui(gg, tk_root)
    app.instances = {}
    home = tmp_path / "home"
    _redirect_home(gg, monkeypatch, home)
    monkeypatch.setattr(tk.Toplevel, "wait_window", _make_fake_wait_window(click="cancel"))
    update_calls = []
    app.update_status = lambda: update_calls.append(True)

    app._save_workspace()

    assert update_calls == []
    assert not (home / ".config" / "GlavaMP" / "workspaces").exists()


def test_save_workspace_invalid_name_shows_error_and_returns(
        gg, tk_root, monkeypatch, tmp_path):
    app = _make_gui(gg, tk_root)
    app.instances = {}
    home = tmp_path / "home"
    _redirect_home(gg, monkeypatch, home)
    monkeypatch.setattr(tk.Toplevel, "wait_window",
                         _make_fake_wait_window(entry_text="bad/name", click="ok"))
    error_calls = []
    monkeypatch.setattr(gg.messagebox, "showerror",
                         lambda *a, **kw: error_calls.append(True))
    update_calls = []
    app.update_status = lambda: update_calls.append(True)

    app._save_workspace()

    assert error_calls == [True]
    assert update_calls == []
    assert not (home / ".config" / "GlavaMP" / "workspaces").exists()


def test_save_workspace_happy_path_writes_json_with_colors_geometry_glsl(
        gg, tk_root, monkeypatch, tmp_path):
    app = _make_gui(gg, tk_root)
    app.settings = {"gradient_mode": "hsv"}
    app.active_module = "bars"
    app._inst_modules = {1: "bars"}

    inst_dir = tmp_path / "inst1"
    inst_dir.mkdir()
    (inst_dir / "bars.glsl").write_text("")
    (inst_dir / "rc.glsl").write_text("")
    (inst_dir / "smooth_parameters.glsl").write_text("")
    inst = _FakeWsInstance(1, str(inst_dir))
    app.instances = {1: inst}

    class _FakeInstBar:
        _tabs = {1: {"label": "Bars \u2726"}}
    app.inst_bar = _FakeInstBar()

    home = tmp_path / "home"
    _redirect_home(gg, monkeypatch, home)

    import gui.colors as colors_mod
    import gui.geometry as geometry_mod
    import gui.instance as instance_mod
    import gui.modules.glsl_io as glsl_io_mod
    # _save_workspace robi LOKALNY `from gui.instance import GlavaInstance`
    # i tworzy ŚWIEŻY GlavaInstance(iid) wewnątrz pętli — self.instances[iid]
    # służy TYLKO do wydobycia listy inst_id (.keys()), nie jest faktycznie
    # użyte jako `inst`. Trzeba patchować na źródle, inaczej realny
    # GlavaInstance dostanie wywołane metody i poleci na nieistniejących
    # ścieżkach.
    monkeypatch.setattr(instance_mod, "GlavaInstance", lambda iid: inst)
    monkeypatch.setattr(colors_mod, "read_colors_from_frag",
                         lambda path: {"top": "#111111"})
    monkeypatch.setattr(geometry_mod, "read_geometry", lambda path: (1, 2, 3, 4))
    monkeypatch.setattr(glsl_io_mod, "read_all_defines",
                         lambda path: {"BAR_WIDTH": 5} if "bars" in path else {"X": 1})
    monkeypatch.setattr(glsl_io_mod, "read_smooth",
                         lambda path, params: {"setfps": 60})

    monkeypatch.setattr(tk.Toplevel, "wait_window",
                         _make_fake_wait_window(entry_text="MyWorkspace", click="ok"))
    update_calls = []
    app.update_status = lambda: update_calls.append(True)

    app._save_workspace()

    ws_path = home / ".config" / "GlavaMP" / "workspaces" / "MyWorkspace.json"
    assert ws_path.exists()
    with open(ws_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["name"] == "MyWorkspace"
    assert data["gradient_mode"] == "hsv"
    assert len(data["instances"]) == 1
    entry = data["instances"][0]
    assert entry["inst_id"] == 1
    assert entry["name"] == "Bars \u2726"
    assert entry["module"] == "bars"
    assert entry["colors"] == {"top": "#111111"}
    assert entry["geometry"] == {"x": 1, "y": 2, "w": 3, "h": 4}
    assert entry["glsl"]["bars.glsl"] == {"BAR_WIDTH": 5}
    assert entry["glsl"]["rc.glsl"] == {"X": 1}
    assert entry["glsl"]["smooth_parameters.glsl"] == {"setfps": 60}
    assert update_calls == [True]


def test_save_workspace_oserror_on_write_shows_error_and_skips_update_status(
        gg, tk_root, monkeypatch, tmp_path):
    app = _make_gui(gg, tk_root)
    app.instances = {}
    home = tmp_path / "home"
    _redirect_home(gg, monkeypatch, home)
    monkeypatch.setattr(tk.Toplevel, "wait_window",
                         _make_fake_wait_window(entry_text="WS1", click="ok"))

    import json as json_mod
    monkeypatch.setattr(json_mod, "dump",
                         lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full")))
    error_calls = []
    monkeypatch.setattr(gg.messagebox, "showerror",
                         lambda *a, **kw: error_calls.append(True))
    update_calls = []
    app.update_status = lambda: update_calls.append(True)

    app._save_workspace()

    assert error_calls == [True]
    assert update_calls == []


# =============================================================================
# _load_workspace — wczesne wyjścia
# =============================================================================

def test_load_workspace_no_saved_files_shows_info_and_returns(
        gg, tk_root, monkeypatch, tmp_path):
    app = _make_gui(gg, tk_root)
    home = tmp_path / "home"
    _redirect_home(gg, monkeypatch, home)
    info_calls = []
    monkeypatch.setattr(gg.messagebox, "showinfo",
                         lambda *a, **kw: info_calls.append(True))

    app._load_workspace()  # ws_dir nie istnieje -> os.listdir po makedirs -> []

    assert info_calls == [True]


def test_load_workspace_cancel_does_nothing(gg, tk_root, monkeypatch, tmp_path):
    app = _make_gui(gg, tk_root)
    home = tmp_path / "home"
    ws_dir = home / ".config" / "GlavaMP" / "workspaces"
    ws_dir.mkdir(parents=True)
    (ws_dir / "WS1.json").write_text(json.dumps({"instances": []}))
    _redirect_home(gg, monkeypatch, home)
    monkeypatch.setattr(tk.Toplevel, "wait_window", _make_fake_wait_window(click="cancel"))

    close_calls = []
    app._on_inst_close = lambda iid: close_calls.append(iid)

    app._load_workspace()

    assert close_calls == []


# =============================================================================
# _load_workspace — pętla per-instancja (helper współdzielony między testami)
# =============================================================================

def _setup_load_env(gg, tk_root, monkeypatch, tmp_path, ws_instances,
                     gradient_mode="rgb", precreate_glsl_files=None):
    """Wspólny szkielet środowiska dla testów pętli per-instancja w
    _load_workspace. Zwraca (app, tracking) — tracking zbiera wywołania
    wszystkich zamockowanych metod/funkcji do asercji."""
    app = _make_gui(gg, tk_root)

    home = tmp_path / "home"
    ws_dir = home / ".config" / "GlavaMP" / "workspaces"
    ws_dir.mkdir(parents=True)
    ws_data = {"gradient_mode": gradient_mode, "instances": ws_instances}
    (ws_dir / "WS1.json").write_text(json.dumps(ws_data))
    _redirect_home(gg, monkeypatch, home)
    monkeypatch.setattr(tk.Toplevel, "wait_window",
                         _make_fake_wait_window(listbox_index=0, click="ok"))

    import gui.core as core_mod
    monkeypatch.setattr(core_mod, "save_settings", lambda s: None)
    monkeypatch.setattr(core_mod, "GLAVA_DISABLE_FLAG", str(tmp_path / "no_disable_flag"))

    app.instances = {}
    app._on_inst_close = lambda iid: None

    tracking = {
        "add_calls": [], "instances_created": {}, "rebuild_calls": [],
        "restart_calls": [], "update_calls": [], "info_calls": [],
    }

    def fake_add(module, start=False, label=None):
        new_id = len(tracking["add_calls"])
        tracking["add_calls"].append((module, label))
        inst_dir = tmp_path / f"inst{new_id}"
        inst_dir.mkdir(exist_ok=True)
        for fname in (precreate_glsl_files or []):
            (inst_dir / fname).write_text("")
        inst = _FakeWsInstance(new_id, str(inst_dir))
        tracking["instances_created"][new_id] = inst
        return new_id
    app._on_inst_add = fake_add

    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "GlavaInstance",
                         lambda iid: tracking["instances_created"][iid])

    app.rebuild_module_tab = lambda: tracking["rebuild_calls"].append(True)
    app.restart_active_instance = (
        lambda module=None, after_fn=None: tracking["restart_calls"].append(module))

    class _FakeInstBar:
        def __init__(self):
            self.set_label_calls = []
        def set_label(self, iid, name):
            self.set_label_calls.append((iid, name))
    app.inst_bar = _FakeInstBar()
    tracking["inst_bar"] = app.inst_bar

    app.update_status = lambda: tracking["update_calls"].append(True)
    monkeypatch.setattr(gg.messagebox, "showinfo",
                         lambda *a, **kw: tracking["info_calls"].append(True))

    return app, tracking


def test_load_workspace_minimal_instance_creates_and_restarts(
        gg, tk_root, monkeypatch, tmp_path):
    app, t = _setup_load_env(gg, tk_root, monkeypatch, tmp_path,
                              ws_instances=[{"module": "bars"}])

    app._load_workspace()

    assert t["add_calls"] == [("bars", None)]
    assert app._active_inst_id == 0
    assert app.active_instance is t["instances_created"][0]
    assert t["rebuild_calls"] == [True]
    assert t["restart_calls"] == ["bars"]
    assert t["update_calls"] == [True]
    assert t["info_calls"] == [True]
    assert t["inst_bar"].set_label_calls == []  # brak "name" w danych


def test_load_workspace_defaults_missing_module_key_to_bars(
        gg, tk_root, monkeypatch, tmp_path):
    app, t = _setup_load_env(gg, tk_root, monkeypatch, tmp_path,
                              ws_instances=[{}])  # brak "module" całkowicie

    app._load_workspace()

    assert t["add_calls"] == [("bars", None)]


def test_load_workspace_sets_label_when_name_present(gg, tk_root, monkeypatch, tmp_path):
    app, t = _setup_load_env(
        gg, tk_root, monkeypatch, tmp_path,
        ws_instances=[{"module": "wave", "name": "My Wave"}])

    app._load_workspace()

    assert t["inst_bar"].set_label_calls == [(0, "My Wave")]


def test_load_workspace_applies_gradient_mode_to_settings(gg, tk_root, monkeypatch, tmp_path):
    app, t = _setup_load_env(gg, tk_root, monkeypatch, tmp_path,
                              ws_instances=[], gradient_mode="hsv")

    app._load_workspace()

    assert app.settings["gradient_mode"] == "hsv"


def test_load_workspace_closes_all_existing_instances_before_loading(
        gg, tk_root, monkeypatch, tmp_path):
    app, t = _setup_load_env(gg, tk_root, monkeypatch, tmp_path, ws_instances=[])
    app.instances = {10: object(), 20: object()}
    close_calls = []
    app._on_inst_close = lambda iid: close_calls.append(iid)

    app._load_workspace()

    assert sorted(close_calls) == [10, 20]


def test_load_workspace_resets_restart_tracking_dicts(gg, tk_root, monkeypatch, tmp_path):
    app, t = _setup_load_env(gg, tk_root, monkeypatch, tmp_path, ws_instances=[])
    app._restart_in_progress = {1: True}
    app._restart_pending = {1: "x"}
    app._restart_after = {1: "y"}

    app._load_workspace()

    assert app._restart_in_progress == {}
    assert app._restart_pending == {}
    assert app._restart_after == {}


def test_load_workspace_removes_disable_flag_and_enables_glava_var(
        gg, tk_root, monkeypatch, tmp_path):
    app, t = _setup_load_env(gg, tk_root, monkeypatch, tmp_path, ws_instances=[])
    flag_path = tmp_path / "disabled"
    flag_path.write_text("")
    import gui.core as core_mod
    monkeypatch.setattr(core_mod, "GLAVA_DISABLE_FLAG", str(flag_path))
    app.glava_enabled_var = _FakeVar(False)

    app._load_workspace()

    assert not flag_path.exists()
    assert app.glava_enabled_var.get() is True


def test_load_workspace_swallows_filenotfound_race_on_disable_flag_removal(
        gg, tk_root, monkeypatch, tmp_path):
    """os.path.exists(GLAVA_DISABLE_FLAG) widzi plik, ale ktoś go usuwa
    (np. inny proces) zanim dojdzie do os.remove() -> FileNotFoundError ->
    except: pass. Wciąż musi ustawić glava_enabled_var na True."""
    app, t = _setup_load_env(gg, tk_root, monkeypatch, tmp_path, ws_instances=[])
    flag_path = tmp_path / "disabled_race"
    flag_path.write_text("")  # istnieje -> przejdzie guard os.path.exists
    import gui.core as core_mod
    monkeypatch.setattr(core_mod, "GLAVA_DISABLE_FLAG", str(flag_path))

    real_remove = os.remove

    def fake_remove(p):
        if p == str(flag_path):
            raise FileNotFoundError("zniknął tuż przed")
        return real_remove(p)

    monkeypatch.setattr(gg.os, "remove", fake_remove)
    app.glava_enabled_var = _FakeVar(False)

    app._load_workspace()  # nie powinno podnieść wyjątku

    assert app.glava_enabled_var.get() is True


def test_load_workspace_skips_glsl_file_that_does_not_exist_on_disk(
        gg, tk_root, monkeypatch, tmp_path):
    import gui.modules.glsl_io as glsl_io_mod
    define_calls = []
    monkeypatch.setattr(glsl_io_mod, "write_define_raw",
                         lambda path, key, val: define_calls.append((key, val)))

    app, t = _setup_load_env(
        gg, tk_root, monkeypatch, tmp_path,
        ws_instances=[{"module": "bars", "glsl": {"bars.glsl": {"BAR_WIDTH": 5}}}],
        precreate_glsl_files=[])  # plik NIE istnieje na dysku -> continue

    app._load_workspace()

    assert define_calls == []


def test_load_workspace_writes_define_raw_for_existing_glsl_file(
        gg, tk_root, monkeypatch, tmp_path):
    import gui.modules.glsl_io as glsl_io_mod
    define_calls = []
    monkeypatch.setattr(glsl_io_mod, "write_define_raw",
                         lambda path, key, val: define_calls.append((key, val)))

    app, t = _setup_load_env(
        gg, tk_root, monkeypatch, tmp_path,
        ws_instances=[{"module": "bars",
                       "glsl": {"bars.glsl": {"BAR_WIDTH": 5, "BAR_GAP": 2}}}],
        precreate_glsl_files=["bars.glsl"])

    app._load_workspace()

    assert sorted(define_calls) == sorted([("BAR_WIDTH", 5), ("BAR_GAP", 2)])


def test_load_workspace_routes_smooth_parameters_to_write_smooth(
        gg, tk_root, monkeypatch, tmp_path):
    import gui.core as core_mod
    import gui.modules.glsl_io as glsl_io_mod
    monkeypatch.setattr(core_mod, "SMOOTH_PARAMS", ["fake_param"], raising=False)
    smooth_calls = []
    monkeypatch.setattr(
        glsl_io_mod, "write_smooth",
        lambda path, defines, params: smooth_calls.append((defines, params)))
    define_calls = []
    monkeypatch.setattr(glsl_io_mod, "write_define_raw",
                         lambda path, key, val: define_calls.append((key, val)))

    app, t = _setup_load_env(
        gg, tk_root, monkeypatch, tmp_path,
        ws_instances=[{"module": "bars",
                       "glsl": {"smooth_parameters.glsl": {"setfps": 60}}}],
        precreate_glsl_files=["smooth_parameters.glsl"])

    app._load_workspace()

    assert smooth_calls == [({"setfps": 60}, ["fake_param"])]
    assert define_calls == []  # smooth_parameters.glsl idzie INNĄ ścieżką


def test_load_workspace_writes_geometry_when_present(gg, tk_root, monkeypatch, tmp_path):
    import gui.geometry as geometry_mod
    geo_calls = []
    monkeypatch.setattr(geometry_mod, "write_geometry",
                         lambda rc_path, x, y, w, h: geo_calls.append((x, y, w, h)))

    app, t = _setup_load_env(
        gg, tk_root, monkeypatch, tmp_path,
        ws_instances=[{"module": "bars",
                       "geometry": {"x": 10, "y": 20, "w": 800, "h": 600}}])

    app._load_workspace()

    assert geo_calls == [(10, 20, 800, 600)]


def test_load_workspace_skips_geometry_when_absent(gg, tk_root, monkeypatch, tmp_path):
    import gui.geometry as geometry_mod
    geo_calls = []
    monkeypatch.setattr(geometry_mod, "write_geometry",
                         lambda *a: geo_calls.append(a))

    app, t = _setup_load_env(gg, tk_root, monkeypatch, tmp_path,
                              ws_instances=[{"module": "bars"}])

    app._load_workspace()

    assert geo_calls == []


def test_load_workspace_writes_colors_when_present(gg, tk_root, monkeypatch, tmp_path):
    import gui.colors as colors_mod
    color_calls = []
    monkeypatch.setattr(
        colors_mod, "write_colors_to_frag",
        lambda module, colors, gradient, live_path=None, tmpl_path=None:
            color_calls.append((module, colors, gradient)))

    app, t = _setup_load_env(
        gg, tk_root, monkeypatch, tmp_path,
        ws_instances=[{"module": "wave", "colors": {"top": "#abcabc"}}],
        gradient_mode="hsv")

    app._load_workspace()

    assert color_calls == [("wave", {"top": "#abcabc"}, "hsv")]


def test_load_workspace_skips_colors_when_absent(gg, tk_root, monkeypatch, tmp_path):
    import gui.colors as colors_mod
    color_calls = []
    monkeypatch.setattr(colors_mod, "write_colors_to_frag",
                         lambda *a, **kw: color_calls.append(True))

    app, t = _setup_load_env(gg, tk_root, monkeypatch, tmp_path,
                              ws_instances=[{"module": "bars"}])

    app._load_workspace()

    assert color_calls == []


# =============================================================================
# _save_window_state
# =============================================================================

class _FakeGeoRoot:
    def __init__(self, geometry_str):
        self._geo = geometry_str

    def geometry(self):
        return self._geo


def test_save_window_state_parses_geometry_and_saves(gg, monkeypatch):
    app = gg.GlavaGUI.__new__(gg.GlavaGUI)
    app.root = _FakeGeoRoot("1040x768+100+50")
    app.gui_conf = {"theme": "forest-dark"}
    save_calls = []
    monkeypatch.setattr(gg, "save_gui_conf", lambda conf: save_calls.append(dict(conf)))

    app._save_window_state()

    assert app.gui_conf["width"]  == 1040
    assert app.gui_conf["height"] == 768
    assert app.gui_conf["x"] == 100
    assert app.gui_conf["y"] == 50
    assert save_calls == [app.gui_conf]


def test_save_window_state_handles_negative_offsets(gg, monkeypatch):
    app = gg.GlavaGUI.__new__(gg.GlavaGUI)
    app.root = _FakeGeoRoot("800x600+-20+-30")
    app.gui_conf = {}
    save_calls = []
    monkeypatch.setattr(gg, "save_gui_conf", lambda conf: save_calls.append(conf))

    app._save_window_state()

    assert app.gui_conf["x"] == -20
    assert app.gui_conf["y"] == -30


def test_save_window_state_no_regex_match_does_not_save(gg, monkeypatch):
    app = gg.GlavaGUI.__new__(gg.GlavaGUI)
    app.root = _FakeGeoRoot("totally-not-a-geometry-string")
    app.gui_conf = {"width": 1}
    save_calls = []
    monkeypatch.setattr(gg, "save_gui_conf", lambda conf: save_calls.append(conf))

    app._save_window_state()

    assert save_calls == []
    assert app.gui_conf == {"width": 1}  # niezmienione


def test_save_window_state_swallows_exception_from_root_geometry(gg):
    class _BrokenRoot:
        def geometry(self):
            raise tk.TclError("window destroyed")
    app = gg.GlavaGUI.__new__(gg.GlavaGUI)
    app.root = _BrokenRoot()
    app.gui_conf = {}

    app._save_window_state()  # nie powinno podnieść wyjątku
