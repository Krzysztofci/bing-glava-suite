# =============================================================================
# tests/test_toggle_race.py
# Testy race condition przy szybkim toggle on/off GLava.
#
# Weryfikują że _on_glava_toggle:
# - nie mnoży procesów przy szybkich kliknięciach
# - nie zostawia osieroconych procesów po off
# - GUI śledzi dokładnie tyle procesów ile instancji
# =============================================================================
import pytest
import os
import time
import threading
import subprocess
import shutil


# ── Fake infrastructure ───────────────────────────────────────────────────────

class FakeRoot:
    """Minimalny mock tk.Tk — obsługuje after() i after_cancel()."""
    def __init__(self):
        self._jobs = {}
        self._job_counter = 0
        self._lock = threading.Lock()

    def after(self, ms, fn, *args):
        with self._lock:
            jid = self._job_counter
            self._job_counter += 1
            self._jobs[jid] = (fn, args)
        return jid

    def after_cancel(self, jid):
        with self._lock:
            self._jobs.pop(jid, None)


class FakeInstance:
    def __init__(self, inst_id, glava_dir):
        self.inst_id  = inst_id
        self.xdg_dir  = glava_dir
        self.glava_dir = glava_dir
        self.conf_dir  = glava_dir

    def module_glsl(self, mod): return os.path.join(self.glava_dir, f"{mod}.glsl")
    @property
    def rc_glsl(self):    return os.path.join(self.glava_dir, "rc.glsl")
    @property
    def smooth_glsl(self): return os.path.join(self.glava_dir, "smooth_parameters.glsl")


class ToggleApp:
    """
    Implementacja _on_glava_toggle z glava-gui.py uruchamiana bez tkinter.
    glava_restart_instance zastąpiony mockiem startującym 'sleep 10'.
    """
    def __init__(self, root, instances, processes, disable_flag, monkeypatch):
        self.root = root
        self.instances = instances
        self.processes = processes
        self._inst_modules = {iid: "bars" for iid in instances}
        self.active_module = "bars"
        self._active_inst_id = next(iter(instances))
        self.active_instance = instances[self._active_inst_id]
        self._toggle_in_progress = False
        self._started_procs = []
        self._started_lock = threading.Lock()

        class _BoolVar:
            def __init__(self): self._v = False
            def get(self): return self._v
            def set(self, v): self._v = v
        self.glava_enabled_var = _BoolVar()

        # Mock glava_restart_instance — startuje sleep 10 zamiast glava
        import gui.glava as glava_mod
        import gui.core as core_mod

        def mock_restart(instance, module, proc=None, after_fn=None,
                         delay_ms=500, extra_flags=None, env=None):
            from gui.glava import glava_stop_instance, _write_rc_module
            _write_rc_module(module, rc_path=instance.rc_glsl)
            glava_stop_instance(proc)
            def _do():
                time.sleep(0.05)
                p = subprocess.Popen(["sleep", "10"],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                with self._started_lock:
                    self._started_procs.append(p)
                if after_fn:
                    after_fn(p)
            threading.Thread(target=_do, daemon=True).start()

        monkeypatch.setattr(glava_mod, "glava_restart_instance", mock_restart)
        monkeypatch.setattr(core_mod, "GLAVA_DISABLE_FLAG", disable_flag)

    def update_status(self):
        pass

    def _on_glava_toggle(self):
        """Dokładna kopia z GlavaGUI._on_glava_toggle."""
        import gui.core as core_mod
        from gui.glava import glava_stop_instance, glava_restart_instance, clear_pid
        import subprocess as _sp

        GLAVA_DISABLE_FLAG = core_mod.GLAVA_DISABLE_FLAG

        if getattr(self, "_toggle_in_progress", False):
            return
        self._toggle_in_progress = True

        enabled = self.glava_enabled_var.get()
        if enabled:
            try:
                os.remove(GLAVA_DISABLE_FLAG)
            except FileNotFoundError:
                pass
            inst_count = [len(self.instances)]
            _lock = threading.Lock()
            for iid, inst in self.instances.items():
                module = self._inst_modules.get(iid, self.active_module)
                proc   = self.processes.get(iid)
                self.processes[iid] = None
                def _after(new_proc, _iid=iid):
                    self.processes[_iid] = new_proc
                    self.root.after(0, self.update_status)
                    with _lock:
                        inst_count[0] -= 1
                        if inst_count[0] == 0:
                            self._toggle_in_progress = False
                glava_restart_instance(instance=inst, module=module,
                                       proc=proc, after_fn=_after)
        else:
            os.makedirs(os.path.dirname(GLAVA_DISABLE_FLAG), exist_ok=True)
            open(GLAVA_DISABLE_FLAG, "w").close()
            for iid in list(self.processes.keys()):
                proc = self.processes.pop(iid, None)
                glava_stop_instance(proc)
                clear_pid(iid)
            _sp.run(["pkill", "-x", "glava"], capture_output=True)
            self._toggle_in_progress = False
            self.root.after(500, self.update_status)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def app(tmp_path, monkeypatch):
    from gui import glava as glava_mod
    from gui import instance as inst_mod
    monkeypatch.setattr(glava_mod, "_PID_DIR", str(tmp_path / "pids"))
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))
    os.makedirs(str(tmp_path / "pids"))

    glava_dir = str(tmp_path / "glava")
    os.makedirs(glava_dir)
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config', 'rc.glsl')
    shutil.copy2(src, os.path.join(glava_dir, 'rc.glsl'))

    instances = {0: FakeInstance(0, glava_dir)}
    processes = {0: None}
    disable_flag = str(tmp_path / "glava_disabled")
    root = FakeRoot()

    a = ToggleApp(root, instances, processes, disable_flag, monkeypatch)
    yield a

    for p in a._started_procs:
        try:
            p.kill()
            p.wait(timeout=2)
        except Exception:
            pass


# ── Testy ─────────────────────────────────────────────────────────────────────

def test_single_toggle_on_starts_one_process(app):
    """Jedno kliknięcie on startuje dokładnie 1 proces."""
    app.glava_enabled_var.set(True)
    app._on_glava_toggle()
    time.sleep(0.2)
    assert len(app._started_procs) == 1

def test_rapid_on_blocked(app):
    """Szybkie on→on→on startuje tylko 1 proces — blokada działa."""
    app.glava_enabled_var.set(True)
    app._on_glava_toggle()
    app._on_glava_toggle()
    app._on_glava_toggle()
    time.sleep(0.2)
    assert len(app._started_procs) == 1

def test_on_off_no_orphans(app):
    """on→(czekaj)→off nie zostawia osieroconych procesów."""
    app.glava_enabled_var.set(True)
    app._on_glava_toggle()
    time.sleep(0.2)
    app.glava_enabled_var.set(False)
    app._on_glava_toggle()
    time.sleep(0.1)
    live = [p for p in app._started_procs if p.poll() is None]
    assert len(live) == 0

def test_rapid_on_off_on_no_orphans(app):
    """Szybkie on→off→on podczas startu nie zostawia procesów poza kontrolą."""
    app.glava_enabled_var.set(True)
    app._on_glava_toggle()       # wątek startuje
    time.sleep(0.02)             # wątek w trakcie sleep(0.05)
    app.glava_enabled_var.set(False)
    app._on_glava_toggle()       # zablokowane — _toggle_in_progress=True
    time.sleep(0.2)
    # Po zwolnieniu blokady — dokładnie 1 proc śledzony przez GUI
    tracked = sum(1 for p in app.processes.values() if p is not None)
    live    = sum(1 for p in app._started_procs if p.poll() is None)
    assert tracked == live

def test_flag_released_after_on(app):
    """Flaga _toggle_in_progress zwalniana po zakończeniu startu."""
    app.glava_enabled_var.set(True)
    app._on_glava_toggle()
    assert app._toggle_in_progress == True
    time.sleep(0.2)
    assert app._toggle_in_progress == False

def test_flag_released_after_off(app):
    """Flaga _toggle_in_progress zwalniana natychmiast przy off."""
    app.glava_enabled_var.set(False)
    app._on_glava_toggle()
    assert app._toggle_in_progress == False

def test_second_toggle_allowed_after_first_completes(app):
    """Po zakończeniu pierwszego toggle, drugi działa normalnie."""
    app.glava_enabled_var.set(True)
    app._on_glava_toggle()
    time.sleep(0.2)              # czekamy aż flaga zwolniona
    app.glava_enabled_var.set(False)
    app._on_glava_toggle()
    time.sleep(0.1)
    app.glava_enabled_var.set(True)
    app._on_glava_toggle()
    time.sleep(0.2)
    assert len(app._started_procs) == 2  # dwa pełne cykle on
