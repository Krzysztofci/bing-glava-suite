import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import gui.glava as glava_mod


class _SyncThread:
    """Podstawia threading.Thread — wykonuje target() SYNCHRONICZNIE,
    eliminując realny wątek tła i niedeterminizm timing w testach."""
    def __init__(self, target=None, daemon=None, args=(), kwargs=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


# =============================================================================
# glava_stop_instance — najważniejsza funkcja w pliku: gwarantuje że proces
# faktycznie nie żyje przed powrotem. Dotąd niepokryte: eskalacja do SIGKILL
# po 2s, fallback dla proc bez .pid, zewnętrzny except OSError.
# =============================================================================

def test_glava_stop_instance_escalates_to_sigkill_after_timeout(monkeypatch):
    """Proces nie umiera po SIGTERM w ciągu 2s -> musi dostać SIGKILL."""
    class _NeverDyingProc:
        pid = 424242

        def __init__(self):
            self.killed = False

        def poll(self):
            return None  # "wciąż żywy" w momencie wejścia

        def terminate(self):
            pass

        def kill(self):
            self.killed = True

    fake_proc = _NeverDyingProc()

    # os.kill(pid, 0) ma zawsze "się udać" — proces nigdy nie znika z
    # punktu widzenia pętli oczekującej na śmierć.
    monkeypatch.setattr(glava_mod.os, "kill", lambda pid, sig: None)

    # Precyzyjnie kontrolowany "czas" — pierwsze wywołanie ustawia deadline,
    # drugie (sprawdzenie while) jest jeszcze przed deadline, trzecie (po
    # jednej iteracji) jest już PO deadline -> wchodzi w gałąź else: SIGKILL.
    times = iter([1000.0, 1000.0, 2000.0])
    monkeypatch.setattr(glava_mod.time, "time", lambda: next(times, 2000.0))
    monkeypatch.setattr(glava_mod.time, "sleep", lambda s: None)

    glava_mod.glava_stop_instance(fake_proc)

    assert fake_proc.killed is True


def test_glava_stop_instance_no_pid_falls_back_to_wait_then_kill(monkeypatch):
    """proc bez atrybutu .pid (np. czysty mock) -> gałąź proc.wait(timeout=2),
    a po TimeoutExpired -> proc.kill()."""
    import subprocess as subprocess_mod

    class _NoPidProc:
        def __init__(self):
            self.kill_called = False

        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            raise subprocess_mod.TimeoutExpired(cmd="glava", timeout=timeout)

        def kill(self):
            self.kill_called = True

    fake_proc = _NoPidProc()
    # getattr(proc, "pid", None) musi zwrócić None — nie definiujemy .pid

    glava_mod.glava_stop_instance(fake_proc)

    assert fake_proc.kill_called is True


def test_glava_stop_instance_swallows_outer_oserror(monkeypatch):
    """proc.poll() rzuca OSError (np. zombie w dziwnym stanie) -> funkcja
    ma broad except OSError: pass, nie powinna crashować."""
    class _BrokenProc:
        def poll(self):
            raise OSError("kernel zombie weirdness")

    glava_mod.glava_stop_instance(_BrokenProc())  # nie powinno podnieść wyjątku


def test_glava_stop_instance_clears_pid_for_adopted_after_kill(monkeypatch, tmp_path):
    """Po zatrzymaniu _AdoptedProcess, plik PID powinien zostać usunięty —
    niezależnie od tego, którą ścieżką (SIGTERM/SIGKILL) proces faktycznie
    się zakończył."""
    monkeypatch.setattr(glava_mod, "_PID_DIR", str(tmp_path))
    glava_mod.write_pid(7, 999999999)  # PID na pewno nieżywy
    assert glava_mod.read_pid(7) == 999999999

    pid_field, ap = glava_mod.adopt_instance(7)
    # adopt_instance na nieżywym PID zwraca (None, None) i czyści plik —
    # więc tworzymy _AdoptedProcess ręcznie, żeby przetestować samo
    # czyszczenie w glava_stop_instance niezależnie od adopt_instance.
    glava_mod.write_pid(7, 999999999)
    ap = glava_mod._AdoptedProcess(999999999, 7)
    monkeypatch.setattr(ap, "poll", lambda: -1)  # już martwy -> krótka ścieżka

    glava_mod.glava_stop_instance(ap)

    assert glava_mod.read_pid(7) is None


# =============================================================================
# glava_restart_instance — REALNA implementacja (gdzie indziej w repo zawsze
# mockowana: test_toggle_race.py, test_shader_change_debounce.py,
# test_glava_gui_toggle.py, test_glava_gui_instances.py). Tu testujemy
# prawdziwy kod, z _SyncThread zamiast realnego wątku w tle.
# =============================================================================

def test_glava_restart_instance_full_cycle(monkeypatch):
    monkeypatch.setattr(threading, "Thread", _SyncThread)

    write_rc_calls = []
    monkeypatch.setattr(glava_mod, "_write_rc_module",
                         lambda module, rc_path=None: write_rc_calls.append((module, rc_path)))
    stop_calls = []
    monkeypatch.setattr(glava_mod, "glava_stop_instance",
                         lambda proc: stop_calls.append(proc))
    clear_calls = []
    monkeypatch.setattr(glava_mod, "clear_pid", lambda iid: clear_calls.append(iid))

    fake_new_proc = object()
    start_calls = []

    def fake_glava_start(extra_flags, env=None, instance=None):
        start_calls.append((extra_flags, env, instance))
        return fake_new_proc

    monkeypatch.setattr(glava_mod, "glava_start", fake_glava_start)

    class _FakeInstance:
        inst_id = 3
        rc_glsl = "/tmp/rc.glsl"

    inst = _FakeInstance()
    old_proc = object()
    after_calls = []

    glava_mod.glava_restart_instance(
        instance=inst, module="bars", delay_ms=0, proc=old_proc,
        after_fn=lambda p: after_calls.append(p),
    )

    assert write_rc_calls == [("bars", "/tmp/rc.glsl")]
    assert stop_calls == [old_proc]
    assert clear_calls == [3]
    assert len(start_calls) == 1
    assert after_calls == [fake_new_proc]


def test_glava_restart_instance_without_after_fn(monkeypatch):
    """after_fn=None nie powinno crashować — if after_fn: guard."""
    monkeypatch.setattr(threading, "Thread", _SyncThread)
    monkeypatch.setattr(glava_mod, "_write_rc_module", lambda module, rc_path=None: None)
    monkeypatch.setattr(glava_mod, "glava_stop_instance", lambda proc: None)
    monkeypatch.setattr(glava_mod, "clear_pid", lambda iid: None)
    monkeypatch.setattr(glava_mod, "glava_start", lambda *a, **kw: None)

    class _FakeInstance:
        inst_id = 0
        rc_glsl = "/tmp/rc.glsl"

    glava_mod.glava_restart_instance(instance=_FakeInstance(), module="wave", delay_ms=0)


# =============================================================================
# _AdoptedProcess.wait() — odczyt /proc/<pid>/status z detekcją zombie
# =============================================================================

def test_adopted_process_wait_returns_immediately_when_proc_status_missing():
    """PID na pewno nieistniejący -> /proc/<pid>/status nie istnieje ->
    return natychmiast, zero mockowania potrzebne."""
    ap = glava_mod._AdoptedProcess(999999999, 0)
    ap.wait(timeout=1)  # nie powinno wisieć ani podnieść wyjątku


def test_adopted_process_wait_detects_zombie_state(monkeypatch):
    import io
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    fake_content = "Name:\tglava\nState:\tZ (zombie)\n"
    monkeypatch.setattr("builtins.open", lambda *a, **kw: io.StringIO(fake_content))

    ap = glava_mod._AdoptedProcess(12345, 0)
    ap.wait(timeout=1)  # powinno wrócić od razu po wykryciu "Z" w State:


def test_adopted_process_wait_polls_until_timeout_when_alive(monkeypatch):
    import io
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    monkeypatch.setattr("builtins.open",
                         lambda *a, **kw: io.StringIO("State:\tS (sleeping)\n"))

    ap = glava_mod._AdoptedProcess(12345, 0)
    ap.wait(timeout=0.15)  # proces "żywy" cały czas -> pętla do timeoutu


# =============================================================================
# Funkcje globalne (legacy/toggle) — dotąd tylko mockowane gdzie indziej
# =============================================================================

def test_glava_is_running_true_when_pgrep_succeeds(monkeypatch):
    import subprocess as subprocess_mod

    class _Result:
        returncode = 0

    monkeypatch.setattr(subprocess_mod, "run", lambda *a, **kw: _Result())

    assert glava_mod.glava_is_running() is True


def test_glava_is_running_false_when_pgrep_fails(monkeypatch):
    import subprocess as subprocess_mod

    class _Result:
        returncode = 1

    monkeypatch.setattr(subprocess_mod, "run", lambda *a, **kw: _Result())

    assert glava_mod.glava_is_running() is False


def test_glava_stop_all_calls_pkill(monkeypatch):
    import subprocess as subprocess_mod
    calls = []
    monkeypatch.setattr(subprocess_mod, "run", lambda cmd: calls.append(cmd))

    glava_mod.glava_stop_all()

    assert calls == [["pkill", "-x", "glava"]]


def test_glava_toggle_stops_when_running(monkeypatch):
    monkeypatch.setattr(glava_mod, "glava_is_running", lambda: True)
    import subprocess as subprocess_mod
    calls = []
    monkeypatch.setattr(subprocess_mod, "run", lambda cmd, **kw: calls.append(cmd))
    start_calls = []
    monkeypatch.setattr(glava_mod, "glava_start", lambda **kw: start_calls.append(kw))

    glava_mod.glava_toggle()

    assert calls == [["pkill", "-x", "glava"]]
    assert start_calls == []


def test_glava_toggle_starts_when_not_running(monkeypatch):
    monkeypatch.setattr(glava_mod, "glava_is_running", lambda: False)
    start_calls = []
    monkeypatch.setattr(glava_mod, "glava_start", lambda **kw: start_calls.append(kw))

    glava_mod.glava_toggle()

    assert len(start_calls) == 1
    assert "XDG_RUNTIME_DIR" in start_calls[0]["env"]


# =============================================================================
# restore_auto / update_autostart — pliki flag i autostart .desktop
# =============================================================================

def test_restore_auto_removes_flags_and_starts_script(monkeypatch, tmp_path):
    red_flag    = tmp_path / "red"
    manual_flag = tmp_path / "manual"
    red_flag.write_text("")
    manual_flag.write_text("")
    monkeypatch.setattr(glava_mod, "FLAG_RED", str(red_flag))
    monkeypatch.setattr(glava_mod, "FLAG_MANUAL", str(manual_flag))
    monkeypatch.setattr(glava_mod, "BIN_DIR", str(tmp_path))

    import subprocess as subprocess_mod
    popen_calls = []
    monkeypatch.setattr(subprocess_mod, "Popen", lambda cmd: popen_calls.append(cmd))

    callback_calls = []
    glava_mod.restore_auto(callback=lambda: callback_calls.append(True))

    assert not red_flag.exists()
    assert not manual_flag.exists()
    assert len(popen_calls) == 1
    assert callback_calls == [True]


def test_restore_auto_without_callback(monkeypatch, tmp_path):
    monkeypatch.setattr(glava_mod, "FLAG_RED", str(tmp_path / "no_red"))
    monkeypatch.setattr(glava_mod, "FLAG_MANUAL", str(tmp_path / "no_manual"))
    monkeypatch.setattr(glava_mod, "BIN_DIR", str(tmp_path))
    import subprocess as subprocess_mod
    monkeypatch.setattr(subprocess_mod, "Popen", lambda cmd: None)

    glava_mod.restore_auto()  # callback=None -> nie powinno crashować


def test_update_autostart_returns_false_on_exception(monkeypatch, tmp_path):
    monkeypatch.setattr(glava_mod, "AUTOSTART_FILE",
                         str(tmp_path / "sub" / "glava.desktop"))
    monkeypatch.setattr(glava_mod.os, "makedirs",
                         lambda *a, **kw: (_ for _ in ()).throw(PermissionError("denied")))

    result = glava_mod.update_autostart("--desktop")

    assert result is False


# =============================================================================
# glava_start — gałąź env= (nadpisanie zmiennych środowiskowych)
# =============================================================================

def test_glava_start_applies_custom_env(monkeypatch, tmp_path):
    monkeypatch.setattr(glava_mod, "_PID_DIR", str(tmp_path))

    captured_env = {}

    class _FakeProc:
        pid = 111

    def fake_popen(cmd, stdout=None, stderr=None, env=None):
        captured_env.update(env or {})
        return _FakeProc()

    import subprocess as subprocess_mod
    monkeypatch.setattr(subprocess_mod, "Popen", fake_popen)

    glava_mod.glava_start(env={"MY_CUSTOM_VAR": "1"})

    assert captured_env.get("MY_CUSTOM_VAR") == "1"
