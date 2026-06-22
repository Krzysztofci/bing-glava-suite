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
    """Tworzy GlavaGUI bez wołania __init__ (które buduje całe okno Tk).
    Atrybuty, których dana metoda potrzebuje, wstrzykujemy ręcznie."""
    return gg.GlavaGUI.__new__(gg.GlavaGUI)


class FakeT(dict):
    pass


class _FakeRoot:
    def after(self, delay, fn, *args):
        fn(*args)
        return "after#0"

    def after_cancel(self, jid):
        pass


class _FakeStatusLabel:
    def __init__(self):
        self.text = None

    def config(self, text=None, **kw):
        if text is not None:
            self.text = text


class _FakeInstance:
    def __init__(self, rc_glsl, glava_dir):
        self.rc_glsl = rc_glsl
        self.glava_dir = glava_dir


# ── get_active_rc_glsl / get_active_glava_dir ────────────────────────────────

def test_get_active_rc_glsl_returns_none_when_no_active_instance(gg):
    app = _make_gui(gg)
    app.active_instance = None
    assert app.get_active_rc_glsl() is None


def test_get_active_rc_glsl_returns_path(gg):
    app = _make_gui(gg)
    app.active_instance = _FakeInstance("/tmp/x/rc.glsl", "/tmp/x")
    assert app.get_active_rc_glsl() == "/tmp/x/rc.glsl"


def test_get_active_glava_dir_returns_none_when_no_active_instance(gg):
    app = _make_gui(gg)
    app.active_instance = None
    assert app.get_active_glava_dir() is None


def test_get_active_glava_dir_returns_path(gg):
    app = _make_gui(gg)
    app.active_instance = _FakeInstance("/tmp/x/rc.glsl", "/tmp/x")
    assert app.get_active_glava_dir() == "/tmp/x"


# ── _save_gui_conf ────────────────────────────────────────────────────────────

def test_save_gui_conf_delegates_to_module_function(gg, monkeypatch):
    app = _make_gui(gg)
    app.gui_conf = {"width": 800, "height": 600, "x": None, "y": None,
                     "theme": "forest-dark"}

    calls = []
    monkeypatch.setattr(gg, "save_gui_conf", lambda conf: calls.append(conf))

    app._save_gui_conf()

    assert calls == [app.gui_conf]


# ── _save_active_instance ────────────────────────────────────────────────────

def test_save_active_instance_marks_active_entry(gg, monkeypatch):
    app = _make_gui(gg)
    app._active_inst_id = 1

    import gui.instance as instance_mod
    fake_entries = [{"inst_id": 0}, {"inst_id": 1}, {"inst_id": 2}]
    monkeypatch.setattr(instance_mod, "load_instances", lambda: fake_entries)
    saved = []
    monkeypatch.setattr(instance_mod, "save_instances", lambda entries: saved.append(entries))

    app._save_active_instance()

    assert saved == [fake_entries]
    assert [e["active"] for e in fake_entries] == [False, True, False]


def test_save_active_instance_all_false_when_none_active(gg, monkeypatch):
    app = _make_gui(gg)
    app._active_inst_id = None

    import gui.instance as instance_mod
    fake_entries = [{"inst_id": 0}, {"inst_id": 1}]
    monkeypatch.setattr(instance_mod, "load_instances", lambda: fake_entries)
    saved = []
    monkeypatch.setattr(instance_mod, "save_instances", lambda entries: saved.append(entries))

    app._save_active_instance()

    assert all(e["active"] is False for e in fake_entries)


def test_save_active_instance_swallows_exceptions(gg, monkeypatch):
    """Błąd I/O (np. uszkodzony instances.json) nie powinien crashować —
    funkcja ma broad except Exception: pass."""
    app = _make_gui(gg)
    app._active_inst_id = 0

    import gui.instance as instance_mod
    monkeypatch.setattr(instance_mod, "load_instances",
                         lambda: (_ for _ in ()).throw(OSError("disk error")))

    app._save_active_instance()  # nie powinno podnieść wyjątku


# ── update_status / _schedule_status_update ──────────────────────────────────

def test_update_status_shows_active_with_module_and_mode(gg, monkeypatch, tmp_path):
    app = _make_gui(gg)
    app.T = FakeT()
    app.status_label = _FakeStatusLabel()

    monkeypatch.setattr(gg, "glava_is_running", lambda: True)
    monkeypatch.setattr(gg, "read_active_module", lambda: "bars")
    monkeypatch.setattr(gg, "FLAG_MANUAL", str(tmp_path / "manual"))
    monkeypatch.setattr(gg, "FLAG_RED", str(tmp_path / "red"))
    monkeypatch.setattr(gg, "WALLPAPER", str(tmp_path / "no_such_wallpaper"))
    monkeypatch.setattr(gg, "WALLPAPER_LOCK", str(tmp_path / "no_such_lock"))

    app.update_status()

    assert "bars" in app.status_label.text
    assert "●" in app.status_label.text


def test_update_status_shows_inactive(gg, monkeypatch, tmp_path):
    app = _make_gui(gg)
    app.T = FakeT()
    app.status_label = _FakeStatusLabel()

    monkeypatch.setattr(gg, "glava_is_running", lambda: False)
    monkeypatch.setattr(gg, "read_active_module", lambda: "bars")
    monkeypatch.setattr(gg, "WALLPAPER", str(tmp_path / "no_such_wallpaper"))
    monkeypatch.setattr(gg, "WALLPAPER_LOCK", str(tmp_path / "no_such_lock"))

    app.update_status()

    assert "○" in app.status_label.text


def test_update_status_shows_wallpaper_timestamp_when_present(gg, monkeypatch, tmp_path):
    app = _make_gui(gg)
    app.T = FakeT()
    app.status_label = _FakeStatusLabel()

    wallpaper_path = tmp_path / "wallpaper.jpg"
    wallpaper_path.write_text("fake")

    monkeypatch.setattr(gg, "glava_is_running", lambda: False)
    monkeypatch.setattr(gg, "read_active_module", lambda: "bars")
    monkeypatch.setattr(gg, "WALLPAPER", str(wallpaper_path))
    monkeypatch.setattr(gg, "WALLPAPER_LOCK", str(tmp_path / "no_such_lock"))

    app.update_status()

    assert "label_wallpaper" in app.status_label.text or ":" in app.status_label.text


def test_update_status_shows_lock_icon_when_locked(gg, monkeypatch, tmp_path):
    app = _make_gui(gg)
    app.T = FakeT()
    app.status_label = _FakeStatusLabel()

    lock_path = tmp_path / "locked"
    lock_path.write_text("")

    monkeypatch.setattr(gg, "glava_is_running", lambda: False)
    monkeypatch.setattr(gg, "read_active_module", lambda: "bars")
    monkeypatch.setattr(gg, "WALLPAPER", str(tmp_path / "no_such_wallpaper"))
    monkeypatch.setattr(gg, "WALLPAPER_LOCK", str(lock_path))

    app.update_status()

    assert "🔒" in app.status_label.text


def test_update_status_shows_manual_mode(gg, monkeypatch, tmp_path):
    app = _make_gui(gg)
    app.T = FakeT()
    app.status_label = _FakeStatusLabel()

    manual_path = tmp_path / "manual"
    manual_path.write_text("")

    monkeypatch.setattr(gg, "glava_is_running", lambda: True)
    monkeypatch.setattr(gg, "read_active_module", lambda: "bars")
    monkeypatch.setattr(gg, "FLAG_MANUAL", str(manual_path))
    monkeypatch.setattr(gg, "FLAG_RED", str(tmp_path / "red"))
    monkeypatch.setattr(gg, "WALLPAPER", str(tmp_path / "no_such_wallpaper"))
    monkeypatch.setattr(gg, "WALLPAPER_LOCK", str(tmp_path / "no_such_lock"))

    app.update_status()

    assert "mode_manual" in app.status_label.text or "ręczny" in app.status_label.text


def test_update_status_shows_red_mode(gg, monkeypatch, tmp_path):
    app = _make_gui(gg)
    app.T = FakeT()
    app.status_label = _FakeStatusLabel()

    red_path = tmp_path / "red"
    red_path.write_text("")

    monkeypatch.setattr(gg, "glava_is_running", lambda: True)
    monkeypatch.setattr(gg, "read_active_module", lambda: "bars")
    monkeypatch.setattr(gg, "FLAG_MANUAL", str(tmp_path / "no_such_manual"))
    monkeypatch.setattr(gg, "FLAG_RED", str(red_path))
    monkeypatch.setattr(gg, "WALLPAPER", str(tmp_path / "no_such_wallpaper"))
    monkeypatch.setattr(gg, "WALLPAPER_LOCK", str(tmp_path / "no_such_lock"))

    app.update_status()

    assert "mode_red" in app.status_label.text or "RED" in app.status_label.text


def test_schedule_status_update_calls_update_and_reschedules(gg):
    app = _make_gui(gg)
    status_calls = []
    app.update_status = lambda: status_calls.append(True)

    scheduled = []

    class _RecordingRoot:
        """Tylko rejestruje zaplanowane wywołanie, NIE wykonuje go —
        bo _schedule_status_update woła samo siebie przez root.after();
        synchroniczny FakeRoot zapętliłby się w nieskończoność."""
        def after(self, delay, fn, *args):
            scheduled.append((delay, fn))
            return "after#0"

    app.root = _RecordingRoot()

    app._schedule_status_update()

    assert status_calls == [True]
    assert len(scheduled) == 1
    assert scheduled[0][0] == 3000
    assert scheduled[0][1] == app._schedule_status_update
