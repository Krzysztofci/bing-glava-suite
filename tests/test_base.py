import os
import sys
import importlib
import pytest
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import gui.modules.base as base_mod
import gui.core as core_mod


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


class ConcreteWidget(base_mod.BaseParamWidget):
    """Konkretna podklasa minimalna do testowania BaseParamWidget — nie
    nadpisuje build_left/build_right (nie wołamy build() w testach)."""
    MODULE_NAME = "bars"
    SHAPE_PARAMS = [("bar_width", "Width", 1, 20, 4, "px", "tooltip")]


class FakeProfileVar:
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


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_app(tmp_path):
    return FakeApp(tmp_path)


@pytest.fixture
def widget(fake_app):
    return ConcreteWidget(parent=None, app=fake_app, T=fake_app.T)


# ── _get_instance ─────────────────────────────────────────────────────────────

def test_get_instance_returns_app_active_instance_when_no_frozen_instance(
        widget, fake_app):
    assert widget._get_instance() is fake_app.active_instance


def test_get_instance_returns_frozen_instance_when_provided(fake_app, tmp_path):
    frozen = FakeInstance(str(tmp_path), "frozen")
    w = ConcreteWidget(parent=None, app=fake_app, T=fake_app.T, instance=frozen)
    assert w._get_instance() is frozen
    # Nawet jeśli active_instance się zmieni, frozen ma priorytet.
    fake_app.active_instance = FakeInstance(str(tmp_path), "other")
    assert w._get_instance() is frozen


def test_get_instance_returns_none_when_app_has_no_active_instance(fake_app):
    del fake_app.__dict__["active_instance"]

    class BareApp:
        pass
    bare = BareApp()
    w = ConcreteWidget(parent=None, app=bare, T=FakeT())
    assert w._get_instance() is None


# ── Path properties: _module_glsl / _smooth_glsl / _glsl / _tmpl / _frag ────

def test_module_glsl_uses_instance_path_when_available(widget, fake_app):
    assert widget._module_glsl == fake_app.active_instance.module_glsl("bars")


def test_module_glsl_falls_back_to_global_path_when_no_instance(fake_app, tmp_path):
    fake_app.active_instance = None
    w = ConcreteWidget(parent=None, app=fake_app, T=fake_app.T)
    monkeypatch_glava_dir = str(tmp_path)
    import gui.modules.base as b
    orig = b.GLAVA_DIR
    b.GLAVA_DIR = monkeypatch_glava_dir
    try:
        assert w._module_glsl == os.path.join(monkeypatch_glava_dir, "bars.glsl")
    finally:
        b.GLAVA_DIR = orig


def test_smooth_glsl_uses_instance_attribute(widget, fake_app):
    assert widget._smooth_glsl == fake_app.active_instance.smooth_glsl


def test_smooth_glsl_falls_back_to_global_when_no_instance(fake_app):
    fake_app.active_instance = None
    w = ConcreteWidget(parent=None, app=fake_app, T=fake_app.T)
    import gui.modules.base as b
    expected = os.path.join(b.GLAVA_DIR, "smooth_parameters.glsl")
    assert w._smooth_glsl == expected


def test_glsl_property_mirrors_module_glsl(widget, fake_app):
    assert widget._glsl == fake_app.active_instance.module_glsl("bars")


def test_glsl_falls_back_to_global_when_no_instance(fake_app):
    fake_app.active_instance = None
    w = ConcreteWidget(parent=None, app=fake_app, T=fake_app.T)
    import gui.modules.base as b
    expected = os.path.join(b.GLAVA_DIR, "bars.glsl")
    assert w._glsl == expected


def test_tmpl_property_uses_instance_path(widget, fake_app):
    assert widget._tmpl == fake_app.active_instance.module_tmpl("bars")


def test_frag_property_uses_instance_path(widget, fake_app):
    assert widget._frag == fake_app.active_instance.module_frag("bars")


def test_frag_falls_back_to_global_when_no_instance(fake_app):
    fake_app.active_instance = None
    w = ConcreteWidget(parent=None, app=fake_app, T=fake_app.T)
    import gui.modules.base as b
    expected = os.path.join(b.GLAVA_DIR, "bars", "1.frag")
    assert w._frag == expected


def test_tmpl_falls_back_to_global_when_no_instance(fake_app):
    fake_app.active_instance = None
    w = ConcreteWidget(parent=None, app=fake_app, T=fake_app.T)
    import gui.modules.base as b
    expected = os.path.join(b.GLAVA_DIR, "bars_colors.frag")
    assert w._tmpl == expected


# ── _expert ───────────────────────────────────────────────────────────────────

def test_expert_returns_value_from_app_expert_mode(widget, fake_app):
    class FakeBoolVar:
        def get(self):
            return True
    fake_app.expert_mode = FakeBoolVar()
    assert widget._expert() is True


def test_expert_returns_false_when_app_has_no_expert_mode_attribute(widget):
    assert widget._expert() is False


# ── _debounce ─────────────────────────────────────────────────────────────────

def test_debounce_module_target_writes_defines_and_schedules_restart(
        widget, monkeypatch):
    write_calls = []
    monkeypatch.setattr(base_mod.glsl_io, "write_defines",
                         lambda path, values, params: write_calls.append((path, values)))
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    widget._debounce("bar_width", 8, target="module")

    assert write_calls == [(widget._module_glsl, {"bar_width": 8})]
    assert restart_calls == [True]


def test_debounce_module_target_raises_without_shape_params(fake_app):
    class NoShapeParamsWidget(base_mod.BaseParamWidget):
        MODULE_NAME = "bars"
        SHAPE_PARAMS = None
    w = NoShapeParamsWidget(parent=None, app=fake_app, T=fake_app.T)
    with pytest.raises(NotImplementedError):
        w._debounce("bar_width", 8, target="module")


def test_debounce_smooth_target_writes_smooth_params(widget, monkeypatch):
    write_calls = []
    monkeypatch.setattr(base_mod.glsl_io, "write_smooth",
                         lambda path, values, params: write_calls.append((path, values)))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    widget._debounce("setgravitystep", 4.2, target="smooth")

    assert write_calls == [(widget._smooth_glsl, {"setgravitystep": 4.2})]


def test_debounce_rc_target_writes_int_request(widget, monkeypatch, fake_app):
    write_calls = []
    monkeypatch.setattr(base_mod.glsl_io, "write_int_req",
                         lambda path, key, value: write_calls.append((path, key, value)))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)
    assert not hasattr(fake_app, "get_active_rc_glsl")

    widget._debounce("someflag", "3", target="rc")

    assert write_calls == [(core_mod.RC_GLSL, "someflag", 3)]


def test_debounce_rc_target_uses_app_get_active_rc_glsl_when_available(
        widget, monkeypatch, fake_app, tmp_path):
    custom_rc = str(tmp_path / "custom_rc.glsl")
    fake_app.get_active_rc_glsl = lambda: custom_rc
    write_calls = []
    monkeypatch.setattr(base_mod.glsl_io, "write_int_req",
                         lambda path, key, value: write_calls.append(path))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    widget._debounce("someflag", "5", target="rc")

    assert write_calls == [custom_rc]


# ── _schedule_restart ─────────────────────────────────────────────────────────

def test_schedule_restart_uses_restart_active_instance_when_available(
        widget, fake_app):
    restart_calls = []
    fake_app.restart_active_instance = (
        lambda module=None, instance=None, after_fn=None:
        restart_calls.append((module, instance)))

    widget._schedule_restart()

    assert restart_calls == [("bars", fake_app.active_instance)]


def test_schedule_restart_falls_back_to_legacy_glava_restart(
        widget, fake_app, monkeypatch):
    assert not hasattr(fake_app, "restart_active_instance")
    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, extra_flags=None, after_fn=None, instance=None:
                         restart_calls.append((module, instance)))

    widget._schedule_restart()

    assert restart_calls == [("bars", fake_app.active_instance)]


def test_schedule_restart_cancels_previous_pending_job(widget, fake_app):
    widget._rjob = "PREVIOUS_JOB_ID"
    cancel_calls = []
    fake_app.root.after_cancel = lambda job: cancel_calls.append(job)
    fake_app.restart_active_instance = lambda **kw: None

    widget._schedule_restart()

    assert cancel_calls == ["PREVIOUS_JOB_ID"]


def test_schedule_restart_swallows_cancel_errors(widget, fake_app):
    """Jeśli after_cancel rzuci wyjątek (np. job już wykonany), nie
    powinno to crashować _schedule_restart."""
    widget._rjob = "STALE_JOB"
    def broken_cancel(job):
        raise RuntimeError("job already executed")
    fake_app.root.after_cancel = broken_cancel
    fake_app.restart_active_instance = lambda **kw: None

    widget._schedule_restart()  # nie powinno podnieść wyjątku


# ── _save_profile ─────────────────────────────────────────────────────────────

def test_save_profile_does_nothing_if_dialog_cancelled(widget, monkeypatch):
    monkeypatch.setattr(base_mod, "ask_string", lambda *a, **kw: None)
    saved = []
    monkeypatch.setattr(base_mod, "save_shader_profile_for_module",
                         lambda *a, **kw: saved.append(True))
    widget._save_profile()
    assert saved == []


def test_save_profile_skips_overwrite_when_declined(widget, monkeypatch):
    monkeypatch.setattr(base_mod, "ask_string", lambda *a, **kw: "Existing")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module",
                         lambda module: {"Existing": {}})
    monkeypatch.setattr(base_mod.messagebox, "askyesno", lambda *a, **kw: False)
    saved = []
    monkeypatch.setattr(base_mod, "save_shader_profile_for_module",
                         lambda *a, **kw: saved.append(True))
    widget._save_profile()
    assert saved == []


def test_save_profile_overwrites_when_confirmed(widget, monkeypatch, fake_app):
    monkeypatch.setattr(base_mod, "ask_string", lambda *a, **kw: "Existing")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module",
                         lambda module: {"Existing": {"old": 1}})
    monkeypatch.setattr(base_mod.messagebox, "askyesno", lambda *a, **kw: True)

    class FakeModule:
        @staticmethod
        def collect_params(app):
            return {"bar_width": 8}
    monkeypatch.setattr(importlib, "import_module", lambda name: FakeModule)

    saved = []
    monkeypatch.setattr(base_mod, "save_shader_profile_for_module",
                         lambda module, name, params: saved.append((module, name, params)))
    widget.profile_var = FakeProfileVar()
    monkeypatch.setattr(widget, "_refresh_cb", lambda: None)

    widget._save_profile()

    assert saved == [("bars", "Existing", {"bar_width": 8})]
    assert widget.profile_var.get() == "Existing"


def test_save_profile_new_name_saves_without_overwrite_prompt(
        widget, monkeypatch, fake_app):
    monkeypatch.setattr(base_mod, "ask_string", lambda *a, **kw: "BrandNew")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module",
                         lambda module: {})
    askyesno_calls = []
    monkeypatch.setattr(base_mod.messagebox, "askyesno",
                         lambda *a, **kw: askyesno_calls.append(True) or True)

    class FakeModule:
        @staticmethod
        def collect_params(app):
            return {"bar_width": 8}
    monkeypatch.setattr(importlib, "import_module", lambda name: FakeModule)

    saved = []
    monkeypatch.setattr(base_mod, "save_shader_profile_for_module",
                         lambda module, name, params: saved.append((module, name, params)))
    widget.profile_var = FakeProfileVar()
    monkeypatch.setattr(widget, "_refresh_cb", lambda: None)

    widget._save_profile()

    assert askyesno_calls == []  # brak prompt overwrite dla nowej nazwy
    assert saved == [("bars", "BrandNew", {"bar_width": 8})]


def test_save_profile_swaps_active_instance_during_collect_and_restores_after(
        widget, monkeypatch, fake_app, tmp_path):
    """collect_params(app) czyta app.active_instance — _save_profile musi
    tymczasowo podstawić zamrożoną instancję (z _get_instance()), a potem
    przywrócić oryginalną, NIEZALEŻNIE od wyniku (try/finally)."""
    frozen = FakeInstance(str(tmp_path), "frozen")
    w = ConcreteWidget(parent=None, app=fake_app, T=fake_app.T, instance=frozen)
    w.profile_var = FakeProfileVar()
    monkeypatch.setattr(w, "_refresh_cb", lambda: None)

    monkeypatch.setattr(base_mod, "ask_string", lambda *a, **kw: "Name")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module", lambda module: {})
    monkeypatch.setattr(base_mod, "save_shader_profile_for_module", lambda *a, **kw: None)

    seen_active_instance = []
    class FakeModule:
        @staticmethod
        def collect_params(app):
            seen_active_instance.append(app.active_instance)
            return {}
    monkeypatch.setattr(importlib, "import_module", lambda name: FakeModule)

    original_active = fake_app.active_instance
    w._save_profile()

    assert seen_active_instance == [frozen]
    assert fake_app.active_instance is original_active  # przywrócone


def test_save_profile_restores_active_instance_even_if_collect_params_raises(
        widget, monkeypatch, fake_app, tmp_path):
    frozen = FakeInstance(str(tmp_path), "frozen")
    w = ConcreteWidget(parent=None, app=fake_app, T=fake_app.T, instance=frozen)

    monkeypatch.setattr(base_mod, "ask_string", lambda *a, **kw: "Name")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module", lambda module: {})

    class BrokenModule:
        @staticmethod
        def collect_params(app):
            raise RuntimeError("boom")
    monkeypatch.setattr(importlib, "import_module", lambda name: BrokenModule)

    original_active = fake_app.active_instance
    with pytest.raises(RuntimeError):
        w._save_profile()

    assert fake_app.active_instance is original_active  # przywrócone mimo wyjątku


# ── _apply_profile ────────────────────────────────────────────────────────────

def test_apply_profile_does_nothing_if_name_empty(widget, monkeypatch):
    widget.profile_var = FakeProfileVar("")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module",
                         lambda module: {"X": {}})
    applied = []
    monkeypatch.setattr(importlib, "import_module",
                         lambda name: type("M", (), {
                             "apply_params": staticmethod(
                                 lambda p, app: applied.append(True))})())
    widget._apply_profile()
    assert applied == []


def test_apply_profile_does_nothing_if_name_not_in_profiles(widget, monkeypatch):
    widget.profile_var = FakeProfileVar("Missing")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module",
                         lambda module: {"Other": {}})
    applied = []
    monkeypatch.setattr(importlib, "import_module",
                         lambda name: type("M", (), {
                             "apply_params": staticmethod(
                                 lambda p, app: applied.append(True))})())
    widget._apply_profile()
    assert applied == []


def test_apply_profile_applies_params_rebuilds_and_uses_restart_active_instance(
        widget, monkeypatch, fake_app):
    widget.profile_var = FakeProfileVar("Existing")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module",
                         lambda module: {"Existing": {"bar_width": 8}})

    applied_calls = []
    class FakeModule:
        @staticmethod
        def apply_params(params, app):
            applied_calls.append((params, app.active_instance))
    monkeypatch.setattr(importlib, "import_module", lambda name: FakeModule)

    restart_calls = []
    fake_app.restart_active_instance = (
        lambda module=None, instance=None, after_fn=None:
        restart_calls.append((module, instance)))

    original_active = fake_app.active_instance
    widget._apply_profile()

    assert applied_calls == [({"bar_width": 8}, fake_app.active_instance)]
    assert fake_app.rebuild_calls == 1
    assert restart_calls == [("bars", fake_app.active_instance)]
    assert fake_app.active_instance is original_active  # przywrócone po zastosowaniu


def test_apply_profile_falls_back_to_legacy_glava_restart(
        widget, monkeypatch, fake_app):
    assert not hasattr(fake_app, "restart_active_instance")
    widget.profile_var = FakeProfileVar("Existing")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module",
                         lambda module: {"Existing": {"bar_width": 8}})

    class FakeModule:
        @staticmethod
        def apply_params(params, app):
            pass
    monkeypatch.setattr(importlib, "import_module", lambda name: FakeModule)

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, extra_flags=None, after_fn=None, instance=None:
                         restart_calls.append((module, instance)))

    widget._apply_profile()

    assert fake_app.rebuild_calls == 1
    assert restart_calls == [("bars", fake_app.active_instance)]


def test_apply_profile_uses_app_extra_flags_for_legacy_restart(
        widget, monkeypatch, fake_app):
    """Legacy fallback przekazuje app.extra_flags jako extra_flags do glava_restart."""
    assert not hasattr(fake_app, "restart_active_instance")
    fake_app.extra_flags = "--custom-flag"
    widget.profile_var = FakeProfileVar("Existing")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module",
                         lambda module: {"Existing": {}})

    class FakeModule:
        @staticmethod
        def apply_params(params, app):
            pass
    monkeypatch.setattr(importlib, "import_module", lambda name: FakeModule)

    import gui.glava as glava_mod
    flags_seen = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, extra_flags=None, after_fn=None, instance=None:
                         flags_seen.append(extra_flags))

    widget._apply_profile()

    assert flags_seen == ["--custom-flag"]


def test_apply_profile_swaps_active_instance_during_apply_and_restores_after(
        widget, monkeypatch, fake_app, tmp_path):
    """apply_params(params, app) czyta/pisze app.active_instance —
    _apply_profile musi tymczasowo podstawić zamrożoną instancję
    (z _get_instance()), a potem przywrócić oryginalną, NIEZALEŻNIE od wyniku
    (try/finally) — analogicznie do _save_profile."""
    frozen = FakeInstance(str(tmp_path), "frozen")
    w = ConcreteWidget(parent=None, app=fake_app, T=fake_app.T, instance=frozen)
    w.profile_var = FakeProfileVar("Existing")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module",
                         lambda module: {"Existing": {}})
    fake_app.restart_active_instance = lambda **kw: None

    seen_active_instance = []
    class FakeModule:
        @staticmethod
        def apply_params(params, app):
            seen_active_instance.append(app.active_instance)
    monkeypatch.setattr(importlib, "import_module", lambda name: FakeModule)

    original_active = fake_app.active_instance
    w._apply_profile()

    assert seen_active_instance == [frozen]
    assert fake_app.active_instance is original_active


def test_apply_profile_restores_active_instance_even_if_apply_params_raises(
        widget, monkeypatch, fake_app, tmp_path):
    frozen = FakeInstance(str(tmp_path), "frozen")
    w = ConcreteWidget(parent=None, app=fake_app, T=fake_app.T, instance=frozen)
    w.profile_var = FakeProfileVar("Existing")
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module",
                         lambda module: {"Existing": {}})

    class BrokenModule:
        @staticmethod
        def apply_params(params, app):
            raise RuntimeError("boom")
    monkeypatch.setattr(importlib, "import_module", lambda name: BrokenModule)

    original_active = fake_app.active_instance
    with pytest.raises(RuntimeError):
        w._apply_profile()

    assert fake_app.active_instance is original_active  # przywrócone mimo wyjątku


# ── _delete_profile ───────────────────────────────────────────────────────────

def test_delete_profile_does_nothing_if_name_empty(widget, monkeypatch):
    widget.profile_var = FakeProfileVar("")
    deleted = []
    monkeypatch.setattr(base_mod, "delete_shader_profile_for_module",
                         lambda *a, **kw: deleted.append(True))
    widget._delete_profile()
    assert deleted == []


def test_delete_profile_skips_when_declined(widget, monkeypatch):
    widget.profile_var = FakeProfileVar("ToDelete")
    monkeypatch.setattr(base_mod.messagebox, "askyesno", lambda *a, **kw: False)
    deleted = []
    monkeypatch.setattr(base_mod, "delete_shader_profile_for_module",
                         lambda *a, **kw: deleted.append(True))
    widget._delete_profile()
    assert deleted == []


def test_delete_profile_deletes_and_refreshes_when_confirmed(widget, monkeypatch):
    widget.profile_var = FakeProfileVar("ToDelete")
    monkeypatch.setattr(base_mod.messagebox, "askyesno", lambda *a, **kw: True)
    deleted = []
    monkeypatch.setattr(base_mod, "delete_shader_profile_for_module",
                         lambda module, name: deleted.append((module, name)))
    refreshed = []
    monkeypatch.setattr(widget, "_refresh_cb", lambda: refreshed.append(True))

    widget._delete_profile()

    assert deleted == [("bars", "ToDelete")]
    assert refreshed == [True]


# ── _refresh_cb ───────────────────────────────────────────────────────────────

def test_refresh_cb_sets_sorted_names_and_selects_first(widget, monkeypatch):
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module",
                         lambda module: {"Zebra": {}, "Apple": {}})
    widget.profile_cb = FakeCombobox()
    widget._refresh_cb()
    assert widget.profile_cb["values"] == ["Apple", "Zebra"]
    assert widget.profile_cb._current_idx == 0


def test_refresh_cb_empty_does_not_set_current(widget, monkeypatch):
    monkeypatch.setattr(base_mod, "get_shader_profiles_for_module", lambda module: {})
    widget.profile_cb = FakeCombobox()
    widget._refresh_cb()
    assert widget.profile_cb["values"] == []
    assert widget.profile_cb._current_idx is None


# ── build() — dispatch do build_left/build_right ────────────────────────────

def test_build_raises_notimplementederror_for_unoverridden_build_left(
        fake_app, monkeypatch):
    """Klasa bazowa (bez nadpisania build_left/build_right) musi rzucić
    NotImplementedError — to kontrakt podklas."""
    monkeypatch.setattr(importlib, "import_module",
                         lambda name: type("FakeMod", (), {
                             "collect_params": staticmethod(lambda app: {})})())

    root = tk.Tk()
    root.withdraw()
    try:
        frame = tk.Frame(root)
        w = ConcreteWidget(parent=frame, app=fake_app, T=fake_app.T)
        with pytest.raises(NotImplementedError):
            w.build()
    finally:
        root.destroy()


# ── _close_detached ───────────────────────────────────────────────────────────

def test_close_detached_destroys_window_deiconifies_root_and_rebuilds(
        fake_app):
    destroy_calls = []
    deiconify_calls = []
    lift_calls = []

    class FakeToplevel:
        def destroy(self):
            destroy_calls.append(True)

    fake_app.root.deiconify = lambda: deiconify_calls.append(True)
    fake_app.root.lift = lambda: lift_calls.append(True)
    rebuild_calls = []

    base_mod._close_detached(FakeToplevel(), fake_app,
                             rebuild_fn=lambda: rebuild_calls.append(True))

    assert destroy_calls == [True]
    assert deiconify_calls == [True]
    assert lift_calls == [True]
    assert rebuild_calls == [True]


def test_close_detached_swallows_destroy_errors(fake_app):
    class BrokenToplevel:
        def destroy(self):
            raise RuntimeError("already destroyed")

    fake_app.root.deiconify = lambda: None
    fake_app.root.lift = lambda: None

    base_mod._close_detached(BrokenToplevel(), fake_app)  # nie powinno crashować


def test_close_detached_swallows_root_deiconify_errors(fake_app):
    class FakeToplevel:
        def destroy(self):
            pass

    def broken_deiconify():
        raise RuntimeError("root destroyed")
    fake_app.root.deiconify = broken_deiconify

    base_mod._close_detached(FakeToplevel(), fake_app)  # nie powinno crashować


def test_close_detached_swallows_rebuild_fn_errors(fake_app):
    class FakeToplevel:
        def destroy(self):
            pass

    fake_app.root.deiconify = lambda: None
    fake_app.root.lift = lambda: None

    def broken_rebuild():
        raise RuntimeError("rebuild failed")

    base_mod._close_detached(FakeToplevel(), fake_app, rebuild_fn=broken_rebuild)


def test_close_detached_no_rebuild_fn_is_noop(fake_app):
    class FakeToplevel:
        def destroy(self):
            pass

    fake_app.root.deiconify = lambda: None
    fake_app.root.lift = lambda: None

    base_mod._close_detached(FakeToplevel(), fake_app, rebuild_fn=None)
