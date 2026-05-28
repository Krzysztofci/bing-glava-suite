import pytest
import os
import shutil

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def glsl_file(tmp_path):
    """Kopia bars.glsl w katalogu tymczasowym."""
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config', 'bars.glsl')
    dst = str(tmp_path / "bars.glsl")
    shutil.copy2(src, dst)
    return dst

@pytest.fixture
def rc_file(tmp_path):
    """Kopia rc.glsl w katalogu tymczasowym."""
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config', 'rc.glsl')
    dst = str(tmp_path / "rc.glsl")
    shutil.copy2(src, dst)
    return dst

@pytest.fixture
def blank_glsl(tmp_path):
    """Pusty plik .glsl z kilkoma przykładowymi definicjami."""
    path = str(tmp_path / "test.glsl")
    with open(path, "w") as f:
        f.write("#define FOO 1\n#define BAR 0\n#request setframerate 60\n")
    return path

# ── decimals ──────────────────────────────────────────────────────────────────

def test_decimals_integer():
    from gui.modules.glsl_io import decimals
    assert decimals(1) == 0
    assert decimals(5) == 0

def test_decimals_one_place():
    from gui.modules.glsl_io import decimals
    assert decimals(0.1) == 1

def test_decimals_three_places():
    from gui.modules.glsl_io import decimals
    assert decimals(0.001) == 3

def test_decimals_trailing_zeros():
    from gui.modules.glsl_io import decimals
    assert decimals(0.10) == 1

# ── read_flag_defines / write_flag_defines ────────────────────────────────────

def test_read_flag_defines_basic(glsl_file):
    from gui.modules.glsl_io import read_flag_defines
    from gui.modules.bars import FLAG_PARAMS
    result = read_flag_defines(glsl_file, FLAG_PARAMS)
    assert isinstance(result, dict)
    for p in FLAG_PARAMS:
        assert p[0] in result
        assert result[p[0]] in (0, 1)

def test_write_flag_defines_set_one(glsl_file):
    from gui.modules.glsl_io import read_flag_defines, write_flag_defines
    from gui.modules.bars import FLAG_PARAMS
    key = FLAG_PARAMS[0][0]
    original = read_flag_defines(glsl_file, FLAG_PARAMS)[key]
    new_val = 1 - original  # flip 0→1 lub 1→0
    write_flag_defines(glsl_file, {key: new_val}, FLAG_PARAMS)
    result = read_flag_defines(glsl_file, FLAG_PARAMS)
    assert result[key] == new_val

def test_write_flag_defines_all(glsl_file):
    from gui.modules.glsl_io import read_flag_defines, write_flag_defines
    from gui.modules.bars import FLAG_PARAMS
    write_flag_defines(glsl_file, {p[0]: 1 for p in FLAG_PARAMS}, FLAG_PARAMS)
    result = read_flag_defines(glsl_file, FLAG_PARAMS)
    for p in FLAG_PARAMS:
        assert result[p[0]] == 1

def test_write_flag_defines_no_duplicate(glsl_file):
    from gui.modules.glsl_io import write_flag_defines
    from gui.modules.bars import FLAG_PARAMS
    key = FLAG_PARAMS[0][0]
    write_flag_defines(glsl_file, {key: 1}, FLAG_PARAMS)
    write_flag_defines(glsl_file, {key: 0}, FLAG_PARAMS)
    with open(glsl_file) as f:
        content = f.read()
    assert content.count(f"#define {key}") == 1

def test_read_flag_defines_missing_file(tmp_path):
    from gui.modules.glsl_io import read_flag_defines
    from gui.modules.bars import FLAG_PARAMS
    result = read_flag_defines(str(tmp_path / "nonexistent.glsl"), FLAG_PARAMS)
    for p in FLAG_PARAMS:
        assert result[p[0]] == 0

# ── write_define_raw ──────────────────────────────────────────────────────────

def test_write_define_raw_string(glsl_file):
    from gui.modules.glsl_io import write_define_raw, read_raw
    write_define_raw(glsl_file, "BAR_WIDTH", "3.14159*2")
    result = read_raw(glsl_file)
    assert result["BAR_WIDTH"] == "3.14159*2"

def test_write_define_raw_overwrites(glsl_file):
    from gui.modules.glsl_io import write_define_raw, read_raw
    write_define_raw(glsl_file, "BAR_WIDTH", "AAA")
    write_define_raw(glsl_file, "BAR_WIDTH", "BBB")
    result = read_raw(glsl_file)
    assert result["BAR_WIDTH"] == "BBB"

def test_write_define_raw_missing_file(tmp_path):
    from gui.modules.glsl_io import write_define_raw
    write_define_raw(str(tmp_path / "nonexistent.glsl"), "KEY", "val")

# ── read_int_req ──────────────────────────────────────────────────────────────

def test_read_int_req_existing(rc_file):
    from gui.modules.glsl_io import write_int_req, read_int_req
    write_int_req(rc_file, "setframerate", 45)
    result = read_int_req(rc_file, "setframerate", 60)
    assert result["setframerate"] == 45

def test_read_int_req_default(rc_file):
    from gui.modules.glsl_io import read_int_req
    result = read_int_req(rc_file, "nonexistent_key_xyz", 99)
    assert result["nonexistent_key_xyz"] == 99

def test_read_int_req_missing_file(tmp_path):
    from gui.modules.glsl_io import read_int_req
    result = read_int_req(str(tmp_path / "nonexistent.glsl"), "key", 42)
    assert result["key"] == 42

# ── read_bool_req / write_bool_req ────────────────────────────────────────────

def test_write_bool_req_true(rc_file):
    """setfloating istnieje w rc.glsl — write_bool_req zastępuje istniejącą wartość."""
    from gui.modules.glsl_io import write_bool_req, read_bool_req
    write_bool_req(rc_file, "setfloating", True)
    result = read_bool_req(rc_file, "setfloating")
    assert result["setfloating"] == True

def test_write_bool_req_false(rc_file):
    from gui.modules.glsl_io import write_bool_req, read_bool_req
    write_bool_req(rc_file, "setfloating", True)
    write_bool_req(rc_file, "setfloating", False)
    result = read_bool_req(rc_file, "setfloating")
    assert result["setfloating"] == False

def test_read_bool_req_missing_key(rc_file):
    from gui.modules.glsl_io import read_bool_req
    result = read_bool_req(rc_file, "nonexistent_key_xyz")
    assert result["nonexistent_key_xyz"] == False

def test_read_bool_req_missing_file(tmp_path):
    from gui.modules.glsl_io import read_bool_req
    result = read_bool_req(str(tmp_path / "nonexistent.glsl"), "key")
    assert result["key"] == False

# ── write_request ─────────────────────────────────────────────────────────────

def test_write_request_string(rc_file):
    from gui.modules.glsl_io import write_request
    write_request(rc_file, "setframerate", "120")
    with open(rc_file) as f:
        content = f.read()
    assert "#request setframerate 120" in content

def test_write_request_overwrites(rc_file):
    from gui.modules.glsl_io import write_request
    write_request(rc_file, "setframerate", "30")
    write_request(rc_file, "setframerate", "144")
    with open(rc_file) as f:
        content = f.read()
    assert "#request setframerate 144" in content
    assert "#request setframerate 30" not in content

def test_write_request_missing_file(tmp_path):
    from gui.modules.glsl_io import write_request
    write_request(str(tmp_path / "nonexistent.glsl"), "key", "val")

# ── read_all_defines ──────────────────────────────────────────────────────────

def test_read_all_defines_basic(glsl_file):
    from gui.modules.glsl_io import read_all_defines
    result = read_all_defines(glsl_file)
    assert isinstance(result, dict)
    assert len(result) > 0

def test_read_all_defines_values_are_strings(glsl_file):
    from gui.modules.glsl_io import read_all_defines
    for k, v in read_all_defines(glsl_file).items():
        assert isinstance(k, str)
        assert isinstance(v, str)

def test_read_all_defines_vs_read_raw(glsl_file):
    """read_all_defines i read_raw zwracają te same klucze."""
    from gui.modules.glsl_io import read_all_defines, read_raw
    all_d = read_all_defines(glsl_file)
    raw   = read_raw(glsl_file)
    assert set(all_d.keys()) == set(raw.keys())

def test_read_all_defines_missing_file(tmp_path):
    from gui.modules.glsl_io import read_all_defines
    assert read_all_defines(str(tmp_path / "nonexistent.glsl")) == {}

def test_read_all_defines_after_write(glsl_file):
    from gui.modules.glsl_io import read_all_defines, write_define_int
    write_define_int(glsl_file, "BAR_WIDTH", 77)
    result = read_all_defines(glsl_file)
    assert result["BAR_WIDTH"] == "77"
