# =============================================================================
# tests/test_coverage_gaps.py
# Testy zamykające luki w pokryciu:
# - instance.py: presets_file, __repr__
# - glsl_io.py: edge cases (ValueError, append path, brak klucza)
# - geometry.py: _get_screen_size_xrandr, get_strut_reserved, get_screen_info
#   (wszystkie mockowane — nie wymagają X11)
# =============================================================================
import pytest
import os
import shutil
import subprocess

# ── instance.py — linia 59 (presets_file), 146 (__repr__) ────────────────────

def test_presets_file_path(tmp_path, monkeypatch):
    """presets_file zwraca ścieżkę kończącą się na presets.json."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))
    inst = inst_mod.GlavaInstance(0, home=str(tmp_path))
    assert inst.presets_file.endswith("presets.json")
    assert str(tmp_path) in inst.presets_file

def test_instance_repr(tmp_path, monkeypatch):
    """__repr__ zawiera inst_id i glava_dir."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))
    inst = inst_mod.GlavaInstance(5, home=str(tmp_path))
    r = repr(inst)
    assert "5" in r
    assert "glava_dir" in r


# ── glsl_io.py — edge cases ───────────────────────────────────────────────────

@pytest.fixture
def glsl_no_key(tmp_path):
    """Plik GLSL bez żadnych #define."""
    path = str(tmp_path / "empty.glsl")
    with open(path, "w") as f:
        f.write("// pusty plik\n#request setframerate 60\n")
    return path

@pytest.fixture
def glsl_bad_value(tmp_path):
    """Plik GLSL z nieprawidłową (nieliczbową) wartością #define."""
    path = str(tmp_path / "bad.glsl")
    with open(path, "w") as f:
        f.write("#define BAR_WIDTH abc\n#define BAR_GAP 2\n")
    return path

@pytest.fixture
def smooth_bad_value(tmp_path):
    """Plik smooth z nieprawidłową wartością #request."""
    path = str(tmp_path / "smooth.glsl")
    with open(path, "w") as f:
        f.write("#request setgravitystep abc\n#request setavgframes xyz\n")
    return path

def test_read_defines_bad_value_returns_default(glsl_bad_value):
    """read_defines ignoruje nieprawidłowe wartości i zwraca domyślne."""
    from gui.modules.glsl_io import read_defines
    from gui.modules.bars import SHAPE_PARAMS
    result = read_defines(glsl_bad_value, SHAPE_PARAMS)
    default = next(p[4] for p in SHAPE_PARAMS if p[0] == "BAR_WIDTH")
    assert result["BAR_WIDTH"] == default

def test_read_flag_defines_bad_value_returns_default(glsl_bad_value):
    """read_flag_defines ignoruje nieprawidłowe wartości i zwraca 0."""
    from gui.modules.glsl_io import read_flag_defines
    from gui.modules.bars import FLAG_PARAMS
    result = read_flag_defines(glsl_bad_value, FLAG_PARAMS)
    for p in FLAG_PARAMS:
        assert result[p[0]] == 0

def test_read_smooth_bad_value_returns_default(smooth_bad_value):
    """read_smooth ignoruje nieprawidłowe wartości i zwraca domyślne."""
    from gui.modules.glsl_io import read_smooth
    from gui.core import SMOOTH_PARAMS
    result = read_smooth(smooth_bad_value, SMOOTH_PARAMS)
    for p in SMOOTH_PARAMS:
        default = p[4]
        assert result[p[0]] == default

def test_write_defines_appends_new_key(tmp_path):
    """write_defines dopisuje klucz jeśli nie istnieje w pliku."""
    from gui.modules.glsl_io import write_defines, read_raw
    from gui.modules.bars import SHAPE_PARAMS
    path = str(tmp_path / "new.glsl")
    with open(path, "w") as f:
        f.write("// plik bez kluczy\n")
    write_defines(path, {"BAR_WIDTH": 7}, SHAPE_PARAMS)
    result = read_raw(path)
    assert "BAR_WIDTH" in result
    assert result["BAR_WIDTH"] == "7"

def test_write_flag_defines_appends_new_key(tmp_path):
    """write_flag_defines dopisuje klucz jeśli nie istnieje."""
    from gui.modules.glsl_io import write_flag_defines, read_raw
    from gui.modules.bars import FLAG_PARAMS
    path = str(tmp_path / "new.glsl")
    with open(path, "w") as f:
        f.write("// plik bez kluczy\n")
    key = FLAG_PARAMS[0][0]
    write_flag_defines(path, {key: 1}, FLAG_PARAMS)
    result = read_raw(path)
    assert key in result
    assert result[key] == "1"

def test_read_int_req_bad_value_returns_default(tmp_path):
    """read_int_req zwraca default gdy wartość nie jest liczbą."""
    from gui.modules.glsl_io import write_request, read_int_req
    path = str(tmp_path / "rc.glsl")
    with open(path, "w") as f:
        f.write("#request setframerate auto\n")
    result = read_int_req(path, "setframerate", 60)
    assert result["setframerate"] == 60

def test_write_smooth_missing_file(tmp_path):
    """write_smooth nie crashuje gdy plik nie istnieje."""
    from gui.modules.glsl_io import write_smooth
    from gui.core import SMOOTH_PARAMS
    write_smooth(str(tmp_path / "nonexistent.glsl"), {"setgravitystep": 4.2}, SMOOTH_PARAMS)

def test_write_bool_req_missing_file(tmp_path):
    """write_bool_req nie crashuje gdy plik nie istnieje."""
    from gui.modules.glsl_io import write_bool_req
    write_bool_req(str(tmp_path / "nonexistent.glsl"), "setfloating", True)

def test_read_rc_module_no_match(tmp_path):
    """read_rc_module zwraca None gdy brak linii #request mod."""
    from gui.glava import read_rc_module
    path = str(tmp_path / "rc.glsl")
    with open(path, "w") as f:
        f.write("#request setframerate 60\n")
    assert read_rc_module(rc_path=path) is None


# ── geometry.py — mockowane X11 ───────────────────────────────────────────────

def test_get_screen_size_xrandr_success(monkeypatch):
    """_get_screen_size_xrandr parsuje wynik xrandr poprawnie."""
    from gui import geometry as geo
    fake_result = subprocess.CompletedProcess(
        args=[], returncode=0,
        stdout="Screen 0: minimum 8 x 8, current 1600 x 900, maximum 32767 x 32767\n"
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
    w, h = geo._get_screen_size_xrandr()
    assert w == 1600
    assert h == 900

def test_get_screen_size_xrandr_fallback(monkeypatch):
    """_get_screen_size_xrandr zwraca 1600x900 gdy xrandr zawiedzie."""
    from gui import geometry as geo
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    w, h = geo._get_screen_size_xrandr()
    assert w == 1600
    assert h == 900

def test_get_strut_reserved_no_windows(monkeypatch):
    """get_strut_reserved zwraca (0,0,0,0) gdy brak okien z STRUT."""
    from gui import geometry as geo
    fake_result = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
    result = geo.get_strut_reserved()
    assert result == (0, 0, 0, 0)

def test_get_strut_reserved_with_taskbar(monkeypatch):
    """get_strut_reserved wykrywa pasek na dole (bottom=40)."""
    from gui import geometry as geo
    call_count = [0]
    def fake_run(cmd, **kw):
        call_count[0] += 1
        if "_NET_CLIENT_LIST" in " ".join(cmd):
            return subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="_NET_CLIENT_LIST(WINDOW): window id # 0x1234\n")
        if "_NET_WM_STRUT_PARTIAL" in " ".join(cmd):
            # left=0, right=0, top=0, bottom=40, ...
            return subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="_NET_WM_STRUT_PARTIAL(CARDINAL) = 0, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 0\n")
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    top, bottom, left, right = geo.get_strut_reserved()
    assert bottom == 40
    assert top == 0

def test_get_screen_info_layer1_strut(monkeypatch):
    """get_screen_info używa STRUT_PARTIAL gdy dostępne."""
    from gui import geometry as geo
    monkeypatch.setattr(geo, "_get_screen_size_xrandr", lambda: (1600, 900))
    monkeypatch.setattr(geo, "get_strut_reserved", lambda: (0, 40, 0, 0))
    result = geo.get_screen_info()
    assert len(result) == 7
    screen_w, screen_h, work_h, top, bottom, left, right = result
    assert screen_w == 1600
    assert screen_h == 900
    assert bottom == 40
    assert work_h == 860  # 900 - 0 - 40

def test_get_screen_info_layer2_workarea(monkeypatch):
    """get_screen_info używa _NET_WORKAREA jako fallback gdy STRUT=0."""
    from gui import geometry as geo
    monkeypatch.setattr(geo, "_get_screen_size_xrandr", lambda: (1600, 900))
    monkeypatch.setattr(geo, "get_strut_reserved", lambda: (0, 0, 0, 0))
    fake_xprop = subprocess.CompletedProcess(
        args=[], returncode=0,
        stdout="_NET_WORKAREA(CARDINAL) = 0, 0, 1600, 860\n")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_xprop)
    result = geo.get_screen_info()
    screen_w, screen_h, work_h, top, bottom, left, right = result
    assert work_h == 860
    assert bottom == 40  # 900 - 0 - 860

def test_get_screen_info_layer3_fallback(monkeypatch):
    """get_screen_info zwraca pełny ekran gdy brak info o paskach."""
    from gui import geometry as geo
    monkeypatch.setattr(geo, "_get_screen_size_xrandr", lambda: (1600, 900))
    monkeypatch.setattr(geo, "get_strut_reserved", lambda: (0, 0, 0, 0))
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **kw: subprocess.CompletedProcess(
                            args=[], returncode=0, stdout=""))
    result = geo.get_screen_info()
    screen_w, screen_h, work_h, top, bottom, left, right = result
    assert work_h == screen_h
    assert bottom == 0
    assert top == 0


# ── geometry.py — pozostałe luki ──────────────────────────────────────────────

def test_get_strut_reserved_multiple_windows(monkeypatch):
    """get_strut_reserved zbiera max wartości z wielu okien."""
    from gui import geometry as geo
    import subprocess as sp
    call_count = [0]
    def fake_run(cmd, **kw):
        c = " ".join(cmd)
        if "_NET_CLIENT_LIST" in c:
            return sp.CompletedProcess(args=[], returncode=0,
                stdout="_NET_CLIENT_LIST(WINDOW): 0x1111 0x2222\n")
        if "0x1111" in c:
            return sp.CompletedProcess(args=[], returncode=0,
                stdout="_NET_WM_STRUT_PARTIAL(CARDINAL) = 0, 0, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0\n")
        if "0x2222" in c:
            return sp.CompletedProcess(args=[], returncode=0,
                stdout="_NET_WM_STRUT_PARTIAL(CARDINAL) = 10, 5, 0, 40, 0, 0, 0, 0, 0, 0, 0, 0\n")
        return sp.CompletedProcess(args=[], returncode=0, stdout="")
    monkeypatch.setattr(sp, "run", fake_run)
    top, bottom, left, right = geo.get_strut_reserved()
    assert top    == 30
    assert bottom == 40
    assert left   == 10
    assert right  == 5

def test_get_screen_info_layer2_invalid_workarea(monkeypatch):
    """get_screen_info ignoruje _NET_WORKAREA gdy work_h <= 0."""
    from gui import geometry as geo
    import subprocess as sp
    monkeypatch.setattr(geo, "_get_screen_size_xrandr", lambda: (1600, 900))
    monkeypatch.setattr(geo, "get_strut_reserved", lambda: (0, 0, 0, 0))
    # work_h = 0 — nieprawidłowe, powinno przejść do warstwy 3
    fake = sp.CompletedProcess(args=[], returncode=0,
        stdout="_NET_WORKAREA(CARDINAL) = 0, 0, 1600, 0\n")
    monkeypatch.setattr(sp, "run", lambda *a, **kw: fake)
    result = geo.get_screen_info()
    screen_w, screen_h, work_h, top, bottom, left, right = result
    # Warstwa 3 — work_h == screen_h
    assert work_h == screen_h

def test_get_screen_info_layer2_workarea_too_large(monkeypatch):
    """get_screen_info ignoruje _NET_WORKAREA gdy work_h > screen_h."""
    from gui import geometry as geo
    import subprocess as sp
    monkeypatch.setattr(geo, "_get_screen_size_xrandr", lambda: (1600, 900))
    monkeypatch.setattr(geo, "get_strut_reserved", lambda: (0, 0, 0, 0))
    fake = sp.CompletedProcess(args=[], returncode=0,
        stdout="_NET_WORKAREA(CARDINAL) = 0, 0, 1600, 9999\n")
    monkeypatch.setattr(sp, "run", lambda *a, **kw: fake)
    result = geo.get_screen_info()
    _, screen_h, work_h, _, _, _, _ = result
    assert work_h == screen_h


# ── glsl_io.py — pozostałe luki ───────────────────────────────────────────────

def test_read_flag_defines_non_int_value(tmp_path):
    """read_flag_defines zwraca 0 gdy wartość nie jest int."""
    from gui.modules.glsl_io import read_flag_defines
    from gui.modules.bars import FLAG_PARAMS
    path = str(tmp_path / "bad_flag.glsl")
    key = FLAG_PARAMS[0][0]
    with open(path, "w") as f:
        f.write(f"#define {key} abc\n")
    result = read_flag_defines(path, FLAG_PARAMS)
    assert result[key] == 0

def test_write_smooth_skips_unknown_key(tmp_path):
    """write_smooth pomija klucze spoza smooth_params."""
    from gui.modules.glsl_io import write_smooth
    from gui.core import SMOOTH_PARAMS
    import shutil
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config', 'smooth_parameters.glsl')
    dst = str(tmp_path / "smooth_parameters.glsl")
    shutil.copy2(src, dst)
    # Klucz który nie istnieje w SMOOTH_PARAMS — powinien być cicho pominięty
    with open(dst) as f:
        before = f.read()
    write_smooth(dst, {"nonexistent_key_xyz": 99.9}, SMOOTH_PARAMS)
    with open(dst) as f:
        after = f.read()
    assert before == after  # plik niezmieniony


# ── core.py — pozostałe luki ──────────────────────────────────────────────────

def test_load_lang_fallback_to_en(tmp_path, monkeypatch):
    """load_lang z nieznanym kodem zwraca zawartość en.json."""
    import json
    from gui import core as core_mod
    lang_dir = str(tmp_path / "lang")
    os.makedirs(lang_dir)
    en_data = {"lang_name": "English", "test_key": "test_value"}
    with open(os.path.join(lang_dir, "en.json"), "w") as f:
        json.dump(en_data, f)
    monkeypatch.setattr(core_mod, "LANG_DIR", lang_dir)
    result = core_mod.load_lang("xx_nonexistent")
    assert result.get("test_key") == "test_value"

def test_load_lang_no_fallback_returns_empty(tmp_path, monkeypatch):
    """load_lang zwraca {} gdy brak pliku i brak en.json."""
    from gui import core as core_mod
    empty_dir = str(tmp_path / "empty_lang")
    os.makedirs(empty_dir)
    monkeypatch.setattr(core_mod, "LANG_DIR", empty_dir)
    result = core_mod.load_lang("xx_nonexistent")
    assert result == {}

def test_available_langs_corrupt_json(tmp_path, monkeypatch):
    """available_langs używa kodu jako nazwy gdy plik jest uszkodzony."""
    import json
    from gui import core as core_mod
    lang_dir = str(tmp_path / "lang")
    os.makedirs(lang_dir)
    with open(os.path.join(lang_dir, "pl.json"), "w") as f:
        f.write("{ invalid json }")
    monkeypatch.setattr(core_mod, "LANG_DIR", lang_dir)
    result = core_mod.available_langs()
    assert "pl" in result
    assert result["pl"] == "pl"  # fallback: kod jako nazwa
