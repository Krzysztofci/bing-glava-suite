import importlib.util
import os
import sys

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
    """Wykonuje after(delay, fn) synchronicznie — konsystentne z innymi
    plikami testowymi w tym repo (test_bars.py, test_circle.py, itd.)."""
    def after(self, delay, fn, *args):
        fn(*args)
        return "after#0"

    def after_cancel(self, jid):
        pass


# =============================================================================
# UWAGA BEZPIECZEŃSTWA — przeczytaj przed dodawaniem nowych testów tutaj:
#
# _on_glava_toggle robi LOKALNY import:
#     from gui.glava import glava_restart_instance, glava_stop_instance
# wewnątrz ciała metody. To znaczy że NIE wystarczy mockować
# gg.glava_restart_instance (top-level import z linii 44-52 glava-gui.py) —
# trzeba patchować bezpośrednio gui.glava (źródłowy moduł), bo lokalny
# import zawsze pobiera świeżą referencję z gui.glava w momencie wywołania.
# To dokładnie ta sama pułapka, która spowodowała wyciek procesu glava
# w tests/test_bars.py (patrz historia commitów).
#
# clear_pid NIE jest lokalnie re-importowane w tej metodzie — używa
# referencji związanej w gg (top-level import). Mockujemy więc OBA miejsca
# (gg.clear_pid i gui.glava.clear_pid) dla bezpieczeństwa, niezależnie od
# tego które faktycznie zostanie użyte.
# =============================================================================


# ── Blokada przed wielokrotnym kliknięciem ───────────────────────────────────

def test_on_glava_toggle_ignores_when_already_in_progress(gg, monkeypatch):
    app = _make_gui(gg)
    app._toggle_in_progress = True
    app.glava_enabled_var = _FakeVar(True)

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart_instance",
                         lambda **kw: restart_calls.append(kw))

    app._on_glava_toggle()

    assert restart_calls == []
    assert app._toggle_in_progress is True  # niezmienione


# ── Włączanie (enabled=True) — restart wszystkich instancji ─────────────────

def test_on_glava_toggle_enables_all_instances(gg, monkeypatch, tmp_path):
    app = _make_gui(gg)
    app.glava_enabled_var = _FakeVar(True)
    app._inst_modules = {0: "bars", 1: "wave"}
    app.active_module = "bars"
    app.instances = {0: object(), 1: object()}
    app.processes = {0: None, 1: None}
    app.root = _FakeRoot()
    status_calls = []
    app.update_status = lambda: status_calls.append(True)

    import gui.core as core_mod
    monkeypatch.setattr(core_mod, "GLAVA_DISABLE_FLAG", str(tmp_path / "disabled"))

    import gui.glava as glava_mod
    restart_calls = []

    def mock_restart(instance, module, proc, after_fn):
        fake_proc = object()
        restart_calls.append((instance, module))
        after_fn(fake_proc)

    monkeypatch.setattr(glava_mod, "glava_restart_instance", mock_restart)

    app._on_glava_toggle()

    assert len(restart_calls) == 2
    assert set(app.processes.keys()) == {0, 1}
    assert all(p is not None for p in app.processes.values())
    assert app._toggle_in_progress is False
    assert len(status_calls) == 2  # update_status raz na zakończoną instancję


def test_on_glava_toggle_enable_removes_disable_flag(gg, monkeypatch, tmp_path):
    app = _make_gui(gg)
    app.glava_enabled_var = _FakeVar(True)
    app._inst_modules = {}
    app.active_module = "bars"
    app.instances = {}
    app.processes = {}
    app.root = _FakeRoot()
    app.update_status = lambda: None

    flag_path = tmp_path / "disabled"
    flag_path.write_text("")
    import gui.core as core_mod
    monkeypatch.setattr(core_mod, "GLAVA_DISABLE_FLAG", str(flag_path))

    import gui.glava as glava_mod
    monkeypatch.setattr(glava_mod, "glava_restart_instance", lambda **kw: None)

    assert flag_path.exists()
    app._on_glava_toggle()
    assert not flag_path.exists()


# ── Wyłączanie (enabled=False) — stop wszystkich instancji ───────────────────

def test_on_glava_toggle_disables_all_instances(gg, monkeypatch, tmp_path):
    app = _make_gui(gg)
    app.glava_enabled_var = _FakeVar(False)
    app.processes = {0: object(), 1: object()}
    app.root = _FakeRoot()
    app.update_status = lambda: None

    flag_path = str(tmp_path / "disabled")
    import gui.core as core_mod
    monkeypatch.setattr(core_mod, "GLAVA_DISABLE_FLAG", flag_path)

    import gui.glava as glava_mod
    stop_calls = []
    monkeypatch.setattr(glava_mod, "glava_stop_instance",
                         lambda proc: stop_calls.append(proc))
    clear_calls = []
    monkeypatch.setattr(gg, "clear_pid", lambda iid: clear_calls.append(iid))
    monkeypatch.setattr(glava_mod, "clear_pid", lambda iid: clear_calls.append(iid))

    app._on_glava_toggle()

    assert os.path.exists(flag_path)
    assert len(stop_calls) == 2
    assert sorted(clear_calls) == [0, 1]
    assert app.processes == {}
    assert app._toggle_in_progress is False


def test_on_glava_toggle_disable_creates_parent_dir(gg, monkeypatch, tmp_path):
    """GLAVA_DISABLE_FLAG może być w katalogu który jeszcze nie istnieje."""
    app = _make_gui(gg)
    app.glava_enabled_var = _FakeVar(False)
    app.processes = {}
    app.root = _FakeRoot()
    app.update_status = lambda: None

    flag_path = str(tmp_path / "nested" / "does_not_exist_yet" / "disabled")
    import gui.core as core_mod
    monkeypatch.setattr(core_mod, "GLAVA_DISABLE_FLAG", flag_path)

    app._on_glava_toggle()

    assert os.path.exists(flag_path)


# ── Wyścig: toggle OFF zdąży wystrzelić ZANIM after_fn z restartu wróci ──────

def test_on_glava_toggle_after_fn_stops_proc_if_disabled_during_restart(
        gg, monkeypatch, tmp_path):
    """To jest dokładnie scenariusz opisany w komentarzu kodu: jeśli
    użytkownik wyłączy toggle PODCZAS trwania restartu, after_fn nie
    powinien zarejestrować nowego procesu — powinien go od razu zatrzymać."""
    app = _make_gui(gg)
    app.glava_enabled_var = _FakeVar(True)
    app._inst_modules = {0: "bars"}
    app.active_module = "bars"
    app.instances = {0: object()}
    app.processes = {0: None}
    app.root = _FakeRoot()
    app.update_status = lambda: None

    import gui.core as core_mod
    monkeypatch.setattr(core_mod, "GLAVA_DISABLE_FLAG", str(tmp_path / "disabled"))

    import gui.glava as glava_mod
    stop_calls = []
    monkeypatch.setattr(glava_mod, "glava_stop_instance",
                         lambda proc: stop_calls.append(proc))

    fake_proc = object()

    def mock_restart(instance, module, proc, after_fn):
        # Symuluje: użytkownik kliknął OFF zanim ten konkretny restart
        # zdążył wrócić z after_fn.
        app.glava_enabled_var.set(False)
        after_fn(fake_proc)

    monkeypatch.setattr(glava_mod, "glava_restart_instance", mock_restart)

    app._on_glava_toggle()

    assert stop_calls == [fake_proc]
    assert app.processes[0] is None  # NIE zarejestrowany — zatrzymany od razu
    assert app._toggle_in_progress is False
