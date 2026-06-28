# =============================================================================
# tests/test_glava.py
# Testy jednostkowe dla gui/glava.py
# Pokrywa: PID management, _AdoptedProcess, glava_stop_instance,
#          _write_rc_module, read_rc_module, update_autostart,
#          toggle_wallpaper_lock, glava_is_instance_running
# Bez realnych procesów GLava — subprocess mockowany.
# =============================================================================

import os
import sys
import time
import signal
import pytest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))



from gui.glava import (
    _pid_path,
    write_pid,
    read_pid,
    clear_pid,
    is_pid_running,
    adopt_instance,
    _AdoptedProcess,
    glava_stop_instance,
    glava_is_instance_running,
    _write_rc_module,
    read_rc_module,
    update_autostart,
    toggle_wallpaper_lock,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_pid_dir(tmp_path, monkeypatch):
    """Przekierowuje _PID_DIR na tmp_path żeby nie pisać do ~/.config/GlavaMP."""
    import gui.glava as glava_mod
    monkeypatch.setattr(glava_mod, "_PID_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def rc_file(tmp_path):
    def _make(content, name="rc.glsl"):
        p = tmp_path / name
        p.write_text(content)
        return str(p)
    return _make


# ---------------------------------------------------------------------------
# PID management
# ---------------------------------------------------------------------------

class TestPidManagement:
    def test_write_and_read_pid(self, tmp_path):
        write_pid(1, 12345)
        assert read_pid(1) == 12345

    def test_read_pid_missing_file(self):
        assert read_pid(99) is None

    def test_clear_pid_removes_file(self, tmp_path):
        write_pid(2, 99999)
        clear_pid(2)
        assert read_pid(2) is None

    def test_clear_pid_no_crash_if_missing(self):
        clear_pid(999)   # nie powinno rzucić wyjątku

    def test_write_pid_swallows_exception(self, monkeypatch):
        """open() rzuca (np. brak uprawnień) -> except Exception: pass,
        write_pid nie powinno podnieść wyjątku."""
        monkeypatch.setattr(
            "builtins.open",
            lambda *a, **kw: (_ for _ in ()).throw(PermissionError("denied")))
        write_pid(123, 456)

    def test_clear_pid_swallows_non_filenotfound_exception(self, monkeypatch):
        """os.remove rzuca coś INNEGO niż FileNotFoundError (np. PermissionError)
        -> musi trafić w drugi, ogólny except Exception: pass, nie w pierwszy."""
        import gui.glava as glava_mod
        monkeypatch.setattr(
            glava_mod.os, "remove",
            lambda p: (_ for _ in ()).throw(PermissionError("denied")))
        clear_pid(123)   # nie powinno rzucić wyjątku

    def test_pid_path_format(self, tmp_path):
        import gui.glava as glava_mod
        path = _pid_path(5)
        assert path.endswith("inst-5.pid")


# ---------------------------------------------------------------------------
# is_pid_running
# ---------------------------------------------------------------------------

class TestIsPidRunning:
    def test_none_returns_false(self):
        assert is_pid_running(None) is False

    def test_running_process(self):
        # Własny PID zawsze istnieje
        assert is_pid_running(os.getpid()) is True

    def test_dead_pid(self):
        # PID 999999 prawie na pewno nie istnieje
        assert is_pid_running(999999) is False


# ---------------------------------------------------------------------------
# _AdoptedProcess
# ---------------------------------------------------------------------------

class TestAdoptedProcess:
    def test_poll_returns_none_when_alive(self):
        proc = _AdoptedProcess(os.getpid(), inst_id=1)
        assert proc.poll() is None

    def test_poll_returns_minus_one_when_dead(self):
        proc = _AdoptedProcess(999999, inst_id=1)
        assert proc.poll() == -1

    def test_terminate_dead_pid_no_crash(self):
        proc = _AdoptedProcess(999999, inst_id=1)
        proc.terminate()   # nie powinno rzucić

    def test_kill_dead_pid_no_crash(self):
        proc = _AdoptedProcess(999999, inst_id=1)
        proc.kill()

    def test_wait_returns_immediately_for_dead_pid(self):
        proc = _AdoptedProcess(999999, inst_id=1)
        start = time.time()
        proc.wait(timeout=2)
        # Martwy PID → brak /proc/<pid>/status → natychmiastowy powrót
        assert time.time() - start < 1.0

    def test_repr(self):
        proc = _AdoptedProcess(1234, inst_id=3)
        assert "1234" in repr(proc)
        assert "3" in repr(proc)


# ---------------------------------------------------------------------------
# adopt_instance
# ---------------------------------------------------------------------------

class TestAdoptInstance:
    def test_no_pid_file_returns_none(self):
        pid, proc = adopt_instance(42)
        assert pid is None
        assert proc is None

    def test_dead_pid_returns_none_and_clears_file(self):
        write_pid(7, 999999)   # martwy PID
        pid, proc = adopt_instance(7)
        assert pid is None
        assert proc is None
        assert read_pid(7) is None   # plik wyczyszczony

    def test_live_pid_returns_adopted_process(self):
        own_pid = os.getpid()
        write_pid(8, own_pid)
        pid, proc = adopt_instance(8)
        assert pid == own_pid
        assert isinstance(proc, _AdoptedProcess)


# ---------------------------------------------------------------------------
# glava_is_instance_running
# ---------------------------------------------------------------------------

class TestGlavaIsInstanceRunning:
    def test_none_returns_false(self):
        assert glava_is_instance_running(None) is False

    def test_alive_popen_returns_true(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        assert glava_is_instance_running(mock_proc) is True

    def test_dead_popen_returns_false(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        assert glava_is_instance_running(mock_proc) is False


# ---------------------------------------------------------------------------
# glava_stop_instance
# ---------------------------------------------------------------------------

class TestGlavaStopInstance:
    def test_none_proc_no_crash(self):
        glava_stop_instance(None)

    def test_stops_running_popen(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 999999   # martwy PID — pętla kill od razu kończy
        glava_stop_instance(mock_proc)
        mock_proc.terminate.assert_called_once()

    def test_already_dead_popen_skips_terminate(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1   # już martwy
        glava_stop_instance(mock_proc)
        mock_proc.terminate.assert_not_called()

    def test_adopted_process_clears_pid(self, tmp_path):
        own_pid = os.getpid()
        write_pid(9, own_pid)
        proc = _AdoptedProcess(999999, inst_id=9)  # martwy PID
        glava_stop_instance(proc)
        assert read_pid(9) is None


# ---------------------------------------------------------------------------
# _write_rc_module / read_rc_module
# ---------------------------------------------------------------------------

class TestWriteRcModule:
    def test_writes_module(self, rc_file):
        path = rc_file("#request mod bars\n")
        _write_rc_module("wave", rc_path=path)
        assert "#request mod wave" in open(path).read()

    def test_replaces_only_mod_line(self, rc_file):
        path = rc_file(
            "#request setfps 60\n"
            "#request mod bars\n"
            "#define SOME 1\n"
        )
        _write_rc_module("circle", rc_path=path)
        content = open(path).read()
        assert "#request mod circle" in content
        assert "#request setfps 60"  in content
        assert "#define SOME 1"      in content

    def test_no_op_on_missing_file(self, tmp_path):
        _write_rc_module("bars", rc_path=str(tmp_path / "missing.glsl"))


class TestReadRcModule:
    def test_reads_known_module(self, rc_file):
        path = rc_file("#request mod wave\n")
        assert read_rc_module(path) == "wave"

    def test_returns_none_for_unknown_module(self, rc_file):
        path = rc_file("#request mod unknown_mod\n")
        assert read_rc_module(path) is None

    def test_returns_none_on_missing_file(self, tmp_path):
        assert read_rc_module(str(tmp_path / "missing.glsl")) is None

    def test_returns_none_when_no_mod_line(self, rc_file):
        path = rc_file("#request setfps 60\n")
        assert read_rc_module(path) is None

    def test_all_valid_modules(self, rc_file):
        for mod in ("bars", "wave", "circle", "graph", "radial"):
            path = rc_file(f"#request mod {mod}\n")
            assert read_rc_module(path) == mod

    def test_uses_default_rc_glsl_when_path_omitted(self, tmp_path, monkeypatch):
        """rc_path=None -> funkcja musi spaść na moduł-level RC_GLSL."""
        import gui.glava as glava_mod
        rc = tmp_path / "rc.glsl"
        rc.write_text("#request mod circle\n")
        monkeypatch.setattr(glava_mod, "RC_GLSL", str(rc))
        assert read_rc_module() == "circle"

    def test_swallows_exception_and_returns_none(self, tmp_path):
        """open() na katalogu (istnieje, ale nie jest plikiem) -> IsADirectoryError
        -> except Exception: pass -> None, bez podniesienia wyjątku."""
        assert read_rc_module(str(tmp_path)) is None


# ---------------------------------------------------------------------------
# update_autostart
# ---------------------------------------------------------------------------

class TestUpdateAutostart:
    def test_creates_desktop_file(self, tmp_path, monkeypatch):
        import gui.glava as glava_mod
        desktop = str(tmp_path / "autostart" / "glava.desktop")
        monkeypatch.setattr(glava_mod, "AUTOSTART_FILE", desktop)
        result = update_autostart("--desktop")
        assert result is True
        assert os.path.exists(desktop)
        assert "Exec=glava --desktop" in open(desktop).read()

    def test_updates_existing_exec_line(self, tmp_path, monkeypatch):
        import gui.glava as glava_mod
        desktop_dir = tmp_path / "autostart"
        desktop_dir.mkdir()
        desktop = str(desktop_dir / "glava.desktop")
        open(desktop, "w").write("[Desktop Entry]\nExec=glava --desktop\n")
        monkeypatch.setattr(glava_mod, "AUTOSTART_FILE", desktop)
        update_autostart("--desktop --verbose")
        assert "Exec=glava --desktop --verbose" in open(desktop).read()

    def test_empty_flags_defaults_to_desktop(self, tmp_path, monkeypatch):
        import gui.glava as glava_mod
        desktop = str(tmp_path / "autostart" / "glava.desktop")
        monkeypatch.setattr(glava_mod, "AUTOSTART_FILE", desktop)
        update_autostart("")
        assert "Exec=glava --desktop" in open(desktop).read()

    def test_returns_false_on_permission_error(self, tmp_path, monkeypatch):
        import gui.glava as glava_mod
        # Mockujemy os.makedirs żeby rzucił PermissionError
        with patch("gui.glava.os.makedirs", side_effect=PermissionError):
            result = update_autostart("--desktop")
        assert result is False

    def test_whitespace_only_flags_defaults_to_desktop(self, tmp_path, monkeypatch):
        """extra_flags="   " jest "truthy" (niepuste), więc .strip() jest
        wołane i daje "" -> druga gałąź (if not flags) musi to złapać."""
        import gui.glava as glava_mod
        desktop = str(tmp_path / "autostart" / "glava.desktop")
        monkeypatch.setattr(glava_mod, "AUTOSTART_FILE", desktop)
        update_autostart("   ")
        assert "Exec=glava --desktop" in open(desktop).read()

    def test_appends_exec_line_when_missing_in_existing_file(self, tmp_path, monkeypatch):
        """Aktualizacja ISTNIEJĄCEGO pliku .desktop, który nie ma jeszcze
        żadnej linii Exec= -> musi ją dopisać na końcu."""
        import gui.glava as glava_mod
        desktop_dir = tmp_path / "autostart"
        desktop_dir.mkdir()
        desktop = str(desktop_dir / "glava.desktop")
        open(desktop, "w").write("[Desktop Entry]\nName=GLava\n")
        monkeypatch.setattr(glava_mod, "AUTOSTART_FILE", desktop)
        update_autostart("--desktop")
        content = open(desktop).read()
        assert "Name=GLava" in content
        assert "Exec=glava --desktop" in content


# ---------------------------------------------------------------------------
# _sudo_run
# ---------------------------------------------------------------------------

class TestSudoRun:
    def test_uses_sudo_directly_when_zenity_unavailable(self, monkeypatch):
        import gui.glava as glava_mod
        import shutil as shutil_mod
        monkeypatch.setattr(shutil_mod, "which", lambda name: None)
        calls = []
        monkeypatch.setattr(glava_mod.subprocess, "run",
                             lambda cmd: calls.append(cmd))

        glava_mod._sudo_run(["apt-get", "update"])

        assert calls == [["sudo", "apt-get", "update"]]

    def test_uses_zenity_password_dialog_when_available(self, monkeypatch):
        import gui.glava as glava_mod
        import shutil as shutil_mod
        monkeypatch.setattr(shutil_mod, "which", lambda name: "/usr/bin/zenity")

        calls = []

        class _Result:
            stdout = "mypassword\n"

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return _Result()

        monkeypatch.setattr(glava_mod.subprocess, "run", fake_run)

        glava_mod._sudo_run(["apt-get", "update"])

        assert calls[0][0] == ["zenity", "--password", "--title=Autoryzacja"]
        sudo_cmd, sudo_kwargs = calls[1]
        assert sudo_cmd == ["sudo", "-S", "apt-get", "update"]
        assert sudo_kwargs["input"] == "mypassword\n"

    def test_zenity_cancelled_password_skips_sudo_call(self, monkeypatch):
        """Pusty stdout z zenity (użytkownik kliknął Cancel) -> sudo NIE jest
        wołane wcale — if passwd: guard."""
        import gui.glava as glava_mod
        import shutil as shutil_mod
        monkeypatch.setattr(shutil_mod, "which", lambda name: "/usr/bin/zenity")

        calls = []

        class _Result:
            stdout = ""

        monkeypatch.setattr(glava_mod.subprocess, "run",
                             lambda cmd, **kw: calls.append(cmd) or _Result())

        glava_mod._sudo_run(["apt-get", "update"])

        assert calls == [["zenity", "--password", "--title=Autoryzacja"]]


# ---------------------------------------------------------------------------
# toggle_wallpaper_lock
# ---------------------------------------------------------------------------

class TestToggleWallpaperLock:
    def test_creates_lock_file(self, tmp_path):
        lock = str(tmp_path / "wallpaper.lock")
        result = toggle_wallpaper_lock(lock)
        assert result is True
        assert os.path.exists(lock)

    def test_removes_existing_lock(self, tmp_path):
        lock = str(tmp_path / "wallpaper.lock")
        open(lock, "a").close()
        result = toggle_wallpaper_lock(lock)
        assert result is False
        assert not os.path.exists(lock)

    def test_double_toggle_restores_lock(self, tmp_path):
        lock = str(tmp_path / "wallpaper.lock")
        r1 = toggle_wallpaper_lock(lock)  # tworzy → True
        r2 = toggle_wallpaper_lock(lock)  # usuwa → False
        r3 = toggle_wallpaper_lock(lock)  # tworzy ponownie → True
        assert r1 is True
        assert r2 is False
        assert r3 is True
        assert os.path.exists(lock)
