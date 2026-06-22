import importlib.util
import os
import sys
import threading

import pytest

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


def _make_gui(gg):
    """Tworzy GlavaGUI bez wołania __init__ (które buduje całe okno Tk)."""
    return gg.GlavaGUI.__new__(gg.GlavaGUI)


class _FakeVar:
    def __init__(self, value):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class _FakeRoot:
    def after(self, delay, fn, *args):
        fn(*args)
        return "after#0"

    def after_cancel(self, jid):
        pass


class _SyncThread:
    """Podstawia threading.Thread — wykonuje target() SYNCHRONICZNIE w tym
    samym wątku, zamiast w prawdziwym tle. Eliminuje niedeterminizm timing
    w testach, a wciąż wykonuje prawdziwą logikę closure'a (_stop_and_clear
    w _on_inst_close). 'import threading' w kodzie produkcyjnym to wciąż
    ten sam moduł z sys.modules, więc patchowanie threading.Thread tutaj
    działa niezależnie od tego gdzie 'import threading' się wykonał."""
    def __init__(self, target=None, daemon=None, args=(), kwargs=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class _FakeInstBar:
    def __init__(self):
        self.add_tab_calls = []
        self.removed = []
        self._tabs = {}

    def add_tab(self, iid, module=None, label=None, select=None):
        self.add_tab_calls.append((iid, module, label, select))
        self._tabs[iid] = {"label": label or f"auto-label-{iid}"}

    def remove_tab(self, iid):
        self.removed.append(iid)


# =============================================================================
# UWAGA BEZPIECZEŃSTWA przy mockowaniu w tym pliku:
#
# _load_saved_instances robi LOKALNY import:
#     from gui.instance import load_instances
# więc to musi być patchowane na gui.instance, NIE na gg.
#
# _on_inst_add i _on_inst_close NIE re-importują lokalnie swoich zależności
# (next_inst_id, GlavaInstance, register_instance, update_instance,
# unregister_instance, glava_restart_instance, glava_stop_instance,
# clear_pid, read_active_module) — wszystkie pochodzą z top-level importów
# na początku glava-gui.py, więc patchujemy je na gg, nie na gui.glava/
# gui.instance/gui.core. To DOKŁADNA ODWROTNOŚĆ wzorca z _on_glava_toggle
# (który lokalnie re-importuje glava_restart_instance/glava_stop_instance).
# Sprawdzaj to za każdym razem dla nowej metody — to jest źródło
# pierwotnego incydentu z bars.py.
# =============================================================================


# ── _load_saved_instances ────────────────────────────────────────────────────

def test_load_saved_instances_skips_nonexistent_directories(gg, monkeypatch):
    app = _make_gui(gg)
    app.instances     = {}
    app.processes     = {}
    app._inst_modules = {}

    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "load_instances",
                         lambda: [{"inst_id": 0, "module": "bars"}])

    class _FakeInst:
        def __init__(self, iid):
            self.inst_id = iid
            self.rc_glsl = f"/tmp/inst{iid}/rc.glsl"

        def exists(self):
            return False  # katalog "nie istnieje" -> pomiń

    monkeypatch.setattr(gg, "GlavaInstance", _FakeInst)

    app._load_saved_instances()

    assert app.instances == {}
    assert app.processes == {}


def test_load_saved_instances_registers_existing_instance(gg, monkeypatch):
    app = _make_gui(gg)
    app.instances     = {}
    app.processes     = {}
    app._inst_modules = {}

    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "load_instances",
                         lambda: [{"inst_id": 0, "module": "wave"}])

    class _FakeInst:
        def __init__(self, iid):
            self.inst_id = iid
            self.rc_glsl = f"/tmp/inst{iid}/rc.glsl"

        def exists(self):
            return True

    monkeypatch.setattr(gg, "GlavaInstance", _FakeInst)
    monkeypatch.setattr(gg, "read_rc_module", lambda rc_path: None)  # brak w rc.glsl
    monkeypatch.setattr(gg, "adopt_instance", lambda iid: (None, None))

    app._load_saved_instances()

    assert 0 in app.instances
    assert app._inst_modules[0] == "wave"  # fallback na wartość z JSON
    assert app.processes[0] is None


def test_load_saved_instances_prefers_rc_module_over_json(gg, monkeypatch):
    app = _make_gui(gg)
    app.instances     = {}
    app.processes     = {}
    app._inst_modules = {}

    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "load_instances",
                         lambda: [{"inst_id": 0, "module": "wave"}])

    class _FakeInst:
        def __init__(self, iid):
            self.inst_id = iid
            self.rc_glsl = "/tmp/rc.glsl"

        def exists(self):
            return True

    monkeypatch.setattr(gg, "GlavaInstance", _FakeInst)
    monkeypatch.setattr(gg, "read_rc_module", lambda rc_path: "circle")  # rc.glsl ma priorytet
    monkeypatch.setattr(gg, "adopt_instance", lambda iid: (None, None))

    app._load_saved_instances()

    assert app._inst_modules[0] == "circle"


def test_load_saved_instances_adopts_running_process(gg, monkeypatch):
    app = _make_gui(gg)
    app.instances     = {}
    app.processes     = {}
    app._inst_modules = {}

    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "load_instances",
                         lambda: [{"inst_id": 0, "module": "bars"}])

    class _FakeInst:
        def __init__(self, iid):
            self.inst_id = iid
            self.rc_glsl = "/tmp/rc.glsl"

        def exists(self):
            return True

    fake_proc = object()
    monkeypatch.setattr(gg, "GlavaInstance", _FakeInst)
    monkeypatch.setattr(gg, "read_rc_module", lambda rc_path: None)
    monkeypatch.setattr(gg, "adopt_instance", lambda iid: (12345, fake_proc))

    app._load_saved_instances()

    assert app.processes[0] is fake_proc


# ── _on_inst_add ──────────────────────────────────────────────────────────────

def test_on_inst_add_registers_and_builds_without_starting(gg, monkeypatch):
    app = _make_gui(gg)
    app.instances     = {}
    app.processes     = {}
    app._inst_modules = {}
    app.inst_bar       = _FakeInstBar()
    build_calls = []
    app._build_inst_frame = lambda iid: build_calls.append(iid)

    monkeypatch.setattr(gg, "next_inst_id", lambda: 7)

    class _FakeInst:
        def __init__(self, iid):
            self.inst_id = iid
            self.created_with_source = "NOT_CALLED"

        def create(self, source=None):
            self.created_with_source = source

    monkeypatch.setattr(gg, "GlavaInstance", _FakeInst)

    register_calls = []
    monkeypatch.setattr(gg, "register_instance",
                         lambda iid, module=None: register_calls.append((iid, module)))
    update_calls = []
    monkeypatch.setattr(gg, "update_instance",
                         lambda iid, **kw: update_calls.append((iid, kw)))
    restart_calls = []
    monkeypatch.setattr(gg, "glava_restart_instance",
                         lambda **kw: restart_calls.append(kw))

    iid = app._on_inst_add("bars", start=False)

    assert iid == 7
    assert 7 in app.instances
    assert app.processes[7] is None
    assert app._inst_modules[7] == "bars"
    assert build_calls == [7]
    assert register_calls == [(7, "bars")]
    assert restart_calls == []  # start=False -> brak restartu


def test_on_inst_add_starts_glava_when_start_true(gg, monkeypatch, tmp_path):
    app = _make_gui(gg)
    app.instances     = {}
    app.processes     = {}
    app._inst_modules = {}
    app.inst_bar = _FakeInstBar()
    app._build_inst_frame = lambda iid: None
    app.root = _FakeRoot()
    status_calls = []
    app.update_status = lambda: status_calls.append(True)

    monkeypatch.setattr(gg, "next_inst_id", lambda: 3)

    class _FakeInst:
        def __init__(self, iid):
            self.inst_id = iid

        def create(self, source=None):
            pass

    monkeypatch.setattr(gg, "GlavaInstance", _FakeInst)
    monkeypatch.setattr(gg, "register_instance", lambda iid, module=None: None)
    monkeypatch.setattr(gg, "update_instance", lambda iid, **kw: None)

    import gui.core as core_mod
    monkeypatch.setattr(core_mod, "GLAVA_DISABLE_FLAG", str(tmp_path / "disabled"))

    fake_proc = object()
    restart_calls = []

    def mock_restart(instance, module, proc, after_fn):
        restart_calls.append((instance, module))
        after_fn(fake_proc)

    monkeypatch.setattr(gg, "glava_restart_instance", mock_restart)

    iid = app._on_inst_add("wave", start=True)

    assert len(restart_calls) == 1
    assert app.processes[iid] is fake_proc
    assert status_calls == [True]


def test_on_inst_add_removes_disable_flag_when_starting(gg, monkeypatch, tmp_path):
    app = _make_gui(gg)
    app.instances     = {}
    app.processes     = {}
    app._inst_modules = {}
    app.inst_bar = _FakeInstBar()
    app._build_inst_frame = lambda iid: None
    app.root = _FakeRoot()
    app.update_status = lambda: None
    app.glava_enabled_var = _FakeVar(False)

    monkeypatch.setattr(gg, "next_inst_id", lambda: 1)

    class _FakeInst:
        def __init__(self, iid):
            self.inst_id = iid

        def create(self, source=None):
            pass

    monkeypatch.setattr(gg, "GlavaInstance", _FakeInst)
    monkeypatch.setattr(gg, "register_instance", lambda iid, module=None: None)
    monkeypatch.setattr(gg, "update_instance", lambda iid, **kw: None)
    monkeypatch.setattr(gg, "glava_restart_instance", lambda **kw: None)

    flag_path = tmp_path / "disabled"
    flag_path.write_text("")
    import gui.core as core_mod
    monkeypatch.setattr(core_mod, "GLAVA_DISABLE_FLAG", str(flag_path))

    app._on_inst_add("bars", start=True)

    assert not flag_path.exists()
    assert app.glava_enabled_var.get() is True


def test_on_inst_add_syncs_actual_label_to_registry(gg, monkeypatch):
    app = _make_gui(gg)
    app.instances     = {}
    app.processes     = {}
    app._inst_modules = {}
    app.inst_bar = _FakeInstBar()  # add_tab zapisuje auto-label do _tabs
    app._build_inst_frame = lambda iid: None

    monkeypatch.setattr(gg, "next_inst_id", lambda: 5)

    class _FakeInst:
        def __init__(self, iid):
            self.inst_id = iid

        def create(self, source=None):
            pass

    monkeypatch.setattr(gg, "GlavaInstance", _FakeInst)
    monkeypatch.setattr(gg, "register_instance", lambda iid, module=None: None)
    monkeypatch.setattr(gg, "glava_restart_instance", lambda **kw: None)

    update_calls = []
    monkeypatch.setattr(gg, "update_instance",
                         lambda iid, **kw: update_calls.append((iid, kw)))

    app._on_inst_add("bars", start=False)

    assert update_calls == [(5, {"name": "auto-label-5"})]


def test_on_inst_add_swallows_update_instance_exception(gg, monkeypatch):
    """Synchronizacja etykiety do rejestru ma broad except Exception: pass —
    błąd np. uszkodzonego instances.json nie powinien crashować dodawania
    nowej instancji."""
    app = _make_gui(gg)
    app.instances     = {}
    app.processes     = {}
    app._inst_modules = {}
    app.inst_bar = _FakeInstBar()
    app._build_inst_frame = lambda iid: None

    monkeypatch.setattr(gg, "next_inst_id", lambda: 9)

    class _FakeInst:
        def __init__(self, iid):
            self.inst_id = iid

        def create(self, source=None):
            pass

    monkeypatch.setattr(gg, "GlavaInstance", _FakeInst)
    monkeypatch.setattr(gg, "register_instance", lambda iid, module=None: None)
    monkeypatch.setattr(gg, "glava_restart_instance", lambda **kw: None)
    monkeypatch.setattr(gg, "update_instance",
                         lambda iid, **kw: (_ for _ in ()).throw(OSError("fail")))

    iid = app._on_inst_add("bars", start=False)  # nie powinno podnieść wyjątku

    assert iid == 9


# ── _on_inst_close ────────────────────────────────────────────────────────────

def test_on_inst_close_stops_process_and_unregisters(gg, monkeypatch):
    monkeypatch.setattr(threading, "Thread", _SyncThread)

    app = _make_gui(gg)
    fake_proc = object()
    app.processes     = {0: fake_proc}
    app.instances     = {0: object()}
    app._inst_modules = {0: "bars"}
    app.inst_bar = _FakeInstBar()
    app._active_inst_id = 1  # nie ta zamykana -> bez przełączania aktywnej
    status_calls = []
    app.update_status = lambda: status_calls.append(True)

    stop_calls = []
    monkeypatch.setattr(gg, "glava_stop_instance", lambda proc: stop_calls.append(proc))
    clear_calls = []
    monkeypatch.setattr(gg, "clear_pid", lambda iid: clear_calls.append(iid))
    unregister_calls = []
    monkeypatch.setattr(gg, "unregister_instance",
                         lambda iid: unregister_calls.append(iid))

    app._on_inst_close(0)

    assert stop_calls == [fake_proc]
    assert clear_calls == [0]
    assert app.inst_bar.removed == [0]
    assert 0 not in app.instances
    assert unregister_calls == [0]
    assert status_calls == [True]


def test_on_inst_close_destroys_instance(gg, monkeypatch):
    monkeypatch.setattr(threading, "Thread", _SyncThread)

    app = _make_gui(gg)
    app.processes = {0: None}
    destroy_calls = []

    class _FakeInst:
        def destroy(self):
            destroy_calls.append(True)

    app.instances     = {0: _FakeInst()}
    app._inst_modules = {0: "bars"}
    app.inst_bar = _FakeInstBar()
    app._active_inst_id = None
    app.update_status = lambda: None

    monkeypatch.setattr(gg, "glava_stop_instance", lambda proc: None)
    monkeypatch.setattr(gg, "clear_pid", lambda iid: None)
    monkeypatch.setattr(gg, "unregister_instance", lambda iid: None)

    app._on_inst_close(0)

    assert destroy_calls == [True]


def test_on_inst_close_switches_active_instance_when_closing_active(gg, monkeypatch):
    monkeypatch.setattr(threading, "Thread", _SyncThread)

    app = _make_gui(gg)
    inst1 = object()
    app.processes     = {0: None, 1: None}
    app.instances     = {0: object(), 1: inst1}
    app._inst_modules = {0: "bars", 1: "wave"}
    app.inst_bar = _FakeInstBar()
    app._active_inst_id = 0  # zamykamy AKTYWNĄ
    app.update_status = lambda: None

    monkeypatch.setattr(gg, "glava_stop_instance", lambda proc: None)
    monkeypatch.setattr(gg, "clear_pid", lambda iid: None)
    monkeypatch.setattr(gg, "unregister_instance", lambda iid: None)
    monkeypatch.setattr(gg, "read_active_module", lambda: "bars")

    app._on_inst_close(0)

    assert app._active_inst_id == 1
    assert app.active_instance is inst1
    assert app.active_module == "wave"


def test_on_inst_close_sets_none_when_no_instances_remain(gg, monkeypatch):
    monkeypatch.setattr(threading, "Thread", _SyncThread)

    app = _make_gui(gg)
    app.processes     = {0: None}
    app.instances     = {0: object()}
    app._inst_modules = {0: "bars"}
    app.inst_bar = _FakeInstBar()
    app._active_inst_id = 0
    app.update_status = lambda: None

    monkeypatch.setattr(gg, "glava_stop_instance", lambda proc: None)
    monkeypatch.setattr(gg, "clear_pid", lambda iid: None)
    monkeypatch.setattr(gg, "unregister_instance", lambda iid: None)

    app._on_inst_close(0)

    assert app._active_inst_id is None
    assert app.active_instance is None
    assert app.active_module is None


def test_on_inst_close_resets_restart_flags_for_closed_instance(gg, monkeypatch):
    monkeypatch.setattr(threading, "Thread", _SyncThread)

    app = _make_gui(gg)
    app.processes     = {0: None}
    app.instances     = {0: object()}
    app._inst_modules = {0: "bars"}
    app.inst_bar = _FakeInstBar()
    app._active_inst_id = 1
    app.update_status = lambda: None
    app._restart_in_progress = {0: True, 1: False}
    app._restart_pending     = {0: ("bars", None, None)}
    app._restart_after       = {0: "after#1"}

    monkeypatch.setattr(gg, "glava_stop_instance", lambda proc: None)
    monkeypatch.setattr(gg, "clear_pid", lambda iid: None)
    monkeypatch.setattr(gg, "unregister_instance", lambda iid: None)

    app._on_inst_close(0)

    assert 0 not in app._restart_in_progress
    assert 0 not in app._restart_pending
    assert 0 not in app._restart_after


def test_on_inst_close_handles_unregister_exception(gg, monkeypatch):
    """unregister_instance może podnieść wyjątek (np. uszkodzony JSON) —
    metoda ma broad except Exception: pass, nie powinno crashować."""
    monkeypatch.setattr(threading, "Thread", _SyncThread)

    app = _make_gui(gg)
    app.processes     = {0: None}
    app.instances     = {0: object()}
    app._inst_modules = {0: "bars"}
    app.inst_bar = _FakeInstBar()
    app._active_inst_id = 1
    app.update_status = lambda: None

    monkeypatch.setattr(gg, "glava_stop_instance", lambda proc: None)
    monkeypatch.setattr(gg, "clear_pid", lambda iid: None)
    monkeypatch.setattr(gg, "unregister_instance",
                         lambda iid: (_ for _ in ()).throw(OSError("fail")))

    app._on_inst_close(0)  # nie powinno podnieść wyjątku
