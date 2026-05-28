# =============================================================================
# tests/test_glava_process.py
# Testy funkcji zarządzania procesami GLava:
# glava_start, glava_stop_instance, glava_is_instance_running,
# toggle_wallpaper_lock, update_autostart.
# =============================================================================
import pytest
import os
import subprocess
import time

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def pid_home(tmp_path, monkeypatch):
    from gui import glava as glava_mod
    monkeypatch.setattr(glava_mod, "_PID_DIR", str(tmp_path))
    return tmp_path

@pytest.fixture
def fake_instance(tmp_path, monkeypatch):
    """GlavaInstance z tmp_path jako home."""
    import glob, shutil
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))
    glava_dir = tmp_path / ".config" / "glava"
    glava_dir.mkdir(parents=True)
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    for f in glob.glob(os.path.join(src, "*.glsl")):
        shutil.copy2(f, str(glava_dir))
    inst = inst_mod.GlavaInstance(0, home=str(tmp_path))
    inst.create()
    return inst

@pytest.fixture
def autostart_file(tmp_path, monkeypatch):
    from gui import glava as glava_mod
    path = str(tmp_path / "autostart" / "glava.desktop")
    monkeypatch.setattr(glava_mod, "AUTOSTART_FILE", path)
    return path

# ── glava_start ───────────────────────────────────────────────────────────────

def test_glava_start_returns_popen_or_none(pid_home, fake_instance):
    """glava_start zwraca Popen lub None — nie crashuje."""
    from gui.glava import glava_start
    result = glava_start(instance=fake_instance)
    # glava może nie być zainstalowane w środowisku testowym — akceptujemy None
    if result is not None:
        assert hasattr(result, 'poll')
        assert hasattr(result, 'terminate')
        result.terminate()
        result.wait(timeout=3)

def test_glava_start_writes_pid(pid_home, fake_instance):
    """glava_start zapisuje PID do pliku gdy instance podana."""
    from gui.glava import glava_start, read_pid, _pid_path
    result = glava_start(instance=fake_instance)
    if result is None:
        pytest.skip("glava nie jest zainstalowana")
    assert os.path.exists(_pid_path(fake_instance.inst_id))
    assert read_pid(fake_instance.inst_id) == result.pid
    result.terminate()
    result.wait(timeout=3)

def test_glava_start_sets_xdg_env(pid_home, fake_instance, monkeypatch):
    """glava_start przekazuje XDG_CONFIG_HOME z instance.xdg_dir."""
    from gui import glava as glava_mod
    captured_env = {}
    original_popen = subprocess.Popen

    def mock_popen(cmd, **kwargs):
        captured_env.update(kwargs.get('env', {}))
        raise FileNotFoundError("glava not installed")

    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    from gui.glava import glava_start
    glava_start(instance=fake_instance)
    assert captured_env.get("XDG_CONFIG_HOME") == fake_instance.xdg_dir

def test_glava_start_no_instance_no_xdg(pid_home, monkeypatch):
    """glava_start bez instance nie nadpisuje XDG_CONFIG_HOME."""
    captured_env = {}

    def mock_popen(cmd, **kwargs):
        captured_env.update(kwargs.get('env', {}))
        raise FileNotFoundError("glava not installed")

    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    from gui.glava import glava_start
    glava_start()
    assert "XDG_CONFIG_HOME" not in captured_env

def test_glava_start_extra_flags(pid_home, monkeypatch):
    """glava_start przekazuje extra_flags do komendy."""
    captured_cmd = []

    def mock_popen(cmd, **kwargs):
        captured_cmd.extend(cmd)
        raise FileNotFoundError("glava not installed")

    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    from gui.glava import glava_start
    glava_start(extra_flags="--desktop --verbose")
    assert "--desktop" in captured_cmd
    assert "--verbose" in captured_cmd

def test_glava_start_default_flag(pid_home, monkeypatch):
    """glava_start bez extra_flags dodaje --desktop."""
    captured_cmd = []

    def mock_popen(cmd, **kwargs):
        captured_cmd.extend(cmd)
        raise FileNotFoundError("glava not installed")

    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    from gui.glava import glava_start
    glava_start()
    assert "--desktop" in captured_cmd

# ── glava_stop_instance ───────────────────────────────────────────────────────

def test_glava_stop_instance_terminates_process(pid_home):
    """glava_stop_instance zatrzymuje działający proces."""
    from gui.glava import glava_stop_instance
    proc = subprocess.Popen(["sleep", "10"])
    assert proc.poll() is None
    glava_stop_instance(proc)
    proc.wait(timeout=3)
    assert proc.poll() is not None

def test_glava_stop_instance_none_does_not_crash(pid_home):
    from gui.glava import glava_stop_instance
    glava_stop_instance(None)

def test_glava_stop_instance_already_dead(pid_home):
    """glava_stop_instance na martwym procesie nie crashuje."""
    from gui.glava import glava_stop_instance
    proc = subprocess.Popen(["sleep", "0.05"])
    proc.wait()
    glava_stop_instance(proc)

def test_glava_stop_instance_clears_pid_for_adopted(pid_home):
    """glava_stop_instance usuwa plik PID dla _AdoptedProcess."""
    from gui.glava import glava_stop_instance, _AdoptedProcess, write_pid, _pid_path
    proc = subprocess.Popen(["sleep", "10"])
    write_pid(1, proc.pid)
    ap = _AdoptedProcess(proc.pid, inst_id=1)
    glava_stop_instance(ap)
    proc.wait(timeout=3)
    assert not os.path.exists(_pid_path(1))

# ── glava_is_instance_running ─────────────────────────────────────────────────

def test_glava_is_instance_running_live(pid_home):
    from gui.glava import glava_is_instance_running
    proc = subprocess.Popen(["sleep", "5"])
    assert glava_is_instance_running(proc) == True
    proc.kill()
    proc.wait()

def test_glava_is_instance_running_dead(pid_home):
    from gui.glava import glava_is_instance_running
    proc = subprocess.Popen(["sleep", "0.05"])
    proc.wait()
    assert glava_is_instance_running(proc) == False

def test_glava_is_instance_running_none(pid_home):
    from gui.glava import glava_is_instance_running
    assert glava_is_instance_running(None) == False

# ── toggle_wallpaper_lock ─────────────────────────────────────────────────────

def test_toggle_wallpaper_lock_creates_file(tmp_path):
    from gui.glava import toggle_wallpaper_lock
    lock = str(tmp_path / "wallpaper.lock")
    result = toggle_wallpaper_lock(lock)
    assert result == True
    assert os.path.exists(lock)

def test_toggle_wallpaper_lock_removes_file(tmp_path):
    from gui.glava import toggle_wallpaper_lock
    lock = str(tmp_path / "wallpaper.lock")
    open(lock, "a").close()
    result = toggle_wallpaper_lock(lock)
    assert result == False
    assert not os.path.exists(lock)

def test_toggle_wallpaper_lock_toggle_twice(tmp_path):
    from gui.glava import toggle_wallpaper_lock
    lock = str(tmp_path / "wallpaper.lock")
    assert toggle_wallpaper_lock(lock) == True
    assert toggle_wallpaper_lock(lock) == False
    assert toggle_wallpaper_lock(lock) == True

# ── update_autostart ──────────────────────────────────────────────────────────

def test_update_autostart_creates_file(autostart_file):
    from gui.glava import update_autostart
    result = update_autostart("--desktop")
    assert result == True
    assert os.path.exists(autostart_file)

def test_update_autostart_exec_line(autostart_file):
    from gui.glava import update_autostart
    update_autostart("--desktop --verbose")
    with open(autostart_file) as f:
        content = f.read()
    assert "Exec=glava --desktop --verbose" in content

def test_update_autostart_empty_flags(autostart_file):
    """Puste extra_flags używają --desktop jako fallback."""
    from gui.glava import update_autostart
    update_autostart("")
    with open(autostart_file) as f:
        content = f.read()
    assert "Exec=glava --desktop" in content

def test_update_autostart_none_flags(autostart_file):
    from gui.glava import update_autostart
    update_autostart(None)
    with open(autostart_file) as f:
        content = f.read()
    assert "Exec=glava --desktop" in content

def test_update_autostart_overwrites_exec(autostart_file):
    """Drugi zapis nadpisuje linię Exec=, nie duplikuje."""
    from gui.glava import update_autostart
    update_autostart("--desktop")
    update_autostart("--desktop --verbose")
    with open(autostart_file) as f:
        content = f.read()
    assert content.count("Exec=") == 1
    assert "Exec=glava --desktop --verbose" in content

def test_update_autostart_desktop_entry_format(autostart_file):
    """Nowo tworzony plik ma poprawny format Desktop Entry."""
    from gui.glava import update_autostart
    update_autostart("--desktop")
    with open(autostart_file) as f:
        content = f.read()
    assert "[Desktop Entry]" in content
    assert "Type=Application" in content
    assert "Name=GLava" in content
