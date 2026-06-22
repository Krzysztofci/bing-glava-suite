import importlib.util
import os
import sys
import threading
import subprocess

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
    return gg.GlavaGUI.__new__(gg.GlavaGUI)


# ── _start_pid_watch ──────────────────────────────────────────────────────────
#
# Sprawdzamy TYLKO konfigurację (target/daemon) i ustawienie flagi — NIE
# wołamy realnego target(), żeby nie wejść w nieskończoną pętlę poniżej.

def test_start_pid_watch_spawns_daemon_thread(gg, monkeypatch):
    app = _make_gui(gg)

    thread_calls = []

    class _CapturingThread:
        def __init__(self, target=None, daemon=None):
            thread_calls.append((target, daemon))

        def start(self):
            pass  # NIE wołamy target() — tylko sprawdzamy konfigurację

    monkeypatch.setattr(threading, "Thread", _CapturingThread)

    app._start_pid_watch()

    assert app._pid_watch_active is True
    assert len(thread_calls) == 1
    assert thread_calls[0] == (app._pid_watch_thread, True)


# ── _pid_watch_thread ─────────────────────────────────────────────────────────
#
# Prawdziwa metoda ma "while self._pid_watch_active: ...” — pętlę nieskończoną
# w produkcji (kończy się tylko gdy ktoś z zewnątrz ustawi flagę na False).
# Testujemy JEDEN przebieg pętli, konstruując scenariusz który sam ustawia
# flagę na False w odpowiednim miejscu, żeby pętla zakończyła się czysto
# po wykonaniu całego ciała — bez prawdziwego subprocess.Popen, bez
# prawdziwego wątku, bez ryzyka zawieszenia testu.

def test_pid_watch_thread_polls_once_then_schedules_sync(gg, monkeypatch):
    app = _make_gui(gg)
    app._pid_watch_active = True
    app._sync_once = lambda: None

    scheduled = []

    class _OneShotRoot:
        """Po pierwszym root.after() gasi flagę -> pętla kończy się czysto
        po jednym pełnym przebiegu, zamiast wisieć w nieskończoność."""
        def after(self, delay, fn, *args):
            scheduled.append(fn)
            app._pid_watch_active = False

    app.root = _OneShotRoot()

    class _FakeProc:
        def wait(self):
            pass  # natychmiastowy powrót — flaga wciąż True w tym momencie

    popen_calls = []

    def fake_popen(*a, **kw):
        popen_calls.append((a, kw))
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    app._pid_watch_thread()  # wywołane DIREKTNIE, nie przez prawdziwy wątek

    assert len(popen_calls) == 1
    assert popen_calls[0][0][0][0] == "inotifywait"
    assert scheduled == [app._sync_once]


def test_pid_watch_thread_exits_immediately_when_inactive(gg):
    """Gdy flaga jest False od początku, pętla nigdy nie wejdzie w ciało —
    zero subprocess.Popen, zero ryzyka."""
    app = _make_gui(gg)
    app._pid_watch_active = False

    app._pid_watch_thread()  # powinno zwrócić się natychmiast, bez efektów
