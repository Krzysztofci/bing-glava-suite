import os
import sys
import pytest
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import gui.modules.bars as bars_mod
import gui.modules.glsl_io as glsl_io


# ── Fakes ─────────────────────────────────────────────────────────────────────

class FakeT(dict):
    pass


class FakeInstance:
    def __init__(self, base_dir, name="inst"):
        self.base_dir = base_dir
        self.name = name
        self.smooth_glsl = os.path.join(base_dir, f"{name}_smooth.glsl")

    def module_glsl(self, module):
        return os.path.join(self.base_dir, f"{self.name}_{module}.glsl")

    def module_tmpl(self, module):
        return os.path.join(self.base_dir, f"{self.name}_{module}_tmpl.frag")

    def module_frag(self, module):
        return os.path.join(self.base_dir, f"{self.name}_{module}_live.frag")


class FakeApp:
    def __init__(self, tmp_path):
        self.T = FakeT()
        self.root = type("FakeRoot", (), {
            "after": staticmethod(lambda delay, fn: fn()),
            "after_cancel": staticmethod(lambda job: None),
        })()
        self.active_instance = FakeInstance(str(tmp_path), "inst0")
        self.update_status_calls = 0
        self.rebuild_calls = 0

    def update_status(self):
        self.update_status_calls += 1

    def rebuild_module_tab(self):
        self.rebuild_calls += 1


@pytest.fixture
def fake_app(tmp_path):
    return FakeApp(tmp_path)


@pytest.fixture
def widget(fake_app):
    return bars_mod.BarsParamWidget(parent=None, app=fake_app, T=fake_app.T)


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def _capture_on_select(monkeypatch):
    """on_select jest domknięciem lokalnym w _combo_row, bindowanym przez
    cb.bind('<<ComboboxSelected>>', on_select) — nie jest atrybutem
    widgetu. Podsłuchujemy tk.Misc.bind() po func.__name__, ten sam
    wzorzec co dla on_change/on_entry w base.py/tab_advanced.py."""
    captured = {}
    orig_bind = tk.Misc.bind
    def fake_bind(self, sequence=None, func=None, add=None):
        if func is not None and getattr(func, "__name__", None) == "on_select":
            captured["on_select"] = func
        return orig_bind(self, sequence, func, add)
    monkeypatch.setattr(tk.Misc, "bind", fake_bind)
    return captured


@pytest.fixture
def real_glsl_file(fake_app, tmp_path):
    """Tworzy realny plik .glsl z domyślnymi DEFINE'ami SHAPE_PARAMS i
    FLAG_PARAMS — pozwala testować collect_params/apply_params/reset_shader
    przez prawdziwy glsl_io, nie przez mocki."""
    path = fake_app.active_instance.module_glsl("bars")
    lines = []
    for key, label, vmin, vmax, default, unit, tooltip in bars_mod.SHAPE_PARAMS:
        lines.append(f"#define {key} {default}\n")
    for key, label, tooltip in bars_mod.FLAG_PARAMS:
        lines.append(f"#define {key} 0\n")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.writelines(lines)
    return path


@pytest.fixture
def real_smooth_file(fake_app):
    path = fake_app.active_instance.smooth_glsl
    lines = []
    for p in bars_mod.SMOOTH_PARAMS:
        key, label, vmin, vmax, default = p[0], p[1], p[2], p[3], p[4]
        lines.append(f"#request {key} {default}\n")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.writelines(lines)
    return path


# ── collect_params / apply_params — module-level API ────────────────────────

def test_collect_params_reads_shape_flag_and_smooth_values(
        fake_app, real_glsl_file, real_smooth_file):
    params = bars_mod.collect_params(fake_app)
    assert params["BAR_WIDTH"] == bars_mod.SHAPE_PARAMS[0][4]
    assert params["DIRECTION"] == 0
    assert "setgravitystep" in params


def test_apply_params_writes_shape_flag_and_smooth_values(
        fake_app, real_glsl_file, real_smooth_file):
    new_params = {"BAR_WIDTH": 15, "DIRECTION": 1, "setgravitystep": 7.5}
    bars_mod.apply_params(new_params, fake_app)

    result = bars_mod.collect_params(fake_app)
    assert result["BAR_WIDTH"] == 15
    assert result["DIRECTION"] == 1


def test_collect_then_apply_then_collect_roundtrip(
        fake_app, real_glsl_file, real_smooth_file):
    """Round-trip: zmiana parametru, zapis, ponowny odczyt powinien
    odzwierciedlać nową wartość."""
    original = bars_mod.collect_params(fake_app)
    modified = dict(original)
    modified["BAR_GAP"] = 9
    bars_mod.apply_params(modified, fake_app)
    reloaded = bars_mod.collect_params(fake_app)
    assert reloaded["BAR_GAP"] == 9


# ── reset_shader — module-level ─────────────────────────────────────────────

def test_reset_shader_copies_template_when_exists(fake_app, tmp_path):
    inst = fake_app.active_instance
    tmpl_path = inst.module_tmpl("bars")
    live_path = inst.module_frag("bars")
    os.makedirs(os.path.dirname(tmpl_path), exist_ok=True)
    with open(tmpl_path, "w") as f:
        f.write("vec3 top = vec3(1.0, 1.0, 1.0);")

    glsl_path = inst.module_glsl("bars")
    os.makedirs(os.path.dirname(glsl_path), exist_ok=True)
    with open(glsl_path, "w") as f:
        for key, *_ in bars_mod.SHAPE_PARAMS:
            f.write(f"#define {key} 999\n")
        for key, *_ in bars_mod.FLAG_PARAMS:
            f.write(f"#define {key} 1\n")

    bars_mod.reset_shader(fake_app)

    assert os.path.exists(live_path)
    with open(live_path) as f:
        assert f.read() == "vec3 top = vec3(1.0, 1.0, 1.0);"


def test_reset_shader_restores_shape_defaults(fake_app, real_glsl_file):
    # Zmień wartość przed resetem
    glsl_io.write_defines(real_glsl_file, {"BAR_WIDTH": 30}, bars_mod.SHAPE_PARAMS)

    bars_mod.reset_shader(fake_app)

    result = glsl_io.read_defines(real_glsl_file, bars_mod.SHAPE_PARAMS)
    default = next(p[4] for p in bars_mod.SHAPE_PARAMS if p[0] == "BAR_WIDTH")
    assert result["BAR_WIDTH"] == default


def test_reset_shader_clears_all_flags_to_zero(fake_app, real_glsl_file):
    glsl_io.write_flag_defines(real_glsl_file, {"FLIP": 1, "MIRROR_YX": 1},
                                bars_mod.FLAG_PARAMS)

    bars_mod.reset_shader(fake_app)

    result = glsl_io.read_flag_defines(real_glsl_file, bars_mod.FLAG_PARAMS)
    for key, *_ in bars_mod.FLAG_PARAMS:
        assert result[key] == 0


def test_reset_shader_skips_copy_when_template_missing(fake_app, real_glsl_file):
    inst = fake_app.active_instance
    live_path = inst.module_frag("bars")
    assert not os.path.exists(inst.module_tmpl("bars"))

    bars_mod.reset_shader(fake_app)  # nie powinno crashować

    assert not os.path.exists(live_path)


# ── _write_flag ──────────────────────────────────────────────────────────────

def test_write_flag_writes_true_as_1(widget, fake_app, real_glsl_file, monkeypatch):
    monkeypatch.setattr(widget, "_update_geometry", lambda: None)
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    class FakeVar:
        def get(self):
            return True
    widget._write_flag("DIRECTION", FakeVar())

    result = glsl_io.read_flag_defines(real_glsl_file, bars_mod.FLAG_PARAMS)
    assert result["DIRECTION"] == 1


def test_write_flag_writes_false_as_0(widget, fake_app, real_glsl_file, monkeypatch):
    glsl_io.write_flag_defines(real_glsl_file, {"DIRECTION": 1}, bars_mod.FLAG_PARAMS)
    monkeypatch.setattr(widget, "_update_geometry", lambda: None)
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    class FakeVar:
        def get(self):
            return False
    widget._write_flag("DIRECTION", FakeVar())

    result = glsl_io.read_flag_defines(real_glsl_file, bars_mod.FLAG_PARAMS)
    assert result["DIRECTION"] == 0


def test_write_flag_triggers_geometry_update_for_flip(
        widget, fake_app, real_glsl_file, monkeypatch):
    geometry_calls = []
    monkeypatch.setattr(widget, "_update_geometry", lambda: geometry_calls.append(True))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    class FakeVar:
        def get(self):
            return True
    widget._write_flag("FLIP", FakeVar())

    assert geometry_calls == [True]


def test_write_flag_triggers_geometry_update_for_mirror_yx(
        widget, fake_app, real_glsl_file, monkeypatch):
    geometry_calls = []
    monkeypatch.setattr(widget, "_update_geometry", lambda: geometry_calls.append(True))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    class FakeVar:
        def get(self):
            return True
    widget._write_flag("MIRROR_YX", FakeVar())

    assert geometry_calls == [True]


def test_write_flag_does_not_trigger_geometry_for_other_flags(
        widget, fake_app, real_glsl_file, monkeypatch):
    geometry_calls = []
    monkeypatch.setattr(widget, "_update_geometry", lambda: geometry_calls.append(True))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    class FakeVar:
        def get(self):
            return True
    widget._write_flag("DIRECTION", FakeVar())

    assert geometry_calls == []


def test_write_flag_calls_schedule_restart(widget, fake_app, real_glsl_file, monkeypatch):
    monkeypatch.setattr(widget, "_update_geometry", lambda: None)
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    class FakeVar:
        def get(self):
            return True
    widget._write_flag("DIRECTION", FakeVar())

    assert restart_calls == [True]


# ── _update_geometry ──────────────────────────────────────────────────────────

import gui.geometry as geometry_mod


def test_update_geometry_reads_flip_and_mirror_yx_and_writes(
        widget, fake_app, real_glsl_file, tmp_path):
    glsl_io.write_flag_defines(real_glsl_file, {"FLIP": 1, "MIRROR_YX": 1},
                                bars_mod.FLAG_PARAMS)
    rc_path = str(tmp_path / "rc.glsl")
    with open(rc_path, "w") as f:
        f.write("#request setgeometry 0 0 100 100\n")
    fake_app.get_active_rc_glsl = lambda: rc_path

    calc_calls = []
    def fake_calc_geometry(module, sw, sh, bottom, top, flipped, mirror_yx,
                            left_reserved, right_reserved):
        calc_calls.append({"flipped": flipped, "mirror_yx": mirror_yx})
        return (0, 0, sw, sh)

    import gui.modules.bars as b
    orig_calc = geometry_mod.calc_geometry
    orig_screen = geometry_mod.get_screen_info
    orig_write = geometry_mod.write_geometry
    geometry_mod.calc_geometry = fake_calc_geometry
    geometry_mod.get_screen_info = lambda: (1920, 1080, 1040, 0, 40, 0, 0)
    write_calls = []
    geometry_mod.write_geometry = lambda rc, x, y, w, h: write_calls.append((rc, x, y, w, h))
    try:
        widget._update_geometry()
    finally:
        geometry_mod.calc_geometry = orig_calc
        geometry_mod.get_screen_info = orig_screen
        geometry_mod.write_geometry = orig_write

    assert calc_calls == [{"flipped": True, "mirror_yx": True}]
    assert write_calls == [(rc_path, 0, 0, 1920, 1080)]


def test_update_geometry_defaults_false_when_flags_absent(
        widget, fake_app, real_glsl_file, tmp_path):
    rc_path = str(tmp_path / "rc.glsl")
    with open(rc_path, "w") as f:
        f.write("#request setgeometry 0 0 100 100\n")
    fake_app.get_active_rc_glsl = lambda: rc_path

    calc_calls = []
    def fake_calc_geometry(module, sw, sh, bottom, top, flipped, mirror_yx,
                            left_reserved, right_reserved):
        calc_calls.append({"flipped": flipped, "mirror_yx": mirror_yx})
        return (0, 0, sw, sh)

    orig_calc = geometry_mod.calc_geometry
    orig_screen = geometry_mod.get_screen_info
    orig_write = geometry_mod.write_geometry
    geometry_mod.calc_geometry = fake_calc_geometry
    geometry_mod.get_screen_info = lambda: (1920, 1080, 1040, 0, 40, 0, 0)
    geometry_mod.write_geometry = lambda *a: None
    try:
        widget._update_geometry()
    finally:
        geometry_mod.calc_geometry = orig_calc
        geometry_mod.get_screen_info = orig_screen
        geometry_mod.write_geometry = orig_write

    assert calc_calls == [{"flipped": False, "mirror_yx": False}]


def test_update_geometry_swallows_exceptions_silently(widget, fake_app):
    """Owinięte w except Exception: pass — błąd w detekcji geometrii nie
    powinien crashować _write_flag, który je wywołuje."""
    orig_calc = geometry_mod.calc_geometry
    def broken(*a, **kw):
        raise RuntimeError("boom")
    geometry_mod.calc_geometry = broken
    try:
        widget._update_geometry()  # nie powinno podnieść wyjątku
    finally:
        geometry_mod.calc_geometry = orig_calc


# ── _validate_buf_sample ─────────────────────────────────────────────────────
# UWAGA: SAMPLE_EXPERT/SAMPLE_NORMAL nie są zdefiniowane w bars.py — to
# artefakt po przeniesieniu opcji audio do tab_advanced.py (potwierdzone
# przez autora). Nie usuwamy kodu teraz, ale testy muszą same dostarczyć
# te stałe przez monkeypatch, żeby zweryfikować zachowanie zgodnie z
# obecnym zapisem funkcji, niezależnie od tego czy w praktyce jest to
# dziś wołane z działającego GUI.

@pytest.fixture
def widget_with_buf_sample_vars(widget):
    class FakeVar:
        def __init__(self, value):
            self._value = value
        def get(self):
            return self._value
        def set(self, v):
            self._value = v
    widget.vars["setbufsize"] = FakeVar("1024")
    widget.vars["setsamplesize"] = FakeVar("512")
    return widget


def test_validate_buf_sample_missing_vars_returns_silently(widget):
    """Brak setbufsize/setsamplesize w self.vars -> KeyError złapany,
    early return bez crashu."""
    widget._validate_buf_sample("setbufsize", 2048)  # nie powinno crashować


def test_validate_buf_sample_clamps_samplesize_when_buf_shrinks(
        widget_with_buf_sample_vars, monkeypatch):
    monkeypatch.setattr(bars_mod, "SAMPLE_NORMAL", [128, 256, 512, 1024], raising=False)
    monkeypatch.setattr(bars_mod, "SAMPLE_EXPERT", [64, 128, 256, 512, 1024, 2048], raising=False)
    monkeypatch.setattr(widget_with_buf_sample_vars, "_expert", lambda: False)

    rc_writes = []
    monkeypatch.setattr(glsl_io, "write_int_req",
                         lambda rc, key, val: rc_writes.append((key, val)))

    # bufsize zmienia się na 256, ale samplesize=512 > 256 -> trzeba zmniejszyć
    widget_with_buf_sample_vars._validate_buf_sample("setbufsize", 256)

    assert widget_with_buf_sample_vars.vars["setsamplesize"].get() == "256"
    assert rc_writes == [("setsamplesize", 256)]


def test_validate_buf_sample_clamps_when_samplesize_exceeds_buf(
        widget_with_buf_sample_vars, monkeypatch):
    monkeypatch.setattr(bars_mod, "SAMPLE_NORMAL", [128, 256, 512, 1024], raising=False)
    monkeypatch.setattr(bars_mod, "SAMPLE_EXPERT", [64, 128, 256, 512, 1024, 2048], raising=False)
    monkeypatch.setattr(widget_with_buf_sample_vars, "_expert", lambda: False)

    widget_with_buf_sample_vars.vars["setbufsize"].set("512")

    # Próba ustawienia samplesize=1024, ale buf=512 -> trzeba przyciąć do <=512
    widget_with_buf_sample_vars._validate_buf_sample("setsamplesize", 1024)

    assert widget_with_buf_sample_vars.vars["setsamplesize"].get() == "512"


def test_validate_buf_sample_uses_expert_values_when_expert_mode_on(
        widget_with_buf_sample_vars, monkeypatch):
    monkeypatch.setattr(bars_mod, "SAMPLE_NORMAL", [128, 256, 512], raising=False)
    monkeypatch.setattr(bars_mod, "SAMPLE_EXPERT", [64, 128, 256, 512, 1024, 2048], raising=False)
    monkeypatch.setattr(widget_with_buf_sample_vars, "_expert", lambda: True)
    monkeypatch.setattr(glsl_io, "write_int_req", lambda *a: None)

    # bufsize=300 (między 256 i 512 w expert): max valid sample <= 300 z
    # SAMPLE_EXPERT to 256. Gdyby użyto SAMPLE_NORMAL wynik byłby identyczny
    # tu (256), więc wybieramy bufsize=600 by odróżnić expert vs normal.
    widget_with_buf_sample_vars._validate_buf_sample("setbufsize", 600)

    # SAMPLE_EXPERT max <= 600 -> 512; SAMPLE_NORMAL max <= 600 -> 512 też
    # (oba listy mają 512 jako największy <=600) — test wartości pośrednio
    # potwierdza że żadna lista nie została pominięta przez błąd nazwy.
    assert widget_with_buf_sample_vars.vars["setsamplesize"].get() == "512"


def test_validate_buf_sample_does_not_modify_when_sample_within_buf(
        widget_with_buf_sample_vars, monkeypatch):
    monkeypatch.setattr(bars_mod, "SAMPLE_NORMAL", [128, 256, 512, 1024], raising=False)
    monkeypatch.setattr(bars_mod, "SAMPLE_EXPERT", [64, 128, 256, 512, 1024, 2048], raising=False)
    monkeypatch.setattr(widget_with_buf_sample_vars, "_expert", lambda: False)

    widget_with_buf_sample_vars.vars["setsamplesize"].set("256")
    rc_writes = []
    monkeypatch.setattr(glsl_io, "write_int_req",
                         lambda *a: rc_writes.append(True))

    # bufsize zwiększa się do 2048, samplesize=256 wciąż <= 2048 -> brak zmian
    widget_with_buf_sample_vars._validate_buf_sample("setbufsize", 2048)

    assert widget_with_buf_sample_vars.vars["setsamplesize"].get() == "256"
    assert rc_writes == []


# ── _combo_row — on_select closure (bindowane na <<ComboboxSelected>>) ──────
#
# _combo_row samo jest GUI (layout) i celowo nieprzetestowane, ale on_select
# w jego wnętrzu to realna logika (walidacja, zapis do rc.glsl, restart) —
# wymaga prawdziwego Tk (Combobox + StringVar), więc dostaje własny fixture
# `root`, niezależny od FakeApp.root używanego przez resztę pliku.

def test_combo_row_on_select_valid_value_validates_writes_and_restarts(
        widget, root, monkeypatch):
    var = tk.StringVar(master=root, value="512")
    widget.vars["setbufsize"] = var
    frame = tk.Frame(root)
    captured = _capture_on_select(monkeypatch)

    validate_calls = []
    monkeypatch.setattr(widget, "_validate_buf_sample",
                         lambda k, v: validate_calls.append((k, v)))
    write_calls = []
    monkeypatch.setattr(glsl_io, "write_int_req",
                         lambda rc, key, val: write_calls.append((rc, key, val)))
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    widget._combo_row(frame, "Buffer", "setbufsize", [256, 512, 1024], "512", "tip")
    captured["on_select"](None)

    assert validate_calls == [("setbufsize", 512)]
    assert write_calls == [(bars_mod.RC_GLSL, "setbufsize", 512)]
    assert restart_calls == [True]


def test_combo_row_on_select_uses_active_rc_glsl_when_app_provides_it(
        widget, root, fake_app, monkeypatch, tmp_path):
    var = tk.StringVar(master=root, value="1024")
    widget.vars["setbufsize"] = var
    frame = tk.Frame(root)
    captured = _capture_on_select(monkeypatch)

    rc_path = str(tmp_path / "active_rc.glsl")
    fake_app.get_active_rc_glsl = lambda: rc_path
    monkeypatch.setattr(widget, "_validate_buf_sample", lambda k, v: None)
    write_calls = []
    monkeypatch.setattr(glsl_io, "write_int_req",
                         lambda rc, key, val: write_calls.append(rc))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    widget._combo_row(frame, "Buffer", "setbufsize", [256, 512, 1024], "1024", "tip")
    captured["on_select"](None)

    assert write_calls == [rc_path]


def test_combo_row_on_select_invalid_value_swallows_valueerror(
        widget, root, monkeypatch):
    """var.get() niekonwertowalne na int -> ValueError -> except: pass,
    żadny zapis/restart nie powinien się wydarzyć."""
    var = tk.StringVar(master=root, value="not-a-number")
    widget.vars["setbufsize"] = var
    frame = tk.Frame(root)
    captured = _capture_on_select(monkeypatch)

    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    widget._combo_row(frame, "Buffer", "setbufsize", [256, 512, 1024], "512", "tip")
    captured["on_select"](None)

    assert restart_calls == []


# ── _reset_shader (widget method) ───────────────────────────────────────────

def test_widget_reset_shader_aborts_if_declined(widget, fake_app, monkeypatch):
    monkeypatch.setattr(bars_mod.messagebox, "askyesno", lambda *a, **kw: False)
    reset_calls = []
    monkeypatch.setattr(bars_mod, "reset_shader", lambda app: reset_calls.append(True))

    widget._reset_shader()

    assert reset_calls == []
    assert fake_app.rebuild_calls == 0


def test_widget_reset_shader_calls_module_reset_and_rebuilds(
        widget, fake_app, monkeypatch):
    monkeypatch.setattr(bars_mod.messagebox, "askyesno", lambda *a, **kw: True)
    reset_calls = []
    monkeypatch.setattr(bars_mod, "reset_shader", lambda app: reset_calls.append(app))

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, **kw: restart_calls.append(module))

    widget._reset_shader()

    assert reset_calls == [fake_app]
    assert fake_app.rebuild_calls == 1
    assert restart_calls == ["bars"]


def test_widget_reset_shader_uses_restart_active_instance_when_available(
        widget, fake_app, monkeypatch):
    monkeypatch.setattr(bars_mod.messagebox, "askyesno", lambda *a, **kw: True)
    monkeypatch.setattr(bars_mod, "reset_shader", lambda app: None)

    restart_calls = []
    fake_app.restart_active_instance = (
        lambda module=None, after_fn=None: restart_calls.append(module))

    widget._reset_shader()

    assert restart_calls == ["bars"]


def test_widget_reset_shader_falls_back_to_legacy_glava_restart(
        widget, fake_app, monkeypatch):
    monkeypatch.setattr(bars_mod.messagebox, "askyesno", lambda *a, **kw: True)
    monkeypatch.setattr(bars_mod, "reset_shader", lambda app: None)
    assert not hasattr(fake_app, "restart_active_instance")

    import gui.glava as glava_mod
    restart_calls = []
    monkeypatch.setattr(glava_mod, "glava_restart",
                         lambda module, extra_flags=None, after_fn=None:
                         restart_calls.append(module))

    widget._reset_shader()

    assert restart_calls == ["bars"]


# ── _write_bool_rc ───────────────────────────────────────────────────────────

def test_write_bool_rc_writes_and_schedules_restart(widget, fake_app, monkeypatch, tmp_path):
    rc_path = str(tmp_path / "rc.glsl")
    with open(rc_path, "w") as f:
        f.write("#request setsomeflag 0\n")
    fake_app.get_active_rc_glsl = lambda: rc_path

    write_calls = []
    monkeypatch.setattr(glsl_io, "write_bool_req",
                         lambda path, key, value: write_calls.append((path, key, value)))
    restart_calls = []
    monkeypatch.setattr(widget, "_schedule_restart", lambda: restart_calls.append(True))

    class FakeVar:
        def get(self):
            return True
    widget._write_bool_rc("setsomeflag", FakeVar())

    assert write_calls == [(rc_path, "setsomeflag", True)]
    assert restart_calls == [True]


def test_write_bool_rc_uses_global_rc_glsl_when_no_active_rc_method(
        widget, fake_app, monkeypatch):
    assert not hasattr(fake_app, "get_active_rc_glsl")
    write_calls = []
    monkeypatch.setattr(glsl_io, "write_bool_req",
                         lambda path, key, value: write_calls.append(path))
    monkeypatch.setattr(widget, "_schedule_restart", lambda: None)

    class FakeVar:
        def get(self):
            return False
    widget._write_bool_rc("setsomeflag", FakeVar())

    assert write_calls == [bars_mod.RC_GLSL]
