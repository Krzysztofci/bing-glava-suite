import os
import sys
import json
import pytest
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import gui.tab_main as tab_main_mod
import gui.core as core_mod
import gui.geometry as geometry_mod


# ── Fakes ─────────────────────────────────────────────────────────────────────

class FakeT(dict):
    pass


class FakeInstance:
    """Minimalna instancja: module_frag/module_tmpl per-instance paths."""
    def __init__(self, base_dir, name="inst"):
        self.base_dir = base_dir
        self.name = name

    def module_frag(self, module):
        return os.path.join(self.base_dir, f"{self.name}_{module}_live.frag")

    def module_tmpl(self, module):
        return os.path.join(self.base_dir, f"{self.name}_{module}_tmpl.frag")


class FakeColorButton:
    """Stub zamiast realnego ColorButton (który ładuje PNG z dysku przez PIL).
    Śledzi tylko ostatni ustawiony kolor."""
    def __init__(self, parent, key, text, color, command, root):
        self.key = key
        self.color = color
        self.command = command
        self.widget = None  # nie tworzymy realnego ttk.Button

    def set_color(self, color):
        self.color = color


class FakeApp:
    def __init__(self, tmp_path, with_multi_instance=False):
        self.T = FakeT()
        self.root = None
        self.settings = {"gradient_mode": "rgb"}
        self.active_module = "bars"
        self.active_instance = FakeInstance(str(tmp_path), "inst0")
        self._active_inst_id = 0
        self._tab_main_ref = None
        self.update_status_calls = 0
        self.rebuild_calls = 0
        # _inst_modules jest odczytywane bezwarunkowo w _change_gradient
        # (self.app._inst_modules.get(iid, ...)) nawet w trybie
        # single-instance — nie jest schowane za hasattr() jak 'instances'.
        self._inst_modules = {0: "bars"}

        if with_multi_instance:
            self.instances = {0: self.active_instance}
            self.processes = {0: None}

    def update_status(self):
        self.update_status_calls += 1

    def rebuild_module_tab(self):
        self.rebuild_calls += 1


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_color_button(monkeypatch):
    monkeypatch.setattr(tab_main_mod, "ColorButton", FakeColorButton)


@pytest.fixture(autouse=True)
def isolated_flags(tmp_path, monkeypatch):
    """Izoluje FLAG_RED/FLAG_MANUAL używane przez write_colors_to_frag,
    żeby testy nie dotykały ~/.config/glava na maszynie dewelopera."""
    flag_red = tmp_path / "red.shift"
    flag_manual = tmp_path / "manual.shift"
    monkeypatch.setattr(core_mod, "FLAG_RED", str(flag_red))
    monkeypatch.setattr(core_mod, "FLAG_MANUAL", str(flag_manual))
    # colors.py importuje FLAG_RED/FLAG_MANUAL z core jako wartości (from .core
    # import FLAG_RED, FLAG_MANUAL) — trzeba patchować też w module colors.
    import gui.colors as colors_mod
    monkeypatch.setattr(colors_mod, "FLAG_RED", str(flag_red))
    monkeypatch.setattr(colors_mod, "FLAG_MANUAL", str(flag_manual))
    # tab_main.py też importuje FLAG_RED/FLAG_MANUAL na poziomie modułu
    # (używane w _restore_auto do czyszczenia flag po sync z tapetą).
    monkeypatch.setattr(tab_main_mod, "FLAG_RED", str(flag_red), raising=False)
    monkeypatch.setattr(tab_main_mod, "FLAG_MANUAL", str(flag_manual), raising=False)
    return str(flag_red), str(flag_manual)


@pytest.fixture
def fake_app(tmp_path):
    return FakeApp(tmp_path)


def _make_tab(fake_app, monkeypatch):
    """Tworzy TabMain bez wołania build() (unikamy realnego tkinter
    layoutu) — __init__ samo woła _load_colors_from_live(), które
    wymaga get_live_frag/_inst, ale działa bez tkinter."""
    monkeypatch.setattr(tab_main_mod, "read_bing_config", lambda: {"BING_REGION": "de-DE"})
    monkeypatch.setattr(tab_main_mod, "load_color_presets", lambda: {})
    return tab_main_mod.TabMain(parent=None, app=fake_app)


# ── _inst / _live_frag / _tmpl_frag — multi-instance vs legacy ─────────────

def test_inst_returns_active_instance(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    assert tab._inst() is fake_app.active_instance


def test_live_frag_uses_instance_path_when_instance_present(
        fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    result = tab._live_frag("wave")
    assert result == fake_app.active_instance.module_frag("wave")


def test_live_frag_defaults_to_active_module_when_module_none(
        fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    result = tab._live_frag()
    assert result == fake_app.active_instance.module_frag("bars")


def test_live_frag_falls_back_to_global_get_live_frag_when_no_instance(
        fake_app, monkeypatch):
    fake_app.active_instance = None
    tab = _make_tab(fake_app, monkeypatch)
    monkeypatch.setattr(tab_main_mod, "get_live_frag", lambda m: f"GLOBAL_{m}")
    result = tab._live_frag("circle")
    assert result == "GLOBAL_circle"


def test_tmpl_frag_uses_instance_path_when_instance_present(
        fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    result = tab._tmpl_frag("wave")
    assert result == fake_app.active_instance.module_tmpl("wave")


def test_tmpl_frag_falls_back_to_global_get_template_when_no_instance(
        fake_app, monkeypatch):
    fake_app.active_instance = None
    tab = _make_tab(fake_app, monkeypatch)
    monkeypatch.setattr(tab_main_mod, "get_template", lambda m: f"GLOBAL_TMPL_{m}")
    result = tab._tmpl_frag("circle")
    assert result == "GLOBAL_TMPL_circle"


# ── _load_colors_from_live ──────────────────────────────────────────────────

def test_load_colors_from_live_uses_frag_colors_when_no_last_session(
        fake_app, monkeypatch):
    monkeypatch.setattr(tab_main_mod, "read_bing_config", lambda: {})
    monkeypatch.setattr(tab_main_mod, "load_color_presets", lambda: {})
    monkeypatch.setattr(tab_main_mod, "read_colors_from_frag",
                         lambda path: {"top": "#111111", "mid": "#222222", "bottom": "#333333"})
    tab = tab_main_mod.TabMain(parent=None, app=fake_app)
    assert tab.current_colors == {"top": "#111111", "mid": "#222222", "bottom": "#333333"}


def test_load_colors_from_live_prefers_last_session_over_frag(
        fake_app, monkeypatch):
    monkeypatch.setattr(tab_main_mod, "read_bing_config", lambda: {})
    monkeypatch.setattr(
        tab_main_mod, "load_color_presets",
        lambda: {"LAST_SESSION": {"top": "#aaaaaa", "mid": "#bbbbbb", "bottom": "#cccccc"}})
    monkeypatch.setattr(tab_main_mod, "read_colors_from_frag",
                         lambda path: {"top": "#111111", "mid": "#222222", "bottom": "#333333"})
    tab = tab_main_mod.TabMain(parent=None, app=fake_app)
    assert tab.current_colors == {"top": "#aaaaaa", "mid": "#bbbbbb", "bottom": "#cccccc"}


def test_load_colors_from_live_keeps_default_when_frag_returns_none(
        fake_app, monkeypatch):
    monkeypatch.setattr(tab_main_mod, "read_bing_config", lambda: {})
    monkeypatch.setattr(tab_main_mod, "load_color_presets", lambda: {})
    monkeypatch.setattr(tab_main_mod, "read_colors_from_frag", lambda path: None)
    tab = tab_main_mod.TabMain(parent=None, app=fake_app)
    assert tab.current_colors == {"top": "#ffffff", "mid": "#888888", "bottom": "#000000"}


# ── _contrast_fg — pure math, no mocks needed ───────────────────────────────

@pytest.mark.parametrize("hex_color,expected", [
    ("#ffffff", "#000000"),   # białe tło -> czarny tekst
    ("#000000", "#ffffff"),   # czarne tło -> biały tekst
    ("#e53935", "#ffffff"),   # czerwony (ciemny) -> biały tekst
])
def test_contrast_fg_returns_correct_text_color(fake_app, monkeypatch, hex_color, expected):
    tab = _make_tab(fake_app, monkeypatch)
    assert tab._contrast_fg(hex_color) == expected


def test_contrast_fg_invalid_hex_falls_back_to_white(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    assert tab._contrast_fg("not-a-color") == "#ffffff"


# ── _pick_color / _update_color_btn ─────────────────────────────────────────

def test_update_color_btn_sets_color_on_known_key(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.color_btns = {"top": FakeColorButton(None, "top", "Top", "#ffffff", None, None)}
    tab._update_color_btn("top", "#123456")
    assert tab.color_btns["top"].color == "#123456"


def test_update_color_btn_ignores_unknown_key(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.color_btns = {}
    tab._update_color_btn("nonexistent", "#123456")  # nie powinno crashować


def test_pick_color_updates_current_colors_and_saves_session(
        fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.color_btns = {"top": FakeColorButton(None, "top", "Top", "#ffffff", None, None)}
    monkeypatch.setattr(tab_main_mod.colorchooser, "askcolor",
                         lambda color, title: ((255, 0, 0), "#ff0000"))
    saved = []
    monkeypatch.setattr(tab, "_save_last_session", lambda: saved.append(True))

    tab._pick_color("top")

    assert tab.current_colors["top"] == "#ff0000"
    assert tab.color_btns["top"].color == "#ff0000"
    assert saved == [True]


def test_pick_color_cancelled_dialog_does_not_change_colors(
        fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.color_btns = {"top": FakeColorButton(None, "top", "Top", "#ffffff", None, None)}
    monkeypatch.setattr(tab_main_mod.colorchooser, "askcolor",
                         lambda color, title: (None, None))
    saved = []
    monkeypatch.setattr(tab, "_save_last_session", lambda: saved.append(True))

    original = dict(tab.current_colors)
    tab._pick_color("top")

    assert tab.current_colors == original
    assert saved == []


# ── _save_last_session ───────────────────────────────────────────────────────

def test_save_last_session_persists_current_colors(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.current_colors = {"top": "#aaaaaa", "mid": "#bbbbbb", "bottom": "#cccccc"}
    saved_presets = []
    monkeypatch.setattr(tab_main_mod, "save_color_presets",
                         lambda presets: saved_presets.append(presets))
    tab._save_last_session()
    assert saved_presets[-1]["LAST_SESSION"] == {"top": "#aaaaaa", "mid": "#bbbbbb", "bottom": "#cccccc"}


# ── _load_preset / _save_preset / _delete_preset / _refresh_preset_cb ──────

class FakeStringVar:
    def __init__(self, value=""):
        self._value = value
    def get(self):
        return self._value
    def set(self, v):
        self._value = v


class FakeCombobox:
    def __init__(self):
        self._values = []
        self._current_idx = None
    def __setitem__(self, key, value):
        if key == "values":
            self._values = value
    def __getitem__(self, key):
        if key == "values":
            return self._values
        raise KeyError(key)
    def current(self, idx):
        self._current_idx = idx


def test_load_preset_applies_existing_preset(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.presets = {"MyPreset": {"top": "#111111", "mid": "#222222", "bottom": "#333333"}}
    tab.preset_var = FakeStringVar("MyPreset")
    tab.color_btns = {k: FakeColorButton(None, k, k, "#000000", None, None)
                       for k in ("top", "mid", "bottom")}
    applied = []
    monkeypatch.setattr(tab, "_apply_colors", lambda: applied.append(True))

    tab._load_preset()

    assert tab.current_colors == {"top": "#111111", "mid": "#222222", "bottom": "#333333"}
    assert applied == [True]
    assert tab.color_btns["top"].color == "#111111"


def test_load_preset_does_nothing_if_name_empty(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.preset_var = FakeStringVar("")
    applied = []
    monkeypatch.setattr(tab, "_apply_colors", lambda: applied.append(True))
    original = dict(tab.current_colors)
    tab._load_preset()
    assert tab.current_colors == original
    assert applied == []


def test_load_preset_does_nothing_if_name_not_in_presets(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.presets = {"Other": {}}
    tab.preset_var = FakeStringVar("Nonexistent")
    applied = []
    monkeypatch.setattr(tab, "_apply_colors", lambda: applied.append(True))
    tab._load_preset()
    assert applied == []


def test_save_preset_saves_when_name_given(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.current_colors = {"top": "#111111", "mid": "#222222", "bottom": "#333333"}
    monkeypatch.setattr(tab_main_mod, "ask_string",
                         lambda parent, T, title, prompt: "NewPreset")
    saved = []
    monkeypatch.setattr(tab_main_mod, "save_color_presets",
                         lambda presets: saved.append(dict(presets)))
    refreshed = []
    monkeypatch.setattr(tab, "_refresh_preset_cb", lambda: refreshed.append(True))

    tab._save_preset()

    assert tab.presets["NewPreset"] == {"top": "#111111", "mid": "#222222", "bottom": "#333333"}
    assert saved[-1]["NewPreset"] == {"top": "#111111", "mid": "#222222", "bottom": "#333333"}
    assert refreshed == [True]


def test_save_preset_cancelled_dialog_does_not_save(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    monkeypatch.setattr(tab_main_mod, "ask_string",
                         lambda parent, T, title, prompt: None)
    saved = []
    monkeypatch.setattr(tab_main_mod, "save_color_presets",
                         lambda presets: saved.append(True))
    tab._save_preset()
    assert saved == []


def test_delete_preset_removes_when_confirmed(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.presets = {"ToDelete": {"top": "#000000"}}
    tab.preset_var = FakeStringVar("ToDelete")
    monkeypatch.setattr(tab_main_mod.messagebox, "askyesno", lambda *a, **kw: True)
    saved = []
    monkeypatch.setattr(tab_main_mod, "save_color_presets",
                         lambda presets: saved.append(dict(presets)))
    refreshed = []
    monkeypatch.setattr(tab, "_refresh_preset_cb", lambda: refreshed.append(True))

    tab._delete_preset()

    assert "ToDelete" not in tab.presets
    assert "ToDelete" not in saved[-1]
    assert refreshed == [True]


def test_delete_preset_declined_confirm_keeps_preset(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.presets = {"KeepMe": {"top": "#000000"}}
    tab.preset_var = FakeStringVar("KeepMe")
    monkeypatch.setattr(tab_main_mod.messagebox, "askyesno", lambda *a, **kw: False)
    saved = []
    monkeypatch.setattr(tab_main_mod, "save_color_presets",
                         lambda presets: saved.append(True))
    tab._delete_preset()
    assert "KeepMe" in tab.presets
    assert saved == []


def test_delete_preset_empty_name_is_noop(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.preset_var = FakeStringVar("")
    askyesno_calls = []
    monkeypatch.setattr(tab_main_mod.messagebox, "askyesno",
                         lambda *a, **kw: askyesno_calls.append(True) or True)
    tab._delete_preset()
    assert askyesno_calls == []


def test_refresh_preset_cb_excludes_last_session_and_sorts(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.presets = {"Zebra": {}, "LAST_SESSION": {}, "Apple": {}}
    tab.preset_cb = FakeCombobox()
    tab._refresh_preset_cb()
    assert tab.preset_cb["values"] == ["Apple", "Zebra"]
    assert tab.preset_cb._current_idx == 0


def test_refresh_preset_cb_empty_does_not_set_current(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.presets = {"LAST_SESSION": {}}
    tab.preset_cb = FakeCombobox()
    tab._refresh_preset_cb()
    assert tab.preset_cb["values"] == []
    assert tab.preset_cb._current_idx is None


# ── _apply_colors — single instance vs all instances ────────────────────────

def test_apply_colors_single_instance_writes_and_restarts_legacy(
        fake_app, monkeypatch, tmp_path):
    tab = _make_tab(fake_app, monkeypatch)
    tab.current_colors = {"top": "#111111", "mid": "#222222", "bottom": "#333333"}

    write_calls = []
    monkeypatch.setattr(tab_main_mod, "write_colors_to_frag",
                         lambda module, colors, mode, tmpl_path, live_path:
                         (write_calls.append((module, colors, mode)), (True, ""))[1])

    saved = []
    monkeypatch.setattr(tab, "_save_last_session", lambda: saved.append(True))

    restart_calls = []
    monkeypatch.setattr(tab_main_mod, "glava_restart",
                         lambda module, after_fn=None: restart_calls.append(module))

    assert not hasattr(fake_app, "restart_active_instance")
    tab._apply_colors()

    assert write_calls == [("bars", tab.current_colors, "rgb")]
    assert saved == [True]
    assert restart_calls == ["bars"]


def test_apply_colors_single_instance_shows_error_on_failure(
        fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    monkeypatch.setattr(tab_main_mod, "write_colors_to_frag",
                         lambda *a, **kw: (False, "Brak szablonu"))
    errors = []
    monkeypatch.setattr(tab_main_mod.messagebox, "showerror",
                         lambda title, msg: errors.append(msg))
    saved = []
    monkeypatch.setattr(tab, "_save_last_session", lambda: saved.append(True))

    tab._apply_colors()

    assert errors == ["Brak szablonu"]
    assert saved == []  # nie zapisujemy sesji gdy zapis się nie powiódł


def test_apply_colors_uses_restart_active_instance_when_available(
        fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    monkeypatch.setattr(tab_main_mod, "write_colors_to_frag",
                         lambda *a, **kw: (True, ""))
    monkeypatch.setattr(tab, "_save_last_session", lambda: None)

    restart_calls = []
    fake_app.restart_active_instance = lambda after_fn=None: restart_calls.append(True)
    legacy_calls = []
    monkeypatch.setattr(tab_main_mod, "glava_restart",
                         lambda module, after_fn=None: legacy_calls.append(module))

    tab._apply_colors()

    assert restart_calls == [True]
    assert legacy_calls == []


def test_apply_colors_all_instances_writes_each_and_restarts_each(
        fake_app, monkeypatch, tmp_path):
    fake_app.instances = {0: fake_app.active_instance, 1: FakeInstance(str(tmp_path), "inst1")}
    fake_app._inst_modules = {0: "bars", 1: "wave"}
    fake_app.processes = {0: None, 1: None}
    tab = _make_tab(fake_app, monkeypatch)
    tab.all_inst_var = FakeStringVar()
    tab.all_inst_var.get = lambda: True

    import gui.glava as glava_mod
    monkeypatch.setattr(glava_mod, "adopt_instance", lambda iid: (None, None), raising=False)
    write_calls = []
    monkeypatch.setattr(tab_main_mod, "write_colors_to_frag",
                         lambda module, colors, mode, tmpl_path, live_path:
                         (write_calls.append(module), (True, ""))[1])
    restart_calls = []
    monkeypatch.setattr(tab_main_mod, "glava_restart_instance",
                         lambda instance, module, proc, after_fn: restart_calls.append(module))
    monkeypatch.setattr(tab, "_save_last_session", lambda: None)

    tab._apply_colors()

    assert sorted(write_calls) == ["bars", "wave"]
    assert sorted(restart_calls) == ["bars", "wave"]


def test_apply_colors_all_instances_shows_error_if_any_instance_fails(
        fake_app, monkeypatch, tmp_path):
    fake_app.instances = {0: fake_app.active_instance, 1: FakeInstance(str(tmp_path), "inst1")}
    fake_app._inst_modules = {0: "bars", 1: "wave"}
    fake_app.processes = {0: None, 1: None}
    tab = _make_tab(fake_app, monkeypatch)
    tab.all_inst_var = FakeStringVar()
    tab.all_inst_var.get = lambda: True

    import gui.glava as glava_mod
    monkeypatch.setattr(glava_mod, "adopt_instance", lambda iid: (None, None), raising=False)
    results = {"bars": (True, ""), "wave": (False, "err")}
    monkeypatch.setattr(tab_main_mod, "write_colors_to_frag",
                         lambda module, colors, mode, tmpl_path, live_path: results[module])
    monkeypatch.setattr(tab_main_mod, "glava_restart_instance",
                         lambda instance, module, proc, after_fn: None)
    monkeypatch.setattr(tab, "_save_last_session", lambda: None)

    errors = []
    monkeypatch.setattr(tab_main_mod.messagebox, "showerror",
                         lambda title, msg: errors.append(msg))

    tab._apply_colors()

    assert len(errors) == 1


# ── _capture_colors ──────────────────────────────────────────────────────────

def test_capture_colors_updates_current_colors_when_found(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.color_btns = {k: FakeColorButton(None, k, k, "#000000", None, None)
                       for k in ("top", "mid", "bottom")}
    monkeypatch.setattr(tab_main_mod, "read_colors_from_frag",
                         lambda path: {"top": "#aaaaaa", "mid": "#bbbbbb", "bottom": "#cccccc"})
    tab._capture_colors()
    assert tab.current_colors == {"top": "#aaaaaa", "mid": "#bbbbbb", "bottom": "#cccccc"}
    assert tab.color_btns["top"].color == "#aaaaaa"


def test_capture_colors_does_nothing_when_frag_returns_none(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    monkeypatch.setattr(tab_main_mod, "read_colors_from_frag", lambda path: None)
    original = dict(tab.current_colors)
    tab._capture_colors()
    assert tab.current_colors == original


# ── _change_gradient ──────────────────────────────────────────────────────────

def test_change_gradient_updates_mode_and_persists_settings(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.gradient_var = FakeStringVar("hsv")
    monkeypatch.setattr(tab_main_mod, "set_gradient_mode", lambda *a, **kw: None)
    saved_settings = []
    monkeypatch.setattr(core_mod, "save_settings",
                         lambda settings: saved_settings.append(dict(settings)))
    monkeypatch.setattr(tab_main_mod, "glava_restart", lambda module, after_fn=None: None)

    tab._change_gradient()

    assert tab.gradient_mode == "hsv"
    assert fake_app.settings["gradient_mode"] == "hsv"
    assert saved_settings[-1]["gradient_mode"] == "hsv"


def test_change_gradient_calls_set_gradient_mode_for_active_instance(
        fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.gradient_var = FakeStringVar("rgb")
    monkeypatch.setattr(core_mod, "save_settings", lambda settings: None)
    monkeypatch.setattr(tab_main_mod, "glava_restart", lambda module, after_fn=None: None)

    calls = []
    monkeypatch.setattr(tab_main_mod, "set_gradient_mode",
                         lambda module, mode, live_path, tmpl_path: calls.append((module, mode)))

    tab._change_gradient()

    assert calls == [("bars", "rgb")]


def test_change_gradient_all_instances_restarts_each_and_restores_active(
        fake_app, monkeypatch, tmp_path):
    """Gdy all_inst_var=True: set_gradient_mode wołane dla każdej
    instancji, restart_active_instance wołane per-instancja przez
    tymczasowe podstawienie _active_inst_id/active_instance, a po
    pętli oryginalny aktywny stan jest przywracany i update_status
    wołane RAZ (nie per-instancja)."""
    inst1 = FakeInstance(str(tmp_path), "inst1")
    fake_app.instances = {0: fake_app.active_instance, 1: inst1}
    fake_app._inst_modules = {0: "bars", 1: "wave"}

    tab = _make_tab(fake_app, monkeypatch)
    tab.gradient_var = FakeStringVar("hsv")
    tab.all_inst_var = type("FakeVar", (), {"get": lambda self: True})()

    monkeypatch.setattr(core_mod, "save_settings", lambda settings: None)
    monkeypatch.setattr(tab_main_mod, "set_gradient_mode", lambda *a, **kw: None)

    restart_calls = []
    seen_active_instance_during_restart = []

    def fake_restart_active_instance(module=None, after_fn=None):
        restart_calls.append(module)
        seen_active_instance_during_restart.append(fake_app.active_instance)

    fake_app.restart_active_instance = fake_restart_active_instance

    tab._change_gradient()

    assert sorted(restart_calls) == ["bars", "wave"]
    # Podczas restartu instancji 1, active_instance musiało być inst1
    # (tymczasowe podstawienie), nie oryginalną active_instance.
    assert inst1 in seen_active_instance_during_restart
    # Po pętli stan jest przywrócony do oryginału.
    assert fake_app._active_inst_id == 0
    assert fake_app.active_instance is fake_app.instances[0]
    # update_status wołane RAZ na końcu, nie per-instancja w pętli.
    assert fake_app.update_status_calls == 1


def test_change_gradient_single_instance_uses_restart_active_instance_when_available(
        fake_app, monkeypatch):
    """all_inst=False (lub brak all_inst_var) -> gałąź elif: restart
    tylko aktywnej instancji przez restart_active_instance, bez pętli
    po wszystkich instancjach."""
    tab = _make_tab(fake_app, monkeypatch)
    tab.gradient_var = FakeStringVar("rgb")
    monkeypatch.setattr(core_mod, "save_settings", lambda settings: None)
    monkeypatch.setattr(tab_main_mod, "set_gradient_mode", lambda *a, **kw: None)

    restart_calls = []
    fake_app.restart_active_instance = lambda after_fn=None: restart_calls.append(True)
    legacy_calls = []
    monkeypatch.setattr(tab_main_mod, "glava_restart",
                         lambda module, after_fn=None: legacy_calls.append(module))

    tab._change_gradient()

    assert restart_calls == [True]
    assert legacy_calls == []


# ── _update_hsv_warn ──────────────────────────────────────────────────────────

def test_update_hsv_warn_sets_warning_when_not_supported(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)

    class FakeLabel:
        def __init__(self):
            self.text = None
        def config(self, text):
            self.text = text

    tab.hsv_warn = FakeLabel()
    monkeypatch.setattr(tab_main_mod, "shader_supports_hsv", lambda module, **kw: False)
    tab._update_hsv_warn()
    assert tab.hsv_warn.text == "⚠ RGB only"


def test_update_hsv_warn_clears_warning_when_supported(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)

    class FakeLabel:
        def __init__(self):
            self.text = None
        def config(self, text):
            self.text = text

    tab.hsv_warn = FakeLabel()
    monkeypatch.setattr(tab_main_mod, "shader_supports_hsv", lambda module, **kw: True)
    tab._update_hsv_warn()
    assert tab.hsv_warn.text == ""


def test_update_hsv_warn_noop_when_no_hsv_warn_attribute(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    assert not hasattr(tab, "hsv_warn")
    tab._update_hsv_warn()  # nie powinno crashować


# ── refresh_gradient_mode ────────────────────────────────────────────────────

def test_refresh_gradient_mode_sets_hsv_when_define_present(
        fake_app, monkeypatch, tmp_path):
    tab = _make_tab(fake_app, monkeypatch)
    live_path = str(tmp_path / "live.frag")
    with open(live_path, "w") as f:
        f.write("#define HSV_MODE 1\n")
    monkeypatch.setattr(tab, "_live_frag", lambda: live_path)
    tab.gradient_var = FakeStringVar("rgb")
    monkeypatch.setattr(tab, "_update_hsv_warn", lambda: None)

    tab.refresh_gradient_mode()

    assert tab.gradient_mode == "hsv"
    assert tab.gradient_var.get() == "hsv"


def test_refresh_gradient_mode_sets_rgb_when_define_zero(
        fake_app, monkeypatch, tmp_path):
    tab = _make_tab(fake_app, monkeypatch)
    live_path = str(tmp_path / "live.frag")
    with open(live_path, "w") as f:
        f.write("#define HSV_MODE 0\n")
    monkeypatch.setattr(tab, "_live_frag", lambda: live_path)
    tab.gradient_var = FakeStringVar("hsv")
    monkeypatch.setattr(tab, "_update_hsv_warn", lambda: None)

    tab.refresh_gradient_mode()

    assert tab.gradient_mode == "rgb"


def test_refresh_gradient_mode_noop_when_file_missing(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    monkeypatch.setattr(tab, "_live_frag", lambda: "/nonexistent/path.frag")
    tab.gradient_mode = "rgb"
    warn_calls = []
    monkeypatch.setattr(tab, "_update_hsv_warn", lambda: warn_calls.append(True))

    tab.refresh_gradient_mode()

    assert tab.gradient_mode == "rgb"
    assert warn_calls == []  # early return przed _update_hsv_warn


def test_refresh_gradient_mode_no_define_leaves_mode_unchanged(
        fake_app, monkeypatch, tmp_path):
    tab = _make_tab(fake_app, monkeypatch)
    live_path = str(tmp_path / "live.frag")
    with open(live_path, "w") as f:
        f.write("vec3 top = vec3(1.0, 1.0, 1.0);\n")
    monkeypatch.setattr(tab, "_live_frag", lambda: live_path)
    tab.gradient_mode = "rgb"
    monkeypatch.setattr(tab, "_update_hsv_warn", lambda: None)

    tab.refresh_gradient_mode()

    assert tab.gradient_mode == "rgb"


# ── refresh_active_instance ──────────────────────────────────────────────────

def test_refresh_active_instance_calls_all_refresh_steps(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.color_btns = {"top": FakeColorButton(None, "top", "Top", "#000000", None, None)}
    calls = []
    monkeypatch.setattr(tab, "_load_colors_from_live", lambda: calls.append("load"))
    monkeypatch.setattr(tab, "refresh_gradient_mode", lambda: calls.append("gradient"))
    monkeypatch.setattr(tab, "refresh_geometry", lambda: calls.append("geometry"))

    tab.refresh_active_instance()

    assert calls == ["load", "gradient", "geometry"]


# ── refresh_geometry ──────────────────────────────────────────────────────────

def test_refresh_geometry_updates_geo_vars_when_geometry_found(
        fake_app, monkeypatch, tmp_path):
    tab = _make_tab(fake_app, monkeypatch)
    rc_path = str(tmp_path / "rc.glsl")
    with open(rc_path, "w") as f:
        f.write("#request setgeometry 10 20 800 600\n")
    monkeypatch.setattr(core_mod, "RC_GLSL", rc_path)
    tab.geo_vars = {k: FakeStringVar() for k in ("x", "y", "w", "h")}

    tab.refresh_geometry()

    assert tab.geo_vars["x"].get() == "10"
    assert tab.geo_vars["y"].get() == "20"
    assert tab.geo_vars["w"].get() == "800"
    assert tab.geo_vars["h"].get() == "600"


def test_refresh_geometry_noop_without_geo_vars_attribute(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    assert not hasattr(tab, "geo_vars")
    tab.refresh_geometry()  # nie powinno crashować


# ── destroy ───────────────────────────────────────────────────────────────────

def test_destroy_stops_meta_watch(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab._meta_watch_active = True
    tab.destroy()
    assert tab._meta_watch_active is False


# ── _wp_prev / _wp_next / _update_region_indicator ──────────────────────────

def test_wp_next_wraps_around_to_first_region(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab._wp_regions = ["de-DE", "en-US", "pl-PL"]
    tab._wp_region_idx = 2  # ostatni
    monkeypatch.setattr(tab, "_update_region_indicator", lambda: None)
    monkeypatch.setattr(tab, "_load_wp_thumbnail", lambda: None)
    monkeypatch.setattr(tab, "_save_region", lambda: None)

    tab._wp_next()

    assert tab._wp_region_idx == 0  # wrap-around


def test_wp_prev_wraps_around_to_last_region(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab._wp_regions = ["de-DE", "en-US", "pl-PL"]
    tab._wp_region_idx = 0  # pierwszy
    monkeypatch.setattr(tab, "_update_region_indicator", lambda: None)
    monkeypatch.setattr(tab, "_load_wp_thumbnail", lambda: None)
    monkeypatch.setattr(tab, "_save_region", lambda: None)

    tab._wp_prev()

    assert tab._wp_region_idx == 2  # wrap-around na koniec listy


def test_wp_next_calls_save_region(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab._wp_regions = ["de-DE", "en-US"]
    tab._wp_region_idx = 0
    monkeypatch.setattr(tab, "_update_region_indicator", lambda: None)
    monkeypatch.setattr(tab, "_load_wp_thumbnail", lambda: None)
    saved = []
    monkeypatch.setattr(tab, "_save_region", lambda: saved.append(True))
    tab._wp_next()
    assert saved == [True]


def test_update_region_indicator_formats_correctly(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab._wp_regions = ["de-DE", "en-US", "pl-PL"]
    tab._wp_region_idx = 1
    tab._region_indicator_var = FakeStringVar()
    tab._update_region_indicator()
    assert tab._region_indicator_var.get() == "en-US  \u00b7  2 / 3"


# ── _save_region / _save_settings / _toggle_lock ────────────────────────────

def test_save_region_writes_current_region_to_config(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab._wp_regions = ["de-DE", "en-US"]
    tab._wp_region_idx = 1
    tab.bing_cfg = {}
    written = []
    monkeypatch.setattr(tab_main_mod, "write_bing_config",
                         lambda cfg: written.append(dict(cfg)))
    tab._save_region()
    assert written[-1]["BING_REGION"] == "en-US"


def test_save_settings_writes_config_and_shows_info(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab._wp_regions = ["de-DE", "en-US"]
    tab._wp_region_idx = 0
    tab.bing_cfg = {}
    written = []
    monkeypatch.setattr(tab_main_mod, "write_bing_config",
                         lambda cfg: written.append(dict(cfg)))
    info_calls = []
    monkeypatch.setattr(tab_main_mod.messagebox, "showinfo",
                         lambda title, msg: info_calls.append(msg))
    tab._save_settings()
    assert written[-1]["BING_REGION"] == "de-DE"
    assert len(info_calls) == 1


def test_toggle_lock_calls_toggle_and_updates_status(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    toggle_calls = []
    monkeypatch.setattr(tab_main_mod, "toggle_wallpaper_lock",
                         lambda path: toggle_calls.append(path))
    tab._toggle_lock()
    assert len(toggle_calls) == 1
    assert fake_app.update_status_calls == 1


# ── _toggle_glava ─────────────────────────────────────────────────────────────

def test_toggle_glava_calls_glava_toggle(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)

    class FakeRoot:
        def after(self, delay, fn):
            fn()  # wykonaj natychmiast w teście
    fake_app.root = FakeRoot()

    toggle_calls = []
    monkeypatch.setattr(tab_main_mod, "glava_toggle", lambda: toggle_calls.append(True))
    tab._toggle_glava()
    assert toggle_calls == [True]
    assert fake_app.update_status_calls == 1


# ── _apply_geometry — walidacja int / wartości dodatnie ─────────────────────

def test_apply_geometry_rejects_non_integer_values(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.geo_vars = {
        "x": FakeStringVar("not-a-number"), "y": FakeStringVar("0"),
        "w": FakeStringVar("100"), "h": FakeStringVar("100"),
    }
    errors = []
    monkeypatch.setattr(tab_main_mod.messagebox, "showerror",
                         lambda title, msg: errors.append(msg))
    write_calls = []
    monkeypatch.setattr(tab_main_mod, "write_geometry",
                         lambda *a: write_calls.append(True))

    tab._apply_geometry()

    assert len(errors) == 1
    assert write_calls == []


def test_apply_geometry_rejects_non_positive_width_or_height(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.geo_vars = {
        "x": FakeStringVar("0"), "y": FakeStringVar("0"),
        "w": FakeStringVar("0"), "h": FakeStringVar("100"),
    }
    errors = []
    monkeypatch.setattr(tab_main_mod.messagebox, "showerror",
                         lambda title, msg: errors.append(msg))
    write_calls = []
    monkeypatch.setattr(tab_main_mod, "write_geometry",
                         lambda *a: write_calls.append(True))

    tab._apply_geometry()

    assert len(errors) == 1
    assert write_calls == []


def test_apply_geometry_writes_and_restarts_on_success(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.geo_vars = {
        "x": FakeStringVar("10"), "y": FakeStringVar("20"),
        "w": FakeStringVar("800"), "h": FakeStringVar("600"),
    }
    write_calls = []
    monkeypatch.setattr(tab_main_mod, "write_geometry",
                         lambda rc_path, x, y, w, h: (
                             write_calls.append((x, y, w, h)), True)[1])
    info_calls = []
    monkeypatch.setattr(tab_main_mod.messagebox, "showinfo",
                         lambda title, msg: info_calls.append(msg))
    restart_calls = []
    monkeypatch.setattr(tab_main_mod, "glava_restart",
                         lambda module, after_fn=None: restart_calls.append(module))

    tab._apply_geometry()

    assert write_calls == [(10, 20, 800, 600)]
    assert len(info_calls) == 1
    assert restart_calls == ["bars"]


def test_apply_geometry_no_restart_message_when_write_fails(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.geo_vars = {
        "x": FakeStringVar("10"), "y": FakeStringVar("20"),
        "w": FakeStringVar("800"), "h": FakeStringVar("600"),
    }
    monkeypatch.setattr(tab_main_mod, "write_geometry", lambda *a: False)
    info_calls = []
    monkeypatch.setattr(tab_main_mod.messagebox, "showinfo",
                         lambda title, msg: info_calls.append(msg))
    restart_calls = []
    monkeypatch.setattr(tab_main_mod, "glava_restart",
                         lambda module, after_fn=None: restart_calls.append(module))

    tab._apply_geometry()

    assert info_calls == []
    assert restart_calls == []


# ── _auto_geometry ────────────────────────────────────────────────────────────

def test_auto_geometry_updates_geo_vars_and_writes(fake_app, monkeypatch):
    tab = _make_tab(fake_app, monkeypatch)
    tab.geo_vars = {k: FakeStringVar() for k in ("x", "y", "w", "h")}

    monkeypatch.setattr(tab_main_mod, "get_screen_info",
                         lambda: (1920, 1080, 1040, 0, 40, 0, 0))
    monkeypatch.setattr(tab_main_mod, "calc_geometry",
                         lambda module, sw, sh, bottom, top: (0, -40, 1920, 1080))
    monkeypatch.setattr(tab_main_mod.messagebox, "showinfo", lambda *a, **kw: None)
    write_calls = []
    monkeypatch.setattr(tab_main_mod, "write_geometry",
                         lambda rc_path, x, y, w, h: (
                             write_calls.append((x, y, w, h)), True)[1])
    restart_calls = []
    monkeypatch.setattr(tab_main_mod, "glava_restart",
                         lambda module, after_fn=None: restart_calls.append(module))

    tab._auto_geometry()

    assert tab.geo_vars["x"].get() == "0"
    assert tab.geo_vars["w"].get() == "1920"
    assert write_calls == [(0, -40, 1920, 1080)]
    assert restart_calls == ["bars"]


# ── _update_geometry_for_module ──────────────────────────────────────────────
# Metoda jest owinięta w try/except Exception: pass (świadomie szerokie —
# błąd w detekcji geometrii nie powinien crashować zmiany modułu), więc
# testy weryfikują efekt (write_geometry wywołane z poprawnymi parametrami),
# nie brak wyjątku — brak wyjątku jest gwarantowany przez sam kod.

@pytest.fixture
def geometry_env(tmp_path, fake_app, monkeypatch):
    """Izoluje glava_dir i rc_path przez metody app (hasattr-checked w
    kodzie: get_active_glava_dir / get_active_rc_glsl)."""
    glava_dir = tmp_path / "glava"
    glava_dir.mkdir()
    rc_path = tmp_path / "rc.glsl"
    rc_path.write_text("#request setgeometry 0 0 100 100\n")

    fake_app.get_active_glava_dir = lambda: str(glava_dir)
    fake_app.get_active_rc_glsl = lambda: str(rc_path)
    return str(glava_dir), str(rc_path)


def test_update_geometry_bars_reads_flip_and_mirror_yx(
        fake_app, monkeypatch, geometry_env):
    glava_dir, rc_path = geometry_env
    tab = _make_tab(fake_app, monkeypatch)

    with open(os.path.join(glava_dir, "bars.glsl"), "w") as f:
        f.write("#define FLIP 1\n#define MIRROR_YX 1\n")

    monkeypatch.setattr(geometry_mod, "get_screen_info",
                         lambda: (1920, 1080, 1040, 0, 40, 0, 50))

    calc_calls = []
    def fake_calc_geometry(module, sw, sh, bottom, top, flipped, mirror_yx,
                            left_reserved, right_reserved):
        calc_calls.append({
            "module": module, "flipped": flipped, "mirror_yx": mirror_yx,
            "left_reserved": left_reserved, "right_reserved": right_reserved,
        })
        return (0, 0, sw, sh)
    monkeypatch.setattr(geometry_mod, "calc_geometry", fake_calc_geometry)

    write_calls = []
    monkeypatch.setattr(geometry_mod, "write_geometry",
                         lambda rc, x, y, w, h: write_calls.append((rc, x, y, w, h)))

    tab._update_geometry_for_module("bars")

    assert calc_calls == [{
        "module": "bars", "flipped": True, "mirror_yx": True,
        "left_reserved": 0, "right_reserved": 50,
    }]
    assert write_calls == [(rc_path, 0, 0, 1920, 1080)]


def test_update_geometry_bars_defaults_when_defines_absent(
        fake_app, monkeypatch, geometry_env):
    glava_dir, rc_path = geometry_env
    tab = _make_tab(fake_app, monkeypatch)

    with open(os.path.join(glava_dir, "bars.glsl"), "w") as f:
        f.write("// no flip defines here\n")

    monkeypatch.setattr(geometry_mod, "get_screen_info",
                         lambda: (1920, 1080, 1040, 0, 40, 0, 0))
    calc_calls = []
    monkeypatch.setattr(geometry_mod, "calc_geometry",
                         lambda module, sw, sh, bottom, top, flipped, mirror_yx,
                         left_reserved, right_reserved: (
                             calc_calls.append((flipped, mirror_yx)),
                             (0, 0, sw, sh))[1])
    monkeypatch.setattr(geometry_mod, "write_geometry", lambda *a: None)

    tab._update_geometry_for_module("bars")

    assert calc_calls == [(False, False)]


def test_update_geometry_bars_missing_glsl_file_uses_defaults(
        fake_app, monkeypatch, geometry_env):
    """bars.glsl nie istnieje na dysku -> flipped/mirror_yx zostają False
    (os.path.exists guard), nie podnosi wyjątku."""
    glava_dir, rc_path = geometry_env
    tab = _make_tab(fake_app, monkeypatch)
    # Nie tworzymy bars.glsl

    monkeypatch.setattr(geometry_mod, "get_screen_info",
                         lambda: (1920, 1080, 1040, 0, 40, 0, 0))
    calc_calls = []
    monkeypatch.setattr(geometry_mod, "calc_geometry",
                         lambda module, sw, sh, bottom, top, flipped, mirror_yx,
                         left_reserved, right_reserved: (
                             calc_calls.append((flipped, mirror_yx)),
                             (0, 0, sw, sh))[1])
    monkeypatch.setattr(geometry_mod, "write_geometry", lambda *a: None)

    tab._update_geometry_for_module("bars")

    assert calc_calls == [(False, False)]


def test_update_geometry_graph_reads_invert_as_flipped(
        fake_app, monkeypatch, geometry_env):
    """Dla modułu 'graph' flagą jest #define INVERT, mapowana na flipped
    (graph nie ma MIRROR_YX — zawsze mirror_yx=False)."""
    glava_dir, rc_path = geometry_env
    tab = _make_tab(fake_app, monkeypatch)

    with open(os.path.join(glava_dir, "graph.glsl"), "w") as f:
        f.write("#define INVERT 1\n")

    monkeypatch.setattr(geometry_mod, "get_screen_info",
                         lambda: (1920, 1080, 1040, 0, 40, 0, 0))
    calc_calls = []
    monkeypatch.setattr(geometry_mod, "calc_geometry",
                         lambda module, sw, sh, bottom, top, flipped, mirror_yx,
                         left_reserved, right_reserved: (
                             calc_calls.append((flipped, mirror_yx)),
                             (0, 0, sw, sh))[1])
    monkeypatch.setattr(geometry_mod, "write_geometry", lambda *a: None)

    tab._update_geometry_for_module("graph")

    assert calc_calls == [(True, False)]


def test_update_geometry_centered_module_skips_define_parsing(
        fake_app, monkeypatch, geometry_env):
    """Dla modułów spoza bars/graph (np. circle) flipped/mirror_yx zawsze
    False — kod nie próbuje parsować żadnego pliku .glsl dla nich."""
    glava_dir, rc_path = geometry_env
    tab = _make_tab(fake_app, monkeypatch)

    monkeypatch.setattr(geometry_mod, "get_screen_info",
                         lambda: (1920, 1080, 1040, 0, 40, 0, 0))
    calc_calls = []
    monkeypatch.setattr(geometry_mod, "calc_geometry",
                         lambda module, sw, sh, bottom, top, flipped, mirror_yx,
                         left_reserved, right_reserved: (
                             calc_calls.append((flipped, mirror_yx)),
                             (0, 0, sw, sh))[1])
    monkeypatch.setattr(geometry_mod, "write_geometry", lambda *a: None)

    tab._update_geometry_for_module("circle")

    assert calc_calls == [(False, False)]


def test_update_geometry_swallows_exceptions_silently(fake_app, monkeypatch):
    """Brak get_active_glava_dir/get_active_rc_glsl -> kod używa
    fallbacków (os.path.expanduser, core.RC_GLSL). Jeśli coś dalej
    rzuci wyjątek (np. calc_geometry zepsute), całość jest wyciszana
    przez except Exception: pass — metoda nie powinna nigdy crashować
    wywołującego."""
    tab = _make_tab(fake_app, monkeypatch)

    monkeypatch.setattr(geometry_mod, "get_screen_info",
                         lambda: (1920, 1080, 1040, 0, 40, 0, 0))

    def broken_calc_geometry(*a, **kw):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr(geometry_mod, "calc_geometry", broken_calc_geometry)

    tab._update_geometry_for_module("bars")  # nie powinno podnieść wyjątku


# ── _restore_auto — sync z tapetą (KMeans), single vs multi-instance ───────

def test_restore_auto_shows_error_when_wallpaper_missing(fake_app, monkeypatch):
    """Używamy nieistniejącej ścieżki tapety (katalog na pewno nie ma
    pliku bing_today.jpg) — bezpieczniejsze niż globalny monkeypatch na
    os.path.exists, który zepsułby pytest/coverage wewnętrznie."""
    tab = _make_tab(fake_app, monkeypatch)
    monkeypatch.setattr(os.path, "expanduser",
                         lambda p: "/nonexistent/path/bing_today.jpg"
                         if "bing_today" in p else p)
    errors = []
    monkeypatch.setattr(tab_main_mod.messagebox, "showerror",
                         lambda title, msg: errors.append(msg))
    tab._restore_auto()
    assert len(errors) == 1


def test_restore_auto_shows_error_when_kmeans_returns_none(
        fake_app, monkeypatch, tmp_path):
    tab = _make_tab(fake_app, monkeypatch)
    wallpaper = tmp_path / "bing_today.jpg"
    wallpaper.write_text("fake")
    monkeypatch.setattr(os.path, "expanduser",
                         lambda p: str(wallpaper) if "bing_today" in p else p)

    import gui.colors as colors_mod
    monkeypatch.setattr(colors_mod, "extract_colors_from_wallpaper", lambda path: None)

    errors = []
    monkeypatch.setattr(tab_main_mod.messagebox, "showerror",
                         lambda title, msg: errors.append(msg))
    write_calls = []
    monkeypatch.setattr(tab_main_mod, "write_colors_to_frag",
                         lambda *a, **kw: write_calls.append(True))

    tab._restore_auto()

    assert len(errors) == 1
    assert write_calls == []


def test_restore_auto_single_instance_writes_and_restarts(
        fake_app, monkeypatch, tmp_path):
    tab = _make_tab(fake_app, monkeypatch)
    wallpaper = tmp_path / "bing_today.jpg"
    wallpaper.write_text("fake")
    monkeypatch.setattr(os.path, "expanduser",
                         lambda p: str(wallpaper) if "bing_today" in p else p)

    extracted_colors = {"top": "#111111", "mid": "#222222", "bottom": "#333333"}
    import gui.colors as colors_mod
    monkeypatch.setattr(colors_mod, "extract_colors_from_wallpaper",
                         lambda path: extracted_colors)

    write_calls = []
    monkeypatch.setattr(tab_main_mod, "write_colors_to_frag",
                         lambda module, colors, mode, tmpl_path, live_path:
                         write_calls.append((module, colors)))

    restart_calls = []
    monkeypatch.setattr(tab_main_mod, "glava_restart_instance",
                         lambda instance, module, proc, after_fn: restart_calls.append(module))

    fake_app.root = type("FakeRoot", (), {"after": staticmethod(lambda d, fn: fn())})()
    fake_app.processes = {0: None}

    tab._restore_auto()

    assert write_calls == [("bars", extracted_colors)]
    assert restart_calls == ["bars"]
    assert fake_app.update_status_calls == 1


def test_restore_auto_removes_flag_files_after_restore(
        fake_app, monkeypatch, tmp_path, isolated_flags):
    tab = _make_tab(fake_app, monkeypatch)
    wallpaper = tmp_path / "bing_today.jpg"
    wallpaper.write_text("fake")
    monkeypatch.setattr(os.path, "expanduser",
                         lambda p: str(wallpaper) if "bing_today" in p else p)

    flag_red, flag_manual = isolated_flags
    open(flag_red, "a").close()
    open(flag_manual, "a").close()
    assert os.path.exists(flag_red)
    assert os.path.exists(flag_manual)

    import gui.colors as colors_mod
    monkeypatch.setattr(colors_mod, "extract_colors_from_wallpaper",
                         lambda path: {"top": "#fff", "mid": "#888", "bottom": "#000"})
    monkeypatch.setattr(tab_main_mod, "write_colors_to_frag", lambda *a, **kw: None)
    monkeypatch.setattr(tab_main_mod, "glava_restart_instance",
                         lambda instance, module, proc, after_fn: None)
    fake_app.root = type("FakeRoot", (), {"after": staticmethod(lambda d, fn: fn())})()
    fake_app.processes = {0: None}

    tab._restore_auto()

    assert not os.path.exists(flag_red)
    assert not os.path.exists(flag_manual)


def test_restore_auto_all_instances_writes_each_and_adopts_missing_processes(
        fake_app, monkeypatch, tmp_path):
    """Gdy all_inst_var=True i app.instances istnieje: dla każdej instancji
    bez procesu (processes[iid] is None) wołane jest adopt_instance, a
    potem write_colors_to_frag + glava_restart_instance per instancja."""
    inst1 = FakeInstance(str(tmp_path), "inst1")
    fake_app.instances = {0: fake_app.active_instance, 1: inst1}
    fake_app._inst_modules = {0: "bars", 1: "wave"}
    fake_app.processes = {0: None, 1: None}
    fake_app.root = type("FakeRoot", (), {"after": staticmethod(lambda d, fn: fn())})()

    tab = _make_tab(fake_app, monkeypatch)
    tab.all_inst_var = type("FakeVar", (), {"get": lambda self: True})()

    wallpaper = tmp_path / "bing_today.jpg"
    wallpaper.write_text("fake")
    monkeypatch.setattr(os.path, "expanduser",
                         lambda p: str(wallpaper) if "bing_today" in p else p)

    import gui.colors as colors_mod
    monkeypatch.setattr(colors_mod, "extract_colors_from_wallpaper",
                         lambda path: {"top": "#fff", "mid": "#888", "bottom": "#000"})

    import gui.glava as glava_mod
    adopt_calls = []
    monkeypatch.setattr(glava_mod, "adopt_instance",
                         lambda iid: (adopt_calls.append(iid), (None, "FAKE_PROC"))[1])

    write_calls = []
    monkeypatch.setattr(tab_main_mod, "write_colors_to_frag",
                         lambda module, colors, mode, tmpl_path, live_path:
                         write_calls.append(module))
    restart_calls = []
    monkeypatch.setattr(tab_main_mod, "glava_restart_instance",
                         lambda instance, module, proc, after_fn: restart_calls.append(module))

    tab._restore_auto()

    assert sorted(adopt_calls) == [0, 1]
    assert sorted(write_calls) == ["bars", "wave"]
    assert sorted(restart_calls) == ["bars", "wave"]


def test_restore_auto_skips_adopt_for_instances_with_running_process(
        fake_app, monkeypatch, tmp_path):
    """Instancja z już istniejącym procesem (processes[iid] is not None)
    nie powinna wywołać adopt_instance dla niej."""
    inst1 = FakeInstance(str(tmp_path), "inst1")
    fake_app.instances = {0: fake_app.active_instance, 1: inst1}
    fake_app._inst_modules = {0: "bars", 1: "wave"}
    fake_app.processes = {0: "ALREADY_RUNNING", 1: None}
    fake_app.root = type("FakeRoot", (), {"after": staticmethod(lambda d, fn: fn())})()

    tab = _make_tab(fake_app, monkeypatch)
    tab.all_inst_var = type("FakeVar", (), {"get": lambda self: True})()

    wallpaper = tmp_path / "bing_today.jpg"
    wallpaper.write_text("fake")
    monkeypatch.setattr(os.path, "expanduser",
                         lambda p: str(wallpaper) if "bing_today" in p else p)

    import gui.colors as colors_mod
    monkeypatch.setattr(colors_mod, "extract_colors_from_wallpaper",
                         lambda path: {"top": "#fff", "mid": "#888", "bottom": "#000"})

    import gui.glava as glava_mod
    adopt_calls = []
    monkeypatch.setattr(glava_mod, "adopt_instance",
                         lambda iid: (adopt_calls.append(iid), (None, "FAKE_PROC"))[1])

    monkeypatch.setattr(tab_main_mod, "write_colors_to_frag", lambda *a, **kw: None)
    monkeypatch.setattr(tab_main_mod, "glava_restart_instance",
                         lambda instance, module, proc, after_fn: None)

    tab._restore_auto()

    assert adopt_calls == [1]  # tylko instancja 1, bo 0 ma już proces


# ── build_tab_main — module-level entry point ───────────────────────────────

def test_build_tab_main_creates_tabmain_calls_build_and_sets_ref(
        fake_app, monkeypatch):
    build_calls = []

    class FakeTabMain:
        def __init__(self, parent, app):
            self.parent = parent
            self.app = app
        def build(self):
            build_calls.append(True)

    monkeypatch.setattr(tab_main_mod, "TabMain", FakeTabMain)
    tab_main_mod.build_tab_main(parent="PARENT", app=fake_app)

    assert build_calls == [True]
    assert isinstance(fake_app._tab_main_ref, FakeTabMain)
