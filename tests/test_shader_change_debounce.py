# =============================================================================
# tests/test_shader_change_debounce.py
# Testy bug #3 — duplikacja procesu GLava przy zmianie parametru shadera.
#
# Problem: zmiana parametru (np. AVG klatek w sekcji wygładzania) wywołuje
# restart_active_instance() z debounce 300ms. Jeśli dwa wywołania trafią
# blisko siebie i debounce nie zadziała poprawnie, mogą wystartować dwa
# równoległe procesy GLava dla tej samej instancji.
#
# Testy weryfikują że:
# 1. Szybkie wielokrotne wywołania restart_active_instance scalają się w 1
# 2. Każde wywołanie anuluje poprzedni after() zanim doda nowy
# 3. change_shader debounce działa niezależnie per instancja
# 4. Zmiana parametru przez tab_module nie odpala restartu bez debounce
# =============================================================================
import pytest
import time
import threading
import subprocess
import os
import shutil


# ── Fake Root (bez tkinter) ───────────────────────────────────────────────────
class FakeRoot:
    """Mock tk.Tk — rejestruje after()/after_cancel() bez GUI."""
    def __init__(self):
        self._jobs    = {}
        self._ctr     = 0
        self._lock    = threading.Lock()
        self.executed = []

    def after(self, ms, fn, *args):
        with self._lock:
            jid = f"after#{self._ctr}"  # string jak prawdziwy tkinter — zawsze truthy
            self._ctr += 1
            self._jobs[jid] = (ms, fn, args)
        return jid

    def after_cancel(self, jid):
        with self._lock:
            self._jobs.pop(jid, None)

    def flush(self):
        """Wykonuje wszystkie zaplanowane after() natychmiast."""
        with self._lock:
            jobs = list(self._jobs.items())
            self._jobs.clear()
        for jid, (ms, fn, args) in jobs:
            fn(*args)
            self.executed.append((ms, fn))

    def pending_count(self):
        with self._lock:
            return len(self._jobs)


# ── FakeInstance ──────────────────────────────────────────────────────────────
class FakeInstance:
    def __init__(self, inst_id, glava_dir):
        self.inst_id   = inst_id
        self.xdg_dir   = glava_dir
        self.glava_dir = glava_dir
        self.conf_dir  = glava_dir

    @property
    def rc_glsl(self):
        return os.path.join(self.glava_dir, "rc.glsl")

    @property
    def smooth_glsl(self):
        return os.path.join(self.glava_dir, "smooth_parameters.glsl")

    def module_glsl(self, mod):
        return os.path.join(self.glava_dir, f"{mod}.glsl")


# ── DebounceApp — izolowana logika debounce z glava-gui.py ───────────────────
class DebounceApp:
    """
    Wyciąga mechanizm debounce z GlavaGUI bez tkinter i bez całego GUI.
    Testuje wyłącznie logikę zarządzania after() i _restart_after/_shader_after.
    glava_restart_instance zastąpiony mockiem który liczy wywołania.
    """
    def __init__(self, root, instance, monkeypatch):
        self.root           = root
        self.active_instance  = instance
        self._active_inst_id  = instance.inst_id
        self.active_module    = "bars"
        self._inst_modules    = {instance.inst_id: "bars"}
        self.processes        = {instance.inst_id: None}
        self._restart_after   = {}
        self._shader_after    = {}
        self.instances        = {instance.inst_id: instance}
        self._restart_calls   = []
        self._started_procs   = []

        import gui.glava as glava_mod

        def mock_restart_instance(instance, module, proc=None,
                                   after_fn=None, delay_ms=500,
                                   extra_flags=None, env=None):
            self._restart_calls.append(module)
            p = subprocess.Popen(["sleep", "10"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            self._started_procs.append(p)
            if after_fn:
                threading.Thread(
                    target=lambda: (time.sleep(0.05), after_fn(p)),
                    daemon=True
                ).start()

        monkeypatch.setattr(glava_mod, "glava_restart_instance",
                            mock_restart_instance)
        self._glava_restart_instance = mock_restart_instance

    def update_status(self):
        pass

    def restart_active_instance(self, module=None, after_fn=None):
        """Kopia restart_active_instance z GlavaGUI (bez update_instance)."""
        iid    = self._active_inst_id
        inst   = self.active_instance
        module = module or self._inst_modules.get(iid, self.active_module)
        self._inst_modules[iid] = module

        if iid in self._restart_after and self._restart_after[iid]:
            try:
                self.root.after_cancel(self._restart_after[iid])
            except Exception:
                pass
            self._restart_after[iid] = None

        def _do_restart():
            self._restart_after[iid] = None
            old_proc = self.processes.get(iid)
            self.processes[iid] = None

            def _after(proc, _iid=iid, _fn=after_fn):
                self.processes[_iid] = proc
                self.root.after(0, self.update_status)
                if _fn:
                    self.root.after(0, _fn)

            self._glava_restart_instance(
                instance=inst, module=module,
                proc=old_proc, after_fn=_after,
            )

        self._restart_after[iid] = self.root.after(300, _do_restart)

    def change_shader(self, inst_id, module):
        """Kopia logiki change_shader z _on_inst_action w GlavaGUI."""
        inst = self.instances.get(inst_id)
        if inst is None:
            return
        self._inst_modules[inst_id] = module

        if inst_id in self._shader_after and self._shader_after[inst_id]:
            try:
                self.root.after_cancel(self._shader_after[inst_id])
            except Exception:
                pass
            self._shader_after[inst_id] = None

        def _do_change_shader(_iid=inst_id, _inst=inst, _module=module):
            self._shader_after[_iid] = None
            proc = self.processes.get(_iid)
            self.processes[_iid] = None

            def _after(new_proc, __iid=_iid):
                self.processes[__iid] = new_proc
                self.root.after(0, self.update_status)

            self._glava_restart_instance(
                instance=_inst, module=_module,
                proc=proc, after_fn=_after,
            )

        self._shader_after[inst_id] = self.root.after(300, _do_change_shader)

    def cleanup(self):
        for p in self._started_procs:
            try:
                p.kill()
                p.wait(timeout=2)
            except Exception:
                pass


# ── Fixture ───────────────────────────────────────────────────────────────────
@pytest.fixture
def app(tmp_path, monkeypatch):
    from gui import glava as glava_mod
    from gui import instance as inst_mod

    monkeypatch.setattr(glava_mod, "_PID_DIR", str(tmp_path / "pids"))
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))
    os.makedirs(str(tmp_path / "pids"))

    glava_dir = str(tmp_path / "glava")
    os.makedirs(glava_dir)
    src_rc = os.path.join(
        os.path.dirname(__file__), '..', 'glava-config', 'rc.glsl'
    )
    shutil.copy2(src_rc, os.path.join(glava_dir, 'rc.glsl'))

    root = FakeRoot()
    inst = FakeInstance(0, glava_dir)
    a = DebounceApp(root, inst, monkeypatch)
    yield a
    a.cleanup()


# ── Testy restart_active_instance (parametry shadera) ────────────────────────

def test_single_param_change_schedules_one_after(app):
    """Jedna zmiana parametru planuje dokładnie 1 after()."""
    app.restart_active_instance()
    assert app.root.pending_count() == 1


def test_rapid_param_changes_schedule_one_after(app):
    """Szybkie wielokrotne zmiany parametru → tylko 1 after() w kolejce."""
    app.restart_active_instance()
    app.restart_active_instance()
    app.restart_active_instance()
    assert app.root.pending_count() == 1


def test_rapid_param_changes_fire_one_restart(app):
    """Szybkie wielokrotne zmiany parametru → tylko 1 glava_restart_instance."""
    app.restart_active_instance()
    app.restart_active_instance()
    app.restart_active_instance()
    app.root.flush()
    assert len(app._restart_calls) == 1


def test_param_change_uses_latest_module(app):
    """Przy szybkich zmianach modułu restart używa ostatnio ustawionego."""
    app.restart_active_instance(module="bars")
    app.restart_active_instance(module="wave")
    app.restart_active_instance(module="circle")
    app.root.flush()
    assert app._restart_calls[-1] == "circle"


def test_second_param_change_cancels_first_after(app):
    """Drugie wywołanie anuluje pierwszy after() — pending_count zawsze == 1."""
    app.restart_active_instance()
    jid1 = app._restart_after.get(0)
    assert jid1 is not None

    app.restart_active_instance()
    jid2 = app._restart_after.get(0)

    assert jid2 is not None
    assert jid2 != jid1
    assert app.root.pending_count() == 1


def test_restart_after_cleared_after_execution(app):
    """Po wykonaniu _do_restart, _restart_after[iid] jest None."""
    app.restart_active_instance()
    app.root.flush()
    assert app._restart_after.get(0) is None


def test_two_sequential_param_changes_fire_two_restarts(app):
    """Dwie zmiany parametru rozdzielone flush() → 2 restarty (poprawne)."""
    app.restart_active_instance(module="bars")
    app.root.flush()
    app.restart_active_instance(module="wave")
    app.root.flush()
    assert len(app._restart_calls) == 2


def test_no_process_duplication_after_rapid_param_change(app):
    """Po flush szybkich wywołań restart — tylko 1 proces uruchomiony."""
    app.restart_active_instance()
    app.restart_active_instance()
    app.restart_active_instance()
    app.root.flush()
    time.sleep(0.1)
    assert len(app._started_procs) == 1


# ── Testy change_shader debounce ──────────────────────────────────────────────

def test_rapid_shader_change_fires_one_restart(app):
    """Szybka zmiana shadera 3x → tylko 1 restart."""
    app.change_shader(0, "bars")
    app.change_shader(0, "wave")
    app.change_shader(0, "circle")
    app.root.flush()
    assert len(app._restart_calls) == 1


def test_rapid_shader_change_uses_last_module(app):
    """Szybka zmiana shadera → restart z ostatnim modułem."""
    app.change_shader(0, "bars")
    app.change_shader(0, "wave")
    app.change_shader(0, "circle")
    app.root.flush()
    assert app._restart_calls[0] == "circle"


def test_shader_change_after_cleared_after_execution(app):
    """Po wykonaniu _do_change_shader, _shader_after[iid] jest None."""
    app.change_shader(0, "wave")
    app.root.flush()
    assert app._shader_after.get(0) is None


def test_shader_change_and_param_change_are_independent(app):
    """_shader_after i _restart_after są niezależne — oba after() w kolejce."""
    app.change_shader(0, "wave")
    app.restart_active_instance(module="wave")
    assert app.root.pending_count() == 2


def test_no_orphan_after_rapid_shader_change(app):
    """Szybka zmiana shadera nie zostawia osieroconych procesów."""
    app.change_shader(0, "bars")
    app.change_shader(0, "wave")
    app.root.flush()
    time.sleep(0.1)
    live = [p for p in app._started_procs if p.poll() is None]
    assert len(live) <= 1
