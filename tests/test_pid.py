import pytest
import os
import subprocess
import time

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def pid_home(tmp_path, monkeypatch):
    """Patchuje _PID_DIR w glava.py na tmp_path."""
    from gui import glava as glava_mod
    monkeypatch.setattr(glava_mod, "_PID_DIR", str(tmp_path))
    return tmp_path

# ── write_pid / read_pid / clear_pid ─────────────────────────────────────────

def test_write_and_read_pid(pid_home):
    from gui.glava import write_pid, read_pid
    write_pid(1, 12345)
    assert read_pid(1) == 12345

def test_read_pid_missing_file(pid_home):
    from gui.glava import read_pid
    assert read_pid(99) is None

def test_read_pid_corrupt_file(pid_home):
    from gui.glava import read_pid, _pid_path
    path = _pid_path(5)
    with open(path, "w") as f:
        f.write("not_a_number")
    assert read_pid(5) is None

def test_clear_pid_removes_file(pid_home):
    from gui.glava import write_pid, clear_pid, _pid_path
    write_pid(1, 99)
    clear_pid(1)
    assert not os.path.exists(_pid_path(1))

def test_clear_pid_nonexistent_does_not_raise(pid_home):
    from gui.glava import clear_pid
    clear_pid(999)

def test_write_pid_creates_dir(tmp_path, monkeypatch):
    """write_pid tworzy katalog jeśli nie istnieje."""
    from gui import glava as glava_mod
    nested = str(tmp_path / "new" / "nested")
    monkeypatch.setattr(glava_mod, "_PID_DIR", nested)
    from gui.glava import write_pid, read_pid
    write_pid(1, 777)
    assert read_pid(1) == 777

# ── is_pid_running ────────────────────────────────────────────────────────────

def test_is_pid_running_live_process(pid_home):
    from gui.glava import is_pid_running
    # os.getpid() na pewno żyje
    assert is_pid_running(os.getpid()) == True

def test_is_pid_running_dead_pid(pid_home):
    from gui.glava import is_pid_running
    # PID 1 może żyć, użyj bardzo dużego nieistniejącego PID
    assert is_pid_running(999999999) == False

def test_is_pid_running_none(pid_home):
    from gui.glava import is_pid_running
    assert is_pid_running(None) == False

def test_is_pid_running_after_process_dies(pid_home):
    from gui.glava import is_pid_running
    proc = subprocess.Popen(["sleep", "0.05"])
    pid = proc.pid
    assert is_pid_running(pid) == True
    proc.wait()
    time.sleep(0.1)
    assert is_pid_running(pid) == False

# ── _AdoptedProcess ───────────────────────────────────────────────────────────

@pytest.fixture
def live_proc():
    """Uruchamia krótki proces i zwraca (proc, pid)."""
    p = subprocess.Popen(["sleep", "5"])
    yield p
    p.kill()
    p.wait()

def test_adopted_poll_live(pid_home, live_proc):
    from gui.glava import _AdoptedProcess
    ap = _AdoptedProcess(live_proc.pid, inst_id=1)
    assert ap.poll() is None

def test_adopted_poll_dead(pid_home):
    from gui.glava import _AdoptedProcess
    proc = subprocess.Popen(["sleep", "0.05"])
    pid = proc.pid
    proc.wait()
    time.sleep(0.1)
    ap = _AdoptedProcess(pid, inst_id=1)
    assert ap.poll() == -1

def test_adopted_terminate(pid_home):
    from gui.glava import _AdoptedProcess
    proc = subprocess.Popen(["sleep", "5"])
    ap = _AdoptedProcess(proc.pid, inst_id=1)
    ap.terminate()
    proc.wait(timeout=3)
    assert ap.poll() == -1

def test_adopted_kill(pid_home):
    from gui.glava import _AdoptedProcess
    proc = subprocess.Popen(["sleep", "5"])
    ap = _AdoptedProcess(proc.pid, inst_id=1)
    ap.kill()
    proc.wait(timeout=3)
    assert ap.poll() == -1

def test_adopted_wait(pid_home):
    """wait() zwraca gdy proces zakończy się lub zniknie z /proc."""
    from gui.glava import _AdoptedProcess
    proc = subprocess.Popen(["sleep", "0.1"])
    ap = _AdoptedProcess(proc.pid, inst_id=1)
    # Zbieramy proces przez Popen.wait() żeby nie był zombie
    proc.wait()
    # Teraz /proc/<pid> powinno zniknąć — ap.wait() wraca natychmiast
    ap.wait(timeout=2)
    assert ap.poll() == -1

def test_adopted_repr(pid_home):
    from gui.glava import _AdoptedProcess
    ap = _AdoptedProcess(1234, inst_id=2)
    assert "1234" in repr(ap)
    assert "2" in repr(ap)

# ── adopt_instance ────────────────────────────────────────────────────────────

def test_adopt_instance_live(pid_home):
    from gui.glava import adopt_instance, write_pid
    proc = subprocess.Popen(["sleep", "5"])
    write_pid(1, proc.pid)
    pid, ap = adopt_instance(1)
    assert pid == proc.pid
    assert ap is not None
    assert ap.poll() is None
    proc.kill()
    proc.wait()

def test_adopt_instance_dead_pid(pid_home):
    from gui.glava import adopt_instance, write_pid
    proc = subprocess.Popen(["sleep", "0.05"])
    pid = proc.pid
    proc.wait()
    time.sleep(0.1)
    write_pid(1, pid)
    result_pid, ap = adopt_instance(1)
    assert result_pid is None
    assert ap is None

def test_adopt_instance_no_pid_file(pid_home):
    from gui.glava import adopt_instance
    pid, ap = adopt_instance(99)
    assert pid is None
    assert ap is None
