import os
import sys
import shutil
import pytest
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import gui.tab_module as tab_module_mod
import gui.core as core_mod


# ── Fakes ─────────────────────────────────────────────────────────────────────

class FakeT(dict):
    """T.get(key, default) — symuluje słownik tłumaczeń zwracany przez
    core.load_lang(), które jest zwykłym dict-em z json.load()."""
    pass


class FakeApp:
    """Minimalna implementacja interfejsu, jakiego TabModule wymaga od app:
    .T, .active_module, .rebuild_module_tab(), .update_status().
    Domyślnie BEZ restart_active_instance — wymusza ścieżkę legacy
    (glava_restart) w _reset_shader/_apply_profile, zgodnie z hasattr-check
    w kodzie."""
    def __init__(self, module="bars"):
        self.T = FakeT()
        self.active_module = module
        self.rebuild_calls = 0
        self.update_status_calls = 0

    def rebuild_module_tab(self):
        self.rebuild_calls += 1

    def update_status(self):
        self.update_status_calls += 1


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_app():
    return FakeApp(module="bars")


@pytest.fixture
def tab(fake_app):
    """TabModule bez wywoływania build() — testujemy metody w izolacji."""
    return tab_module_mod.TabModule(parent=None, app=fake_app)


@pytest.fixture
def no_dialogs(monkeypatch):
    """Zastępuje messagebox/simpledialog w gui.tab_module mockami, żeby
    żaden test nie odpalił realnego okna modalnego. Domyślnie:
    askyesno -> True, askstring -> None, showinfo/showwarning -> no-op."""
    calls = {"askyesno": [], "askstring": [], "showinfo": [], "showwarning": []}

    class FakeMessagebox:
        @staticmethod
        def askyesno(*a, **kw):
            calls["askyesno"].append((a, kw))
            return True

        @staticmethod
        def showinfo(*a, **kw):
            calls["showinfo"].append((a, kw))

        @staticmethod
        def showwarning(*a, **kw):
            calls["showwarning"].append((a, kw))

    class FakeSimpledialog:
        @staticmethod
        def askstring(*a, **kw):
            calls["askstring"].append((a, kw))
            return None

    monkeypatch.setattr(tab_module_mod, "messagebox", FakeMessagebox)
    monkeypatch.setattr(tab_module_mod, "simpledialog", FakeSimpledialog)
    return calls


@pytest.fixture
def isolated_glava_dir(tmp_path, monkeypatch):
    """Izoluje core.GLAVA_DIR do tmp_path, żeby testy fallbacku w
    _reset_shader (get_template/get_live_frag) nie dotykały realnego
    ~/.config/glava."""
    glava_dir = tmp_path / "glava"
    glava_dir.mkdir()
    monkeypatch.setattr(core_mod, "GLAVA_DIR", str(glava_dir))
    monkeypatch.setattr(tab_module_mod, "get_template",
                         lambda module=None: os.path.join(
                             str(glava_dir),
                             core_mod.MODULE_TEMPLATES.get(module, "graph_colors.frag")))
    monkeypatch.setattr(tab_module_mod, "get_live_frag",
                         lambda module=None: os.path.join(
                             str(glava_dir),
                             core_mod.MODULE_LIVEFRAGS.get(module, "graph/1.frag")))
    return str(glava_dir)


# ── _load_module_plugin ──────────────────────────────────────────────────────

def test_load_module_plugin_imports_real_module():
    """_load_module_plugin('bars') powinno zaimportować gui.modules.bars."""
    mod = tab_module_mod._load_module_plugin("bars")
    assert mod.__name__ == "gui.modules.bars"


def test_load_module_plugin_unknown_module_raises_importerror():
    with pytest.raises(ImportError):
        tab_module_mod._load_module_plugin("nonexistent_module_xyz")


# ── _build_module_params — dispatch / fallback do placeholdera ─────────────

def test_build_module_params_falls_back_to_placeholder_on_importerror(
        tab, fake_app, monkeypatch):
    """Gdy moduł nie istnieje, _build_module_params nie crashuje — woła
    _build_placeholder zamiast podnosić wyjątek dalej."""
    fake_app.active_module = "nonexistent_module_xyz"
    tab.module = "nonexistent_module_xyz"

    placeholder_calls = []
    monkeypatch.setattr(
        tab_module_mod, "_build_placeholder",
        lambda parent, module, T: placeholder_calls.append(module))

    tab._build_module_params(parent=None)
    assert placeholder_calls == ["nonexistent_module_xyz"]


def test_build_module_params_delegates_to_plugin_build_params(
        tab, fake_app, monkeypatch):
    """Gdy plugin istnieje, _build_module_params woła mod.build_params(...)."""
    calls = []

    class FakePlugin:
        @staticmethod
        def build_params(parent, app, T):
            calls.append((parent, app, T))

    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: FakePlugin)
    tab._build_module_params(parent="PARENT_SENTINEL")
    assert len(calls) == 1
    assert calls[0][0] == "PARENT_SENTINEL"
    assert calls[0][1] is fake_app


# ── _apply_profile ───────────────────────────────────────────────────────────

def test_apply_profile_does_nothing_if_name_empty(tab, fake_app, monkeypatch):
    """Brak wybranego profilu (profile_var puste) -> early return, brak
    wywołania apply_params."""
    class FakeVar:
        def get(self):
            return ""
    tab.profile_var = FakeVar()

    called = []
    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: called.append(name))
    tab._apply_profile()
    assert called == []


def test_apply_profile_does_nothing_if_name_not_in_profiles(
        tab, fake_app, monkeypatch):
    class FakeVar:
        def get(self):
            return "Nieistniejący profil"
    tab.profile_var = FakeVar()

    monkeypatch.setattr(tab_module_mod, "get_shader_profiles_for_module",
                         lambda module: {"Inny": {}})
    called = []
    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: called.append(name))
    tab._apply_profile()
    assert called == []


def test_apply_profile_applies_params_and_uses_legacy_restart_without_restart_active_instance(
        tab, fake_app, monkeypatch):
    """Gdy app NIE ma restart_active_instance, _apply_profile musi spaść
    na legacy glava_restart (hasattr-check w kodzie)."""
    class FakeVar:
        def get(self):
            return "MyProfile"
    tab.profile_var = FakeVar()

    monkeypatch.setattr(tab_module_mod, "get_shader_profiles_for_module",
                         lambda module: {"MyProfile": {"key": 1}})

    applied = []

    class FakePlugin:
        @staticmethod
        def apply_params(params, app):
            applied.append(params)

    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: FakePlugin)

    restart_calls = []
    monkeypatch.setattr(tab_module_mod, "glava_restart",
                         lambda module, after_fn=None: restart_calls.append(module))

    assert not hasattr(fake_app, "restart_active_instance")
    tab._apply_profile()

    assert applied == [{"key": 1}]
    assert restart_calls == ["bars"]


def test_apply_profile_uses_restart_active_instance_when_available(
        tab, fake_app, monkeypatch):
    """Gdy app MA restart_active_instance, _apply_profile powinno użyć go
    zamiast legacy glava_restart."""
    class FakeVar:
        def get(self):
            return "MyProfile"
    tab.profile_var = FakeVar()

    monkeypatch.setattr(tab_module_mod, "get_shader_profiles_for_module",
                         lambda module: {"MyProfile": {"key": 1}})

    class FakePlugin:
        @staticmethod
        def apply_params(params, app):
            pass

    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: FakePlugin)

    legacy_calls = []
    monkeypatch.setattr(tab_module_mod, "glava_restart",
                         lambda module, after_fn=None: legacy_calls.append(module))

    restart_calls = []
    fake_app.restart_active_instance = (
        lambda module, after_fn=None: restart_calls.append(module))

    tab._apply_profile()

    assert restart_calls == ["bars"]
    assert legacy_calls == []


def test_apply_profile_swallows_importerror_silently(tab, fake_app, monkeypatch):
    """Jeśli plugin nie istnieje, _apply_profile nie powinno crashować —
    ImportError jest wyciszane (pass)."""
    class FakeVar:
        def get(self):
            return "MyProfile"
    tab.profile_var = FakeVar()

    monkeypatch.setattr(tab_module_mod, "get_shader_profiles_for_module",
                         lambda module: {"MyProfile": {}})

    def raise_import_error(name):
        raise ImportError(name)
    monkeypatch.setattr(tab_module_mod, "_load_module_plugin", raise_import_error)

    tab._apply_profile()  # nie powinno podnieść wyjątku


# ── _save_profile ────────────────────────────────────────────────────────────

def test_save_profile_does_nothing_if_user_cancels_dialog(
        tab, fake_app, no_dialogs, monkeypatch):
    """simpledialog.askstring zwraca None (Cancel) -> early return."""
    called = []
    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: called.append(name))
    tab._save_profile()
    assert called == []
    assert len(no_dialogs["askstring"]) == 1


def test_save_profile_saves_collected_params_and_refreshes(
        tab, fake_app, no_dialogs, monkeypatch):
    class FakeSimpledialog:
        @staticmethod
        def askstring(*a, **kw):
            return "NewProfile"
    monkeypatch.setattr(tab_module_mod, "simpledialog", FakeSimpledialog)

    class FakePlugin:
        @staticmethod
        def collect_params(app):
            return {"a": 1, "b": 2}

    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: FakePlugin)

    saved = []
    monkeypatch.setattr(tab_module_mod, "save_shader_profile_for_module",
                         lambda module, name, params: saved.append((module, name, params)))

    refresh_calls = []
    monkeypatch.setattr(tab, "_refresh_profile_cb",
                         lambda: refresh_calls.append(True))

    class FakeProfileVar:
        def __init__(self):
            self.value = None
        def set(self, v):
            self.value = v
    tab.profile_var = FakeProfileVar()

    tab._save_profile()

    assert saved == [("bars", "NewProfile", {"a": 1, "b": 2})]
    assert refresh_calls == [True]
    assert tab.profile_var.value == "NewProfile"


def test_save_profile_shows_warning_on_importerror(
        tab, fake_app, no_dialogs, monkeypatch):
    class FakeSimpledialog:
        @staticmethod
        def askstring(*a, **kw):
            return "NewProfile"
    monkeypatch.setattr(tab_module_mod, "simpledialog", FakeSimpledialog)

    def raise_import_error(name):
        raise ImportError(name)
    monkeypatch.setattr(tab_module_mod, "_load_module_plugin", raise_import_error)

    tab._save_profile()
    assert len(no_dialogs["showwarning"]) == 1


# ── _delete_profile ──────────────────────────────────────────────────────────

def test_delete_profile_does_nothing_if_name_empty(tab, fake_app, monkeypatch):
    class FakeVar:
        def get(self):
            return ""
    tab.profile_var = FakeVar()

    called = []
    monkeypatch.setattr(tab_module_mod, "delete_shader_profile_for_module",
                         lambda module, name: called.append((module, name)))
    tab._delete_profile()
    assert called == []


def test_delete_profile_skips_when_user_declines_confirm(
        tab, fake_app, monkeypatch):
    class FakeVar:
        def get(self):
            return "ToDelete"
    tab.profile_var = FakeVar()

    class FakeMessagebox:
        @staticmethod
        def askyesno(*a, **kw):
            return False
    monkeypatch.setattr(tab_module_mod, "messagebox", FakeMessagebox)

    called = []
    monkeypatch.setattr(tab_module_mod, "delete_shader_profile_for_module",
                         lambda module, name: called.append((module, name)))
    tab._delete_profile()
    assert called == []


def test_delete_profile_deletes_and_refreshes_when_confirmed(
        tab, fake_app, no_dialogs, monkeypatch):
    class FakeVar:
        def get(self):
            return "ToDelete"
    tab.profile_var = FakeVar()

    deleted = []
    monkeypatch.setattr(tab_module_mod, "delete_shader_profile_for_module",
                         lambda module, name: deleted.append((module, name)))

    refresh_calls = []
    monkeypatch.setattr(tab, "_refresh_profile_cb",
                         lambda: refresh_calls.append(True))

    tab._delete_profile()

    assert deleted == [("bars", "ToDelete")]
    assert refresh_calls == [True]
    assert len(no_dialogs["askyesno"]) == 1


# ── _refresh_profile_cb ───────────────────────────────────────────────────────

class FakeCombobox:
    """Minimalny stub ttk.Combobox — przechowuje 'values' i indeks 'current'."""
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


def test_refresh_profile_cb_sets_sorted_names(tab, fake_app, monkeypatch):
    monkeypatch.setattr(
        tab_module_mod, "get_shader_profiles_for_module",
        lambda module: {"Zebra": {}, "Apple": {}, "Mango": {}})
    tab.profile_cb = FakeCombobox()
    tab._refresh_profile_cb()
    assert tab.profile_cb["values"] == ["Apple", "Mango", "Zebra"]
    assert tab.profile_cb._current_idx == 0


def test_refresh_profile_cb_empty_profiles_does_not_set_current(
        tab, fake_app, monkeypatch):
    """Gdy nie ma żadnych profili, .current(0) nie powinno być wołane
    (lista jest pusta — IndexError gdyby próbowano ustawić current)."""
    monkeypatch.setattr(
        tab_module_mod, "get_shader_profiles_for_module",
        lambda module: {})
    tab.profile_cb = FakeCombobox()
    tab._refresh_profile_cb()
    assert tab.profile_cb["values"] == []
    assert tab.profile_cb._current_idx is None


# ── _reset_shader — confirm dialog gate ─────────────────────────────────────

def test_reset_shader_aborts_if_user_declines_confirm(
        tab, fake_app, monkeypatch):
    class FakeMessagebox:
        @staticmethod
        def askyesno(*a, **kw):
            return False
        @staticmethod
        def showinfo(*a, **kw):
            pass
    monkeypatch.setattr(tab_module_mod, "messagebox", FakeMessagebox)

    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: (_ for _ in ()).throw(
                             AssertionError("nie powinno być wołane")))

    tab._reset_shader()
    assert fake_app.rebuild_calls == 0


# ── _reset_shader — plugin ma reset_shader ──────────────────────────────────

def test_reset_shader_calls_plugin_reset_shader_when_available(
        tab, fake_app, no_dialogs, monkeypatch):
    reset_calls = []

    class FakePlugin:
        @staticmethod
        def reset_shader(app):
            reset_calls.append(app)

    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: FakePlugin)
    monkeypatch.setattr(tab_module_mod, "glava_restart",
                         lambda module, after_fn=None: None)

    tab._reset_shader()

    assert reset_calls == [fake_app]
    assert fake_app.rebuild_calls == 1
    assert len(no_dialogs["showinfo"]) == 1


def test_reset_shader_uses_restart_active_instance_when_available(
        tab, fake_app, no_dialogs, monkeypatch):
    class FakePlugin:
        @staticmethod
        def reset_shader(app):
            pass

    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: FakePlugin)

    restart_calls = []
    fake_app.restart_active_instance = (
        lambda module, after_fn=None: restart_calls.append(module))

    legacy_calls = []
    monkeypatch.setattr(tab_module_mod, "glava_restart",
                         lambda module, after_fn=None: legacy_calls.append(module))

    tab._reset_shader()

    assert restart_calls == ["bars"]
    assert legacy_calls == []


# ── _reset_shader — plugin BEZ reset_shader -> fallback kopiowania ─────────

def test_reset_shader_fallback_copies_template_when_plugin_lacks_reset_shader(
        tab, fake_app, no_dialogs, monkeypatch, isolated_glava_dir):
    """Plugin istnieje, ale nie ma atrybutu reset_shader -> ścieżka
    fallback: kopiuje get_template() -> get_live_frag()."""
    class FakePluginNoReset:
        pass  # brak reset_shader

    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: FakePluginNoReset)
    monkeypatch.setattr(tab_module_mod, "glava_restart",
                         lambda module, after_fn=None: None)

    tmpl_path = tab_module_mod.get_template("bars")
    os.makedirs(os.path.dirname(tmpl_path), exist_ok=True)
    with open(tmpl_path, "w") as f:
        f.write("vec3 fallback_template_content;")

    tab._reset_shader()

    live_path = tab_module_mod.get_live_frag("bars")
    assert os.path.exists(live_path)
    with open(live_path) as f:
        assert f.read() == "vec3 fallback_template_content;"


def test_reset_shader_fallback_skips_copy_if_template_missing(
        tab, fake_app, no_dialogs, monkeypatch, isolated_glava_dir):
    """Jeśli szablon nie istnieje, fallback nie crashuje i nie tworzy
    live frag (os.path.exists(tmpl) strzeże copy2)."""
    class FakePluginNoReset:
        pass

    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: FakePluginNoReset)
    monkeypatch.setattr(tab_module_mod, "glava_restart",
                         lambda module, after_fn=None: None)

    tab._reset_shader()  # nie powinno podnieść wyjątku

    live_path = tab_module_mod.get_live_frag("bars")
    assert not os.path.exists(live_path)


# ── _reset_shader — ImportError -> ten sam fallback kopiowania ─────────────

def test_reset_shader_importerror_falls_back_to_template_copy(
        tab, fake_app, no_dialogs, monkeypatch, isolated_glava_dir):
    """Gdy _load_module_plugin podnosi ImportError, _reset_shader powinno
    spaść na identyczny fallback kopiowania szablonu (duplikowana ścieżka
    w kodzie — except ImportError ma swoją własną kopię logiki)."""
    def raise_import_error(name):
        raise ImportError(name)
    monkeypatch.setattr(tab_module_mod, "_load_module_plugin", raise_import_error)
    monkeypatch.setattr(tab_module_mod, "glava_restart",
                         lambda module, after_fn=None: None)

    tmpl_path = tab_module_mod.get_template("bars")
    os.makedirs(os.path.dirname(tmpl_path), exist_ok=True)
    with open(tmpl_path, "w") as f:
        f.write("vec3 importerror_fallback;")

    tab._reset_shader()

    live_path = tab_module_mod.get_live_frag("bars")
    assert os.path.exists(live_path)
    with open(live_path) as f:
        assert f.read() == "vec3 importerror_fallback;"


def test_reset_shader_always_rebuilds_tab_and_shows_info(
        tab, fake_app, no_dialogs, monkeypatch):
    """Niezależnie od ścieżki (plugin/fallback), reset zawsze kończy się
    rebuild_module_tab() + showinfo."""
    class FakePlugin:
        @staticmethod
        def reset_shader(app):
            pass

    monkeypatch.setattr(tab_module_mod, "_load_module_plugin",
                         lambda name: FakePlugin)
    monkeypatch.setattr(tab_module_mod, "glava_restart",
                         lambda module, after_fn=None: None)

    tab._reset_shader()

    assert fake_app.rebuild_calls == 1
    assert len(no_dialogs["showinfo"]) == 1


# ── _build_placeholder ───────────────────────────────────────────────────────
# UWAGA: pomijamy testy "czy ttk.LabelFrame/ttk.Label się tworzy" — to czyste
# GUI-rendering bez logiki (podobnie jak w theme.py). _build_placeholder nie
# ma żadnego rozgałęzienia warte sprawdzenia poza samym renderowaniem widgetów.


# ── build_tab_module (module-level entry point) ─────────────────────────────

def test_build_tab_module_creates_tabmodule_and_calls_build(monkeypatch):
    """build_tab_module tworzy TabModule i woła .build() — sam entry point,
    bez realnego tkinter (build() jest monkeypatchowane)."""
    build_calls = []

    class FakeTabModule:
        def __init__(self, parent, app):
            self.parent = parent
            self.app = app
        def build(self):
            build_calls.append(True)

    monkeypatch.setattr(tab_module_mod, "TabModule", FakeTabModule)
    fake_app = FakeApp()
    tab_module_mod.build_tab_module(parent="PARENT", app=fake_app)
    assert build_calls == [True]
