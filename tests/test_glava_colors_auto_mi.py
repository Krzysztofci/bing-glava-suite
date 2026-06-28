# =============================================================================
# tests/test_glava_colors_auto_mi.py
# Testy dla scripts/glava-colors-auto-mi — wieloinstancyjny auto-updater
# kolorów z tapety Bing (PID management, start/stop procesów GLava per
# instancja, orkiestracja w main()).
#
# UWAGA: plik źródłowy nie ma rozszerzenia .py -> logic-cov (path.suffix ==
# ".py" w jego file-discovery) nigdy go nie zobaczy w żadnym raporcie,
# niezależnie od pokrycia. To nie zmienia faktu, że zawiera realną logikę
# (te samy wzorce co gui/glava.py: PID files, SIGTERM->SIGKILL escalation,
# env var construction) — testujemy go normalnie, tylko bez wsparcia
# narzędzia przy mierzeniu wyniku (czysty coverage.py).
#
# Ładowanie: spec_from_file_location nie umie wywnioskować loadera dla
# pliku bez rozszerzenia (w przeciwieństwie do glava-gui.py, gdzie .py
# pozwala na automatyczne wykrycie) -> jawny SourceFileLoader.
# =============================================================================

import os
import sys
import json
import signal
import importlib.util
from importlib.machinery import SourceFileLoader

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def _load_module():
    path = os.path.join(os.path.dirname(__file__), "..", "scripts",
                         "glava-colors-auto-mi")
    loader = SourceFileLoader("glava_colors_auto_mi", path)
    spec = importlib.util.spec_from_loader("glava_colors_auto_mi", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mi():
    """Moduł-skrypt wczytany raz na cały plik. __name__ != '__main__' (bo
    spec_from_loader dostaje własną nazwę) -> `if __name__ == '__main__':
    main()` na dole skryptu NIE odpala się przy ładowaniu. Stałe ścieżek są
    monkeypatchowane per-test, więc współdzielenie modułu jest bezpieczne."""
    return _load_module()


class _FakeInstance:
    def __init__(self, inst_id, exists=True, xdg_dir="/tmp/xdg"):
        self.inst_id = inst_id
        self._exists = exists
        self.xdg_dir = xdg_dir

    def exists(self):
        return self._exists

    def module_tmpl(self, module):
        return f"/tmp/{module}_tmpl.frag"

    def module_frag(self, module):
        return f"/tmp/{module}_live.frag"


# ── load_instances ────────────────────────────────────────────────────────────

def test_load_instances_missing_file_returns_empty_list(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "INSTANCES_FILE", str(tmp_path / "missing.json"))
    assert mi.load_instances() == []


def test_load_instances_returns_parsed_list(mi, tmp_path, monkeypatch):
    f = tmp_path / "instances.json"
    f.write_text(json.dumps([{"inst_id": 1, "module": "bars"}]))
    monkeypatch.setattr(mi, "INSTANCES_FILE", str(f))
    assert mi.load_instances() == [{"inst_id": 1, "module": "bars"}]


def test_load_instances_non_list_json_returns_empty_list(mi, tmp_path, monkeypatch):
    """Plik istnieje, JSON poprawny, ale nie jest listą (np. dict) ->
    isinstance(data, list) guard musi to złapać."""
    f = tmp_path / "instances.json"
    f.write_text(json.dumps({"not": "a list"}))
    monkeypatch.setattr(mi, "INSTANCES_FILE", str(f))
    assert mi.load_instances() == []


def test_load_instances_corrupt_json_swallows_exception(mi, tmp_path, monkeypatch):
    f = tmp_path / "instances.json"
    f.write_text("{not valid json")
    monkeypatch.setattr(mi, "INSTANCES_FILE", str(f))
    assert mi.load_instances() == []


# ── load_gradient_mode ────────────────────────────────────────────────────────

def test_load_gradient_mode_missing_file_defaults_to_rgb(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "SETTINGS_FILE", str(tmp_path / "missing.json"))
    assert mi.load_gradient_mode() == "rgb"


def test_load_gradient_mode_reads_value_from_file(mi, tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"gradient_mode": "hsv"}))
    monkeypatch.setattr(mi, "SETTINGS_FILE", str(f))
    assert mi.load_gradient_mode() == "hsv"


def test_load_gradient_mode_missing_key_defaults_to_rgb(mi, tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"other_key": 1}))
    monkeypatch.setattr(mi, "SETTINGS_FILE", str(f))
    assert mi.load_gradient_mode() == "rgb"


def test_load_gradient_mode_corrupt_json_swallows_exception(mi, tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    f.write_text("{not valid json")
    monkeypatch.setattr(mi, "SETTINGS_FILE", str(f))
    assert mi.load_gradient_mode() == "rgb"


# ── read_pid ──────────────────────────────────────────────────────────────────

def test_read_pid_missing_file_returns_none(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))
    assert mi.read_pid(99) is None


def test_read_pid_reads_valid_int(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))
    (tmp_path / "inst-1.pid").write_text("12345")
    assert mi.read_pid(1) == 12345


def test_read_pid_corrupt_content_returns_none(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))
    (tmp_path / "inst-2.pid").write_text("not-a-number")
    assert mi.read_pid(2) is None


# ── is_pid_running ────────────────────────────────────────────────────────────

def test_is_pid_running_none_returns_false(mi):
    assert mi.is_pid_running(None) is False


def test_is_pid_running_own_pid_returns_true(mi):
    assert mi.is_pid_running(os.getpid()) is True


def test_is_pid_running_dead_pid_returns_false(mi):
    assert mi.is_pid_running(999999) is False


# ── stop_instance ─────────────────────────────────────────────────────────────

def test_stop_instance_not_running_only_clears_pid_file(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))
    (tmp_path / "inst-5.pid").write_text("999999")  # martwy PID
    kill_calls = []

    def fake_kill(pid, sig):
        if sig == 0:
            raise OSError("no such process")  # is_pid_running -> False
        kill_calls.append(sig)

    monkeypatch.setattr(mi.os, "kill", fake_kill)

    mi.stop_instance(5)

    assert kill_calls == []  # is_pid_running(999999) -> False -> brak SIGTERM
    assert not (tmp_path / "inst-5.pid").exists()


def test_stop_instance_dies_quickly_sends_only_sigterm(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))
    (tmp_path / "inst-6.pid").write_text("424242")
    kill_calls = []
    alive = {"state": True}

    def fake_kill(pid, sig):
        if sig == 0:
            if not alive["state"]:
                raise OSError("dead")
            return
        kill_calls.append(sig)
        if sig == signal.SIGTERM:
            alive["state"] = False  # "umiera" natychmiast po SIGTERM

    monkeypatch.setattr(mi.os, "kill", fake_kill)
    monkeypatch.setattr(mi.time, "sleep", lambda s: None)

    mi.stop_instance(6)

    assert kill_calls == [signal.SIGTERM]
    assert not (tmp_path / "inst-6.pid").exists()


def test_stop_instance_escalates_to_sigkill_when_process_never_dies(
        mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))
    (tmp_path / "inst-7.pid").write_text("434343")
    kill_calls = []

    def fake_kill(pid, sig):
        kill_calls.append(sig)  # is_pid_running zawsze "żywy" (sig=0 nigdy nie rzuca)

    monkeypatch.setattr(mi.os, "kill", fake_kill)
    monkeypatch.setattr(mi.time, "sleep", lambda s: None)

    mi.stop_instance(7)

    assert signal.SIGTERM in kill_calls
    assert signal.SIGKILL in kill_calls


def test_stop_instance_swallows_oserror_from_kill(mi, tmp_path, monkeypatch):
    """os.kill(pid, SIGTERM) sam rzuca OSError (np. proces zniknął tuż
    przed wysłaniem sygnału) -> zewnętrzny except OSError: pass."""
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))
    (tmp_path / "inst-8.pid").write_text("454545")

    def fake_kill(pid, sig):
        if sig == 0:
            return  # is_pid_running -> "żywy"
        raise OSError("proces zniknął")

    monkeypatch.setattr(mi.os, "kill", fake_kill)

    mi.stop_instance(8)  # nie powinno podnieść wyjątku


def test_stop_instance_pid_file_missing_does_not_crash(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))
    mi.stop_instance(999)  # brak pliku PID -> FileNotFoundError złapany


# ── start_instance ────────────────────────────────────────────────────────────

def test_start_instance_skips_when_disabled_flag_present(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "DISABLE_FLAG", str(tmp_path / "disabled"))
    (tmp_path / "disabled").write_text("")
    popen_calls = []
    monkeypatch.setattr(mi.subprocess, "Popen", lambda *a, **kw: popen_calls.append(True))

    result = mi.start_instance(1, "/tmp/xdg-inst-1")

    assert result is None
    assert popen_calls == []


def test_start_instance_sets_xdg_config_home_and_writes_pid(
        mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "DISABLE_FLAG", str(tmp_path / "disabled_unused"))
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))

    captured_env = {}

    class _FakeProc:
        pid = 777

    def fake_popen(cmd, stdout=None, stderr=None, env=None):
        captured_env.update(env or {})
        return _FakeProc()

    monkeypatch.setattr(mi.subprocess, "Popen", fake_popen)

    proc = mi.start_instance(2, "/tmp/xdg-inst-2")

    assert proc.pid == 777
    assert captured_env["XDG_CONFIG_HOME"] == "/tmp/xdg-inst-2"
    assert mi.read_pid(2) == 777


def test_start_instance_fills_display_env_defaults_when_missing(
        mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "DISABLE_FLAG", str(tmp_path / "disabled_unused"))
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.delenv("XAUTHORITY", raising=False)

    captured_env = {}

    class _FakeProc:
        pid = 1

    monkeypatch.setattr(
        mi.subprocess, "Popen",
        lambda cmd, stdout=None, stderr=None, env=None:
            captured_env.update(env or {}) or _FakeProc())

    mi.start_instance(3, "/tmp/xdg-inst-3")

    assert captured_env["DISPLAY"] == ":0"
    assert "DBUS_SESSION_BUS_ADDRESS" in captured_env
    assert captured_env["XAUTHORITY"].endswith(".Xauthority")


def test_start_instance_preserves_existing_display_env(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "DISABLE_FLAG", str(tmp_path / "disabled_unused"))
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))
    monkeypatch.setenv("DISPLAY", ":7")

    captured_env = {}

    class _FakeProc:
        pid = 1

    monkeypatch.setattr(
        mi.subprocess, "Popen",
        lambda cmd, stdout=None, stderr=None, env=None:
            captured_env.update(env or {}) or _FakeProc())

    mi.start_instance(4, "/tmp/xdg-inst-4")

    assert captured_env["DISPLAY"] == ":7"


def test_start_instance_returns_none_and_logs_on_popen_exception(
        mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "DISABLE_FLAG", str(tmp_path / "disabled_unused"))
    monkeypatch.setattr(mi, "GLAVAMP_DIR", str(tmp_path))
    monkeypatch.setattr(
        mi.subprocess, "Popen",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("brak binarki glava")))

    result = mi.start_instance(5, "/tmp/xdg-inst-5")

    assert result is None


# ── main() — wczesne wyjścia ─────────────────────────────────────────────────

def test_main_exits_when_manual_flag_present_without_force(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "FORCE", False)
    monkeypatch.setattr(mi, "FLAG_MANUAL", str(tmp_path / "manual"))
    monkeypatch.setattr(mi, "FLAG_RED", str(tmp_path / "red_unused"))
    (tmp_path / "manual").write_text("")

    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 0


def test_main_exits_when_red_flag_present_without_force(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "FORCE", False)
    monkeypatch.setattr(mi, "FLAG_MANUAL", str(tmp_path / "manual_unused"))
    monkeypatch.setattr(mi, "FLAG_RED", str(tmp_path / "red"))
    (tmp_path / "red").write_text("")

    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 0


def test_main_force_bypasses_manual_and_red_flags(mi, tmp_path, monkeypatch):
    """--force ignoruje flagi -> kod idzie dalej do sprawdzenia tapety
    (gdzie i tak zrobi sys.exit(1), bo tapeta nie istnieje) — kod 1, nie
    0, potwierdza że flagi NIE zatrzymały wykonania wcześniej."""
    monkeypatch.setattr(mi, "FORCE", True)
    monkeypatch.setattr(mi, "FLAG_MANUAL", str(tmp_path / "manual"))
    monkeypatch.setattr(mi, "FLAG_RED", str(tmp_path / "red"))
    (tmp_path / "manual").write_text("")
    (tmp_path / "red").write_text("")
    monkeypatch.setattr(mi, "WALLPAPER", str(tmp_path / "missing.jpg"))

    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 1


def test_main_exits_when_wallpaper_missing(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "FORCE", True)
    monkeypatch.setattr(mi, "WALLPAPER", str(tmp_path / "missing.jpg"))

    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 1


def test_main_exits_when_gui_modules_import_error(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "FORCE", True)
    wallpaper = tmp_path / "wallpaper.jpg"
    wallpaper.write_bytes(b"fake")
    monkeypatch.setattr(mi, "WALLPAPER", str(wallpaper))

    # from gui.colors import extract_colors_from_wallpaper -> usunięcie
    # atrybutu ze ŹRÓDŁA powoduje ImportError przy 'from X import Y',
    # bez potrzeby patchowania __import__ globalnie.
    import gui.colors as colors_mod
    monkeypatch.delattr(colors_mod, "extract_colors_from_wallpaper", raising=False)

    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 1


def test_main_exits_when_color_extraction_fails(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "FORCE", True)
    wallpaper = tmp_path / "wallpaper.jpg"
    wallpaper.write_bytes(b"fake")
    monkeypatch.setattr(mi, "WALLPAPER", str(wallpaper))

    import gui.colors as colors_mod
    monkeypatch.setattr(colors_mod, "extract_colors_from_wallpaper", lambda path: None)

    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 1


def test_main_exits_cleanly_when_no_instances(mi, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "FORCE", True)
    wallpaper = tmp_path / "wallpaper.jpg"
    wallpaper.write_bytes(b"fake")
    monkeypatch.setattr(mi, "WALLPAPER", str(wallpaper))

    import gui.colors as colors_mod
    monkeypatch.setattr(colors_mod, "extract_colors_from_wallpaper",
                         lambda path: {"top": "#fff"})
    monkeypatch.setattr(mi, "load_instances", lambda: [])

    with pytest.raises(SystemExit) as exc:
        mi.main()
    assert exc.value.code == 0


# ── main() — pętla per-instancja ─────────────────────────────────────────────

@pytest.fixture
def main_prereqs(mi, tmp_path, monkeypatch):
    """Wspólne warunki wstępne, żeby main() dotarł do pętli instancji:
    FORCE=True, tapeta istnieje, ekstrakcja kolorów się udaje. Każdy test
    dalej konfiguruje load_instances/GlavaInstance/write_colors_to_frag/PID
    pod swój scenariusz. Zwraca gui.colors (do dalszego monkeypatchowania
    write_colors_to_frag z tego samego miejsca)."""
    monkeypatch.setattr(mi, "FORCE", True)
    wallpaper = tmp_path / "wallpaper.jpg"
    wallpaper.write_bytes(b"fake")
    monkeypatch.setattr(mi, "WALLPAPER", str(wallpaper))
    monkeypatch.setattr(mi, "load_gradient_mode", lambda: "rgb")

    import gui.colors as colors_mod
    monkeypatch.setattr(colors_mod, "extract_colors_from_wallpaper",
                         lambda path: {"top": "#111", "mid": "#222", "bottom": "#333"})
    return colors_mod


def test_main_skips_instance_with_missing_directory(mi, main_prereqs, monkeypatch):
    monkeypatch.setattr(mi, "load_instances", lambda: [{"inst_id": 1, "module": "bars"}])

    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "GlavaInstance",
                         lambda inst_id: _FakeInstance(inst_id, exists=False))

    write_calls = []
    monkeypatch.setattr(main_prereqs, "write_colors_to_frag",
                         lambda *a, **kw: write_calls.append(True) or (True, None))

    mi.main()  # katalog nie istnieje -> continue -> pętla kończy się normalnie

    assert write_calls == []


def test_main_continues_when_write_colors_fails(mi, main_prereqs, monkeypatch):
    monkeypatch.setattr(mi, "load_instances", lambda: [{"inst_id": 1, "module": "bars"}])
    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "GlavaInstance", lambda inst_id: _FakeInstance(inst_id))
    monkeypatch.setattr(main_prereqs, "write_colors_to_frag",
                         lambda *a, **kw: (False, "boom"))
    calls = []
    monkeypatch.setattr(mi, "stop_instance", lambda iid: calls.append(("stop", iid)))
    monkeypatch.setattr(mi, "start_instance", lambda iid, xdg: calls.append(("start", iid)))

    mi.main()

    assert calls == []  # błąd zapisu kolorów -> continue, brak restartu


def test_main_skips_restart_when_process_not_running(mi, main_prereqs, monkeypatch):
    monkeypatch.setattr(mi, "load_instances", lambda: [{"inst_id": 1, "module": "bars"}])
    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "GlavaInstance", lambda inst_id: _FakeInstance(inst_id))
    monkeypatch.setattr(main_prereqs, "write_colors_to_frag", lambda *a, **kw: (True, None))
    monkeypatch.setattr(mi, "read_pid", lambda iid: None)
    monkeypatch.setattr(mi, "is_pid_running", lambda pid: False)
    calls = []
    monkeypatch.setattr(mi, "stop_instance", lambda iid: calls.append(("stop", iid)))
    monkeypatch.setattr(mi, "start_instance", lambda iid, xdg: calls.append(("start", iid)))

    mi.main()

    assert calls == []  # proces nie działa -> kolory zapisane, ale bez restartu


def test_main_restarts_instance_when_process_running(mi, main_prereqs, monkeypatch):
    monkeypatch.setattr(mi, "load_instances", lambda: [{"inst_id": 1, "module": "bars"}])
    import gui.instance as instance_mod
    fake_inst = _FakeInstance(1, xdg_dir="/tmp/xdg-1")
    monkeypatch.setattr(instance_mod, "GlavaInstance", lambda inst_id: fake_inst)
    monkeypatch.setattr(main_prereqs, "write_colors_to_frag", lambda *a, **kw: (True, None))
    monkeypatch.setattr(mi, "read_pid", lambda iid: 555)
    monkeypatch.setattr(mi, "is_pid_running", lambda pid: True)
    monkeypatch.setattr(mi.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(mi, "stop_instance", lambda iid: calls.append(("stop", iid)))
    monkeypatch.setattr(mi, "start_instance",
                         lambda iid, xdg: calls.append(("start", iid, xdg)))

    mi.main()

    assert calls == [("stop", 1), ("start", 1, "/tmp/xdg-1")]


def test_main_defaults_missing_module_key_to_graph(mi, main_prereqs, monkeypatch):
    """entry.get('module', 'graph') -> brak klucza 'module' we wpisie ->
    domyślny moduł 'graph'."""
    monkeypatch.setattr(mi, "load_instances", lambda: [{"inst_id": 1}])  # brak "module"
    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "GlavaInstance", lambda inst_id: _FakeInstance(inst_id))
    write_calls = []
    monkeypatch.setattr(
        main_prereqs, "write_colors_to_frag",
        lambda module, *a, **kw: write_calls.append(module) or (True, None))
    monkeypatch.setattr(mi, "read_pid", lambda iid: None)
    monkeypatch.setattr(mi, "is_pid_running", lambda pid: False)

    mi.main()

    assert write_calls == ["graph"]


def test_main_passes_gradient_mode_and_colors_to_write_colors_to_frag(
        mi, main_prereqs, monkeypatch):
    monkeypatch.setattr(mi, "load_gradient_mode", lambda: "hsv")
    monkeypatch.setattr(main_prereqs, "extract_colors_from_wallpaper",
                         lambda path: {"top": "#abc"})
    monkeypatch.setattr(mi, "load_instances", lambda: [{"inst_id": 1, "module": "wave"}])
    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "GlavaInstance", lambda inst_id: _FakeInstance(inst_id))

    captured = {}

    def fake_write(module, colors, gradient_mode, tmpl_path=None, live_path=None):
        captured.update(module=module, colors=colors, gradient_mode=gradient_mode)
        return True, None

    monkeypatch.setattr(main_prereqs, "write_colors_to_frag", fake_write)
    monkeypatch.setattr(mi, "read_pid", lambda iid: None)
    monkeypatch.setattr(mi, "is_pid_running", lambda pid: False)

    mi.main()

    assert captured == {"module": "wave", "colors": {"top": "#abc"}, "gradient_mode": "hsv"}


# ── main() — czyszczenie flag na końcu ──────────────────────────────────────

def test_main_removes_manual_and_red_flags_on_successful_run(
        mi, main_prereqs, tmp_path, monkeypatch):
    manual = tmp_path / "manual"
    red = tmp_path / "red"
    manual.write_text("")
    red.write_text("")
    monkeypatch.setattr(mi, "FLAG_MANUAL", str(manual))
    monkeypatch.setattr(mi, "FLAG_RED", str(red))
    monkeypatch.setattr(mi, "load_instances", lambda: [{"inst_id": 1, "module": "bars"}])
    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "GlavaInstance", lambda inst_id: _FakeInstance(inst_id))
    monkeypatch.setattr(main_prereqs, "write_colors_to_frag", lambda *a, **kw: (True, None))
    monkeypatch.setattr(mi, "read_pid", lambda iid: None)
    monkeypatch.setattr(mi, "is_pid_running", lambda pid: False)

    mi.main()  # przechodzi normalnie do końca (brak sys.exit po pętli)

    assert not manual.exists()
    assert not red.exists()


def test_main_flag_cleanup_swallows_missing_files(mi, main_prereqs, tmp_path, monkeypatch):
    monkeypatch.setattr(mi, "FLAG_MANUAL", str(tmp_path / "no_manual"))
    monkeypatch.setattr(mi, "FLAG_RED", str(tmp_path / "no_red"))
    monkeypatch.setattr(mi, "load_instances", lambda: [{"inst_id": 1, "module": "bars"}])
    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "GlavaInstance", lambda inst_id: _FakeInstance(inst_id))
    monkeypatch.setattr(main_prereqs, "write_colors_to_frag", lambda *a, **kw: (True, None))
    monkeypatch.setattr(mi, "read_pid", lambda iid: None)
    monkeypatch.setattr(mi, "is_pid_running", lambda pid: False)

    mi.main()  # nie powinno crashować mimo braku plików flag (FileNotFoundError)
