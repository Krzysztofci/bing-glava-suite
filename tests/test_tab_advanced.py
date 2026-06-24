# =============================================================================
# tests/test_tab_advanced.py
# Testy logic-coverage dla gui/tab_advanced.py.
#
# Zasady (zgodne z konwencją ustaloną dla tab_main.py):
# - Plik samodzielny: własne Fake* (nie współdzielone z test_tab_main.py).
# - _build_* i widget-factory (_combo_row) są ŚWIADOMIE pominięte — to czysty
#   GUI-layout, nietestowany w tym projekcie (patrz: tab_main).
# - Lokalne importy wewnątrz funkcji (np. `from .glava import X` w _do(),
#   `import threading`/`import time` w _restart_all/_do) patchujemy na ŹRÓDLE
#   (gui.glava / threading / time), nie na tab_advanced_mod.
# - Top-level importy (`from .core import RC_GLSL`, `from .geometry import
#   get_screen_info`) patchujemy NA tab_advanced_mod (bo to import nazwy,
#   nie atrybutu modułu — `from X import Y` tworzy własne wiązanie Y w
#   przestrzeni nazw modułu importującego).
# - Realne wątki podstawiamy FakeThread wykonującym target() synchronicznie
#   (to przypadkowy szczegół implementacji _restart_all, nie test wyścigu).
# =============================================================================

import os
import pytest

import gui.tab_advanced as tab_advanced_mod


# ── Fake'i ────────────────────────────────────────────────────────────────────

class FakeT:
    """Stub słownika tłumaczeń — .get(key, default) zawsze zwraca default,
    żeby testy nie zależały od treści JSON-a z tłumaczeniami."""
    def get(self, key, default=""):
        return default


class FakeStringVar:
    def __init__(self, value=""):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class FakeBooleanVar:
    def __init__(self, value=False):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class FakeRoot:
    """after()/after_cancel() wykonują się SYNCHRONICZNIE i NATYCHMIAST —
    upraszcza testowanie debounce/restart bez realnego event loopa Tk."""
    def __init__(self):
        self.after_calls = []
        self.after_cancel_calls = []
        self.destroy_calls = 0

    def after(self, delay, fn):
        self.after_calls.append((delay, fn))
        fn()
        return f"job-{len(self.after_calls)}"

    def after_cancel(self, job):
        self.after_cancel_calls.append(job)

    def destroy(self):
        self.destroy_calls += 1


class FakeInstance:
    """Minimalna instancja GlavaInstance — potrzebujemy tylko .rc_glsl."""
    def __init__(self, rc_glsl):
        self.rc_glsl = rc_glsl


class FakeThread:
    """Wykonuje target() SYNCHRONICZNIE w wątku wywołującym — wątek jest tu
    przypadkowym szczegółem implementacji _restart_all, nie testujemy
    warunków wyścigu (to byłby odrębny test_*_race.py)."""
    def __init__(self, target, daemon=True):
        self._target = target

    def start(self):
        self._target()


class FakeApp:
    def __init__(self):
        self.T = FakeT()
        self.gui_conf = {}
        self._resize_after = None
        self.root = FakeRoot()
        self.save_window_state_calls = 0
        self.save_gui_conf_calls = 0
        self._restart = False
        self.active_module = "bars"
        self.update_status_calls = 0
        self.on_expert_toggle_calls = 0

    def _save_window_state(self):
        self.save_window_state_calls += 1

    def _save_gui_conf(self):
        self.save_gui_conf_calls += 1

    def update_status(self):
        self.update_status_calls += 1

    def _on_expert_toggle(self):
        self.on_expert_toggle_calls += 1


@pytest.fixture
def fake_app():
    return FakeApp()


@pytest.fixture
def rc_path(tmp_path, monkeypatch):
    """Patchuje globalny RC_GLSL (zaimportowany jako nazwa w tab_advanced_mod)
    na tymczasowy plik — żeby testy nie dotykały realnej ścieżki userowej."""
    p = str(tmp_path / "rc.glsl")
    monkeypatch.setattr(tab_advanced_mod, "RC_GLSL", p)
    return p


def _make_tab(fake_app):
    return tab_advanced_mod.TabAdvanced(parent=object(), app=fake_app)


# ── build_tab_advanced — module-level entry point ───────────────────────────

def test_build_tab_advanced_creates_instance_and_calls_build(fake_app, monkeypatch):
    build_calls = []
    monkeypatch.setattr(tab_advanced_mod.TabAdvanced, "build",
                         lambda self: build_calls.append(self))
    parent = object()

    tab_advanced_mod.build_tab_advanced(parent, fake_app)

    assert len(build_calls) == 1
    tab = build_calls[0]
    assert isinstance(tab, tab_advanced_mod.TabAdvanced)
    assert tab.parent is parent
    assert tab.app is fake_app


# ── _apply_theme ─────────────────────────────────────────────────────────────

def test_apply_theme_saves_state_and_restarts_without_pending_resize(fake_app):
    tab = _make_tab(fake_app)
    tab._theme_var = FakeStringVar("forest-light")
    fake_app._resize_after = None

    tab._apply_theme()

    assert fake_app.gui_conf["theme"] == "forest-light"
    assert fake_app.root.after_cancel_calls == []  # brak pending resize -> brak cancel
    assert fake_app.save_window_state_calls == 1
    assert fake_app.save_gui_conf_calls == 1
    assert fake_app._restart is True
    assert fake_app.root.destroy_calls == 1


def test_apply_theme_cancels_pending_resize_job_before_restart(fake_app):
    """Jeśli debounced zapis pozycji okna jeszcze czeka (_resize_after),
    _apply_theme musi go anulować i wyczyścić, zanim zniszczy okno —
    inaczej callback strzeli już po destroy()."""
    tab = _make_tab(fake_app)
    tab._theme_var = FakeStringVar("forest-dark")
    fake_app._resize_after = "PENDING_RESIZE_JOB"

    tab._apply_theme()

    assert fake_app.root.after_cancel_calls == ["PENDING_RESIZE_JOB"]
    assert fake_app._resize_after is None


# ── _rc_glsl ──────────────────────────────────────────────────────────────────

def test_rc_glsl_uses_app_active_rc_glsl_when_available(fake_app):
    tab = _make_tab(fake_app)
    fake_app.get_active_rc_glsl = lambda: "/instance/specific/rc.glsl"

    assert tab._rc_glsl() == "/instance/specific/rc.glsl"


def test_rc_glsl_falls_back_to_global_when_app_returns_falsy(fake_app, rc_path):
    tab = _make_tab(fake_app)
    fake_app.get_active_rc_glsl = lambda: None  # np. brak aktywnej instancji

    assert tab._rc_glsl() == rc_path


def test_rc_glsl_falls_back_to_global_when_app_lacks_method(fake_app, rc_path):
    tab = _make_tab(fake_app)
    assert not hasattr(fake_app, "get_active_rc_glsl")

    assert tab._rc_glsl() == rc_path


# ── _read_request_bool / _read_request_int ──────────────────────────────────

def test_read_request_bool_returns_false_when_file_missing(fake_app, rc_path):
    tab = _make_tab(fake_app)
    assert tab._read_request_bool("setmirror") is False


def test_read_request_bool_parses_true(fake_app, rc_path):
    tab = _make_tab(fake_app)
    with open(rc_path, "w") as f:
        f.write("#request setmirror true\n")
    assert tab._read_request_bool("setmirror") is True


def test_read_request_bool_parses_false(fake_app, rc_path):
    tab = _make_tab(fake_app)
    with open(rc_path, "w") as f:
        f.write("#request setmirror false\n")
    assert tab._read_request_bool("setmirror") is False


def test_read_request_bool_returns_false_when_key_absent(fake_app, rc_path):
    tab = _make_tab(fake_app)
    with open(rc_path, "w") as f:
        f.write("#request setinterpolate true\n")
    assert tab._read_request_bool("setmirror") is False


def test_read_request_int_returns_default_when_file_missing(fake_app, rc_path):
    tab = _make_tab(fake_app)
    assert tab._read_request_int("setbufsize", 4096) == 4096


def test_read_request_int_parses_value_from_file(fake_app, rc_path):
    tab = _make_tab(fake_app)
    with open(rc_path, "w") as f:
        f.write("#request setbufsize 8192\n")
    assert tab._read_request_int("setbufsize", 4096) == 8192


def test_read_request_int_returns_default_when_key_absent(fake_app, rc_path):
    tab = _make_tab(fake_app)
    with open(rc_path, "w") as f:
        f.write("#request setsamplerate 44100\n")
    assert tab._read_request_int("setbufsize", 4096) == 4096


# ── _write_request_to ────────────────────────────────────────────────────────

def test_write_request_to_noop_when_file_missing(fake_app, tmp_path):
    tab = _make_tab(fake_app)
    rc = str(tmp_path / "nope.glsl")

    tab._write_request_to(rc, "setbufsize", 4096)

    assert not os.path.exists(rc)


def test_write_request_to_replaces_existing_key(fake_app, tmp_path):
    tab = _make_tab(fake_app)
    rc = tmp_path / "rc.glsl"
    rc.write_text("#request setbufsize 1024\n#request setsamplerate 44100\n")

    tab._write_request_to(str(rc), "setbufsize", 8192)

    content = rc.read_text()
    assert "#request setbufsize 8192\n" in content
    assert "#request setbufsize 1024" not in content
    assert "#request setsamplerate 44100\n" in content  # nie naruszone


def test_write_request_to_appends_when_key_absent_and_file_ends_with_newline(
        fake_app, tmp_path):
    tab = _make_tab(fake_app)
    rc = tmp_path / "rc.glsl"
    rc.write_text("#request setsamplerate 44100\n")

    tab._write_request_to(str(rc), "setbufsize", 8192)

    content = rc.read_text()
    assert content == "#request setsamplerate 44100\n#request setbufsize 8192\n"


def test_write_request_to_appends_newline_first_when_file_lacks_trailing_newline(
        fake_app, tmp_path):
    tab = _make_tab(fake_app)
    rc = tmp_path / "rc.glsl"
    rc.write_text("#request setsamplerate 44100")  # bez \n na końcu

    tab._write_request_to(str(rc), "setbufsize", 8192)

    content = rc.read_text()
    assert content == "#request setsamplerate 44100\n#request setbufsize 8192\n"


# ── _write_request ───────────────────────────────────────────────────────────

def test_write_request_writes_to_all_instances_when_present(fake_app, tmp_path):
    tab = _make_tab(fake_app)
    rc0 = tmp_path / "inst0_rc.glsl"
    rc1 = tmp_path / "inst1_rc.glsl"
    rc0.write_text("#request setbufsize 1024\n")
    rc1.write_text("#request setbufsize 1024\n")
    fake_app.instances = {0: FakeInstance(str(rc0)), 1: FakeInstance(str(rc1))}

    tab._write_request("setbufsize", 8192)

    assert "#request setbufsize 8192\n" in rc0.read_text()
    assert "#request setbufsize 8192\n" in rc1.read_text()


def test_write_request_writes_to_single_global_rc_when_no_instances(
        fake_app, rc_path):
    tab = _make_tab(fake_app)
    with open(rc_path, "w") as f:
        f.write("#request setbufsize 1024\n")
    assert not hasattr(fake_app, "instances")

    tab._write_request("setbufsize", 8192)

    with open(rc_path) as f:
        assert "#request setbufsize 8192\n" in f.read()


# ── _write_bool_rc ────────────────────────────────────────────────────────────

def test_write_bool_rc_converts_true_to_string(fake_app, rc_path, monkeypatch):
    tab = _make_tab(fake_app)
    import gui.glava as glava_mod
    monkeypatch.setattr(glava_mod, "glava_restart", lambda *a, **kw: None)
    captured = []
    monkeypatch.setattr(tab, "_debounce_request",
                         lambda key, val: captured.append((key, val)))

    tab._write_bool_rc("setmirror", FakeBooleanVar(True))

    assert captured == [("setmirror", "true")]


def test_write_bool_rc_converts_false_to_string(fake_app, rc_path, monkeypatch):
    tab = _make_tab(fake_app)
    captured = []
    monkeypatch.setattr(tab, "_debounce_request",
                         lambda key, val: captured.append((key, val)))

    tab._write_bool_rc("setmirror", FakeBooleanVar(False))

    assert captured == [("setmirror", "false")]


# ── _debounce_request — anulowanie poprzedniego joba ────────────────────────

def test_debounce_request_writes_value_before_scheduling_restart(
        fake_app, rc_path, monkeypatch):
    tab = _make_tab(fake_app)
    with open(rc_path, "w") as f:
        f.write("#request setbufsize 1024\n")
    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, after_fn=None: restart_calls.append(module))

    tab._debounce_request("setbufsize", 8192)

    with open(rc_path) as f:
        assert "#request setbufsize 8192\n" in f.read()
    assert restart_calls == ["bars"]  # legacy branch, brak instances/restart_active_instance


def test_debounce_request_cancels_existing_rjob_before_scheduling_new(
        fake_app, rc_path, monkeypatch):
    tab = _make_tab(fake_app)
    import gui.glava as glava_mod
    monkeypatch.setattr(glava_mod, "glava_restart", lambda *a, **kw: None)
    tab._rjob = "OLD_JOB"

    tab._debounce_request("setbufsize", 8192)

    assert fake_app.root.after_cancel_calls == ["OLD_JOB"]


def test_debounce_request_swallows_after_cancel_exception(
        fake_app, rc_path, monkeypatch):
    tab = _make_tab(fake_app)
    import gui.glava as glava_mod
    monkeypatch.setattr(glava_mod, "glava_restart", lambda *a, **kw: None)
    tab._rjob = "STALE_JOB"

    def broken_after_cancel(job):
        raise RuntimeError("nieaktualny identyfikator joba po resize")
    fake_app.root.after_cancel = broken_after_cancel

    tab._debounce_request("setbufsize", 8192)  # nie powinno podnieść wyjątku


def test_debounce_request_first_call_has_no_rjob_to_cancel(
        fake_app, rc_path, monkeypatch):
    tab = _make_tab(fake_app)
    import gui.glava as glava_mod
    monkeypatch.setattr(glava_mod, "glava_restart", lambda *a, **kw: None)
    assert not hasattr(tab, "_rjob")

    tab._debounce_request("setbufsize", 8192)

    assert fake_app.root.after_cancel_calls == []


# ── _debounce_request — gałąź legacy (brak instances/restart_active_instance) ─

def test_debounce_request_legacy_branch_calls_glava_restart_with_active_module(
        fake_app, rc_path, monkeypatch):
    tab = _make_tab(fake_app)
    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, after_fn=None: restart_calls.append((module, after_fn)))

    tab._debounce_request("setsamplerate", 44100)

    assert len(restart_calls) == 1
    module, after_fn = restart_calls[0]
    assert module == "bars"
    assert after_fn == fake_app.update_status


# ── _debounce_request — gałąź restart_active_instance (multi-instance GUI) ──

def test_debounce_request_uses_restart_active_instance_when_available(
        fake_app, rc_path, monkeypatch):
    tab = _make_tab(fake_app)
    restart_calls = []
    fake_app.restart_active_instance = lambda after_fn=None: restart_calls.append(after_fn)

    tab._debounce_request("setsamplerate", 44100)

    assert len(restart_calls) == 1
    assert restart_calls[0] == fake_app.update_status


# ── _debounce_request — gałąź wielo-instancyjna (app.instances + processes) ──

def test_debounce_request_multi_instance_restarts_all_and_updates_status(
        fake_app, rc_path, monkeypatch, tmp_path):
    """Branch: app.instances + app.processes obecne -> _restart_all buduje
    wątek per-instancja (tu zsynchronizowany przez FakeThread), zatrzymuje
    stary proces, startuje nowy, aktualizuje processes[iid] i zeruje flagę
    _restart_in_progress po każdym restarcie."""
    tab = _make_tab(fake_app)
    inst0 = FakeInstance(str(tmp_path / "inst0_rc.glsl"))
    inst1 = FakeInstance(str(tmp_path / "inst1_rc.glsl"))
    fake_app.instances = {0: inst0, 1: inst1}
    fake_app.processes = {0: "OLD_PROC_0", 1: "OLD_PROC_1"}

    import threading
    monkeypatch.setattr(threading, "Thread", FakeThread)
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)

    import gui.glava as glava_mod
    stop_calls = []
    start_calls = []
    monkeypatch.setattr(glava_mod, "glava_stop_instance",
                         lambda proc: stop_calls.append(proc))
    counter = {"n": 0}

    def fake_glava_start(instance):
        start_calls.append(instance)
        counter["n"] += 1
        return f"NEW_PROC_{counter['n']}"
    monkeypatch.setattr(glava_mod, "glava_start", fake_glava_start)

    tab._debounce_request("setbufsize", 4096)

    assert stop_calls == ["OLD_PROC_0", "OLD_PROC_1"]
    assert start_calls == [inst0, inst1]
    assert fake_app.processes[0] == "NEW_PROC_1"
    assert fake_app.processes[1] == "NEW_PROC_2"
    assert fake_app._restart_in_progress == {0: False, 1: False}
    assert fake_app.update_status_calls == 2


def test_debounce_request_multi_instance_initializes_restart_in_progress_dict(
        fake_app, rc_path, monkeypatch, tmp_path):
    tab = _make_tab(fake_app)
    inst0 = FakeInstance(str(tmp_path / "inst0_rc.glsl"))
    fake_app.instances = {0: inst0}
    fake_app.processes = {0: "OLD_PROC"}
    assert not hasattr(fake_app, "_restart_in_progress")

    import threading
    monkeypatch.setattr(threading, "Thread", FakeThread)
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    import gui.glava as glava_mod
    monkeypatch.setattr(glava_mod, "glava_stop_instance", lambda proc: None)
    monkeypatch.setattr(glava_mod, "glava_start", lambda instance: "NEW_PROC")

    tab._debounce_request("setbufsize", 4096)

    assert fake_app._restart_in_progress == {0: False}


def test_debounce_request_multi_instance_skips_everything_when_any_already_restarting(
        fake_app, rc_path, monkeypatch, tmp_path):
    """ODKRYCIE: `if any(rip.values()): return` w _restart_all przerywa
    CAŁĄ funkcję, jeśli JAKAKOLWIEK instancja jest w trakcie restartu —
    nawet instancje, które same nie są aktywnie restartowane, są wtedy
    pominięte. To czyni wewnętrzny `if self._restart_in_progress.get(iid):
    continue` w pętli for martwym kodem w normalnym przepływie (nie da się
    do niego dojść, bo guard na starcie funkcji już go wyłapuje wcześniej) —
    wart potwierdzenia/sprzątnięcia, podobnie jak wcześniejsze martwe gałęzie
    w glava.py / tab_main.py."""
    tab = _make_tab(fake_app)
    inst0 = FakeInstance(str(tmp_path / "inst0_rc.glsl"))
    inst1 = FakeInstance(str(tmp_path / "inst1_rc.glsl"))
    fake_app.instances = {0: inst0, 1: inst1}
    fake_app.processes = {0: "OLD_PROC_0", 1: "OLD_PROC_1"}
    fake_app._restart_in_progress = {0: True}  # instancja 0 już się restartuje

    import threading
    monkeypatch.setattr(threading, "Thread", FakeThread)
    import gui.glava as glava_mod
    stop_calls = []
    monkeypatch.setattr(glava_mod, "glava_stop_instance",
                         lambda proc: stop_calls.append(proc))
    monkeypatch.setattr(glava_mod, "glava_start", lambda instance: "NEW_PROC")

    tab._debounce_request("setbufsize", 4096)

    assert stop_calls == []  # zero restartów — blokada na poziomie całej funkcji
    assert fake_app.processes == {0: "OLD_PROC_0", 1: "OLD_PROC_1"}
    assert fake_app.update_status_calls == 0


# ── _show_logs ────────────────────────────────────────────────────────────────

def test_show_logs_shows_error_when_log_file_missing(fake_app, monkeypatch, tmp_path):
    tab = _make_tab(fake_app)
    monkeypatch.setattr(os.path, "expanduser",
                         lambda p: str(tmp_path) if p == "~" else p)
    popen_calls = []
    monkeypatch.setattr(tab_advanced_mod.subprocess, "Popen",
                         lambda args: popen_calls.append(args))
    info_calls = []
    monkeypatch.setattr(tab_advanced_mod.messagebox, "showinfo",
                         lambda title, msg: info_calls.append((title, msg)))

    tab._show_logs()

    assert popen_calls == []
    assert len(info_calls) == 1
    assert "glava-color-daemon.log" in info_calls[0][1]


def test_show_logs_opens_xterm_when_log_exists(fake_app, monkeypatch, tmp_path):
    tab = _make_tab(fake_app)
    monkeypatch.setattr(os.path, "expanduser",
                         lambda p: str(tmp_path) if p == "~" else p)
    log_dir = tmp_path / ".local" / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "glava-color-daemon.log").write_text("linia 1\n")

    popen_calls = []
    monkeypatch.setattr(tab_advanced_mod.subprocess, "Popen",
                         lambda args: popen_calls.append(args))
    info_calls = []
    monkeypatch.setattr(tab_advanced_mod.messagebox, "showinfo",
                         lambda title, msg: info_calls.append((title, msg)))

    tab._show_logs()

    assert len(popen_calls) == 1
    assert popen_calls[0][0] == "xterm"
    assert info_calls == []


def test_show_logs_falls_back_to_x_terminal_emulator_when_xterm_missing(
        fake_app, monkeypatch, tmp_path):
    tab = _make_tab(fake_app)
    monkeypatch.setattr(os.path, "expanduser",
                         lambda p: str(tmp_path) if p == "~" else p)
    log_dir = tmp_path / ".local" / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "glava-color-daemon.log").write_text("linia 1\n")

    popen_calls = []

    def fake_popen(args):
        popen_calls.append(args)
        if args[0] == "xterm":
            raise FileNotFoundError("xterm nie zainstalowany")
        return "PROC_OK"
    monkeypatch.setattr(tab_advanced_mod.subprocess, "Popen", fake_popen)
    info_calls = []
    monkeypatch.setattr(tab_advanced_mod.messagebox, "showinfo",
                         lambda title, msg: info_calls.append((title, msg)))

    tab._show_logs()

    assert [c[0] for c in popen_calls] == ["xterm", "x-terminal-emulator"]
    assert info_calls == []


def test_show_logs_falls_back_to_inline_text_when_no_terminal_available(
        fake_app, monkeypatch, tmp_path):
    tab = _make_tab(fake_app)
    monkeypatch.setattr(os.path, "expanduser",
                         lambda p: str(tmp_path) if p == "~" else p)
    log_dir = tmp_path / ".local" / "logs"
    log_dir.mkdir(parents=True)
    log_file = log_dir / "glava-color-daemon.log"
    log_file.write_text("linia A\nlinia B\nlinia C\n")

    def fake_popen(args):
        if args[0] == "xterm":
            raise FileNotFoundError("xterm nie zainstalowany")
        raise RuntimeError("brak żadnego emulatora terminala")
    monkeypatch.setattr(tab_advanced_mod.subprocess, "Popen", fake_popen)
    info_calls = []
    monkeypatch.setattr(tab_advanced_mod.messagebox, "showinfo",
                         lambda title, msg: info_calls.append((title, msg)))

    tab._show_logs()

    assert len(info_calls) == 1
    title, msg = info_calls[0]
    assert "linia A" in msg and "linia C" in msg


# ── _on_expert_toggle ─────────────────────────────────────────────────────────

def test_on_expert_toggle_delegates_to_app(fake_app):
    tab = _make_tab(fake_app)
    tab._on_expert_toggle()
    assert fake_app.on_expert_toggle_calls == 1


# ── _test_strut ───────────────────────────────────────────────────────────────

def test_test_strut_shows_screen_info_message(fake_app, monkeypatch):
    tab = _make_tab(fake_app)
    monkeypatch.setattr(tab_advanced_mod, "get_screen_info",
                         lambda: (1920, 1080, 1040, 0, 40, 0, 0))
    info_calls = []
    monkeypatch.setattr(tab_advanced_mod.messagebox, "showinfo",
                         lambda title, msg: info_calls.append((title, msg)))

    tab._test_strut()

    assert len(info_calls) == 1
    title, msg = info_calls[0]
    assert "1920" in msg and "1080" in msg
    assert "40" in msg  # bottom_reserved


# ── _expert ───────────────────────────────────────────────────────────────────

def test_expert_returns_false_when_app_has_no_expert_mode(fake_app):
    tab = _make_tab(fake_app)
    assert not hasattr(fake_app, "expert_mode")
    assert tab._expert() is False


def test_expert_returns_true_when_expert_mode_enabled(fake_app):
    tab = _make_tab(fake_app)
    fake_app.expert_mode = FakeBooleanVar(True)
    assert tab._expert() is True


def test_expert_returns_false_when_expert_mode_disabled(fake_app):
    tab = _make_tab(fake_app)
    fake_app.expert_mode = FakeBooleanVar(False)
    assert tab._expert() is False


# ── _show_license_text ───────────────────────────────────────────────────────

def test_show_license_text_for_license_file(fake_app, monkeypatch):
    tab = _make_tab(fake_app)
    info_calls = []
    monkeypatch.setattr(tab_advanced_mod.messagebox, "showinfo",
                         lambda title, msg: info_calls.append((title, msg)))

    tab._show_license_text("LICENSE")

    assert len(info_calls) == 1
    title, msg = info_calls[0]
    assert title == "LICENSE"
    assert "MIT License" in msg


def test_show_license_text_for_third_party_credits(fake_app, monkeypatch):
    tab = _make_tab(fake_app)
    info_calls = []
    monkeypatch.setattr(tab_advanced_mod.messagebox, "showinfo",
                         lambda title, msg: info_calls.append((title, msg)))

    tab._show_license_text("CREDITS")

    assert len(info_calls) == 1
    title, msg = info_calls[0]
    assert title == "CREDITS"
    assert "GLava (GPLv3)" in msg
    assert "Forest-ttk-theme" in msg
