# =============================================================================
# tests/test_glsl_io.py
# Testy jednostkowe dla gui/modules/glsl_io.py
# Pokrywa: read/write_defines, read/write_flag_defines, read/write_smooth,
#          read/write_int_req, read/write_bool_req, write_request,
#          read_raw, write_define_int, write_define_float, write_define_raw,
#          read_all_defines, decimals
# Bez tkinter — wszystkie funkcje IO są środowiskowo neutralne.
# =============================================================================

import os
import re
import sys
import pytest

# ---------------------------------------------------------------------------
# Stub tkinter żeby glsl_io.py dał się zaimportować bez wyświetlacza
# ---------------------------------------------------------------------------
import types

tk_stub = types.ModuleType("tkinter")
tk_stub.ttk = types.ModuleType("tkinter.ttk")
tk_stub.Toplevel = None
sys.modules.setdefault("tkinter", tk_stub)
sys.modules.setdefault("tkinter.ttk", tk_stub.ttk)

# Dodaj scripts/ do ścieżki
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from gui.modules.glsl_io import (
    decimals,
    read_defines,
    write_defines,
    read_flag_defines,
    write_flag_defines,
    read_raw,
    read_all_defines,
    write_define_int,
    write_define_float,
    write_define_raw,
    read_smooth,
    write_smooth,
    read_int_req,
    write_int_req,
    read_bool_req,
    write_bool_req,
    write_request,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def glsl_file(tmp_path):
    """Zwraca funkcję tworzącą plik .glsl z podaną zawartością."""
    def _make(content, name="test.glsl"):
        p = tmp_path / name
        p.write_text(content)
        return str(p)
    return _make


# ---------------------------------------------------------------------------
# decimals()
# ---------------------------------------------------------------------------

class TestDecimals:
    def test_integer_step(self):
        assert decimals(1) == 0

    def test_one_decimal(self):
        assert decimals(0.1) == 1

    def test_two_decimals(self):
        assert decimals(0.01) == 2

    def test_trailing_zero_stripped(self):
        # 0.10 → "0.1" → 1 miejsce
        assert decimals(0.10) == 1

    def test_large_integer(self):
        assert decimals(100) == 0


# ---------------------------------------------------------------------------
# read_defines / write_defines
# ---------------------------------------------------------------------------

SHAPE_PARAMS = [
    ("BAR_WIDTH",  "Szerokość", 1, 40,  5, "px", "tooltip"),
    ("BAR_GAP",    "Odstęp",    0, 20,  1, "px", "tooltip"),
    ("AMPLIFY",    "Wzmocnienie", 50, 800, 300, "",  "tooltip"),
]

class TestReadDefines:
    def test_reads_existing_values(self, glsl_file):
        path = glsl_file("#define BAR_WIDTH 10\n#define BAR_GAP 3\n#define AMPLIFY 500\n")
        result = read_defines(path, SHAPE_PARAMS)
        assert result["BAR_WIDTH"] == 10
        assert result["BAR_GAP"]   == 3
        assert result["AMPLIFY"]   == 500

    def test_returns_defaults_for_missing_keys(self, glsl_file):
        path = glsl_file("#define BAR_WIDTH 10\n")
        result = read_defines(path, SHAPE_PARAMS)
        assert result["BAR_GAP"]  == 1    # default z SHAPE_PARAMS
        assert result["AMPLIFY"]  == 300

    def test_nonexistent_file_returns_defaults(self, tmp_path):
        result = read_defines(str(tmp_path / "missing.glsl"), SHAPE_PARAMS)
        assert result == {p[0]: p[4] for p in SHAPE_PARAMS}

    def test_ignores_invalid_value(self, glsl_file):
        path = glsl_file("#define BAR_WIDTH not_a_number\n")
        result = read_defines(path, SHAPE_PARAMS)
        assert result["BAR_WIDTH"] == 5   # fallback do default


class TestWriteDefines:
    def test_updates_existing_define(self, glsl_file):
        path = glsl_file("#define BAR_WIDTH 5\n#define BAR_GAP 1\n")
        write_defines(path, {"BAR_WIDTH": 15}, SHAPE_PARAMS)
        content = open(path).read()
        assert "#define BAR_WIDTH 15" in content
        assert "#define BAR_GAP 1" in content

    def test_appends_missing_define(self, glsl_file):
        path = glsl_file("// shader\n#define BAR_GAP 1\n")
        write_defines(path, {"BAR_WIDTH": 7}, SHAPE_PARAMS)
        content = open(path).read()
        assert "#define BAR_WIDTH 7" in content

    def test_deduplicates_define(self, glsl_file):
        path = glsl_file("#define BAR_WIDTH 5\n#define BAR_WIDTH 5\n")
        write_defines(path, {"BAR_WIDTH": 20}, SHAPE_PARAMS)
        content = open(path).read()
        assert content.count("#define BAR_WIDTH") == 1
        assert "#define BAR_WIDTH 20" in content

    def test_ignores_unknown_key(self, glsl_file):
        path = glsl_file("#define BAR_WIDTH 5\n")
        original = open(path).read()
        write_defines(path, {"UNKNOWN_KEY": 99}, SHAPE_PARAMS)
        assert open(path).read() == original

    def test_no_op_on_missing_file(self, tmp_path):
        # Nie rzuca wyjątku gdy plik nie istnieje
        write_defines(str(tmp_path / "missing.glsl"), {"BAR_WIDTH": 5}, SHAPE_PARAMS)


# ---------------------------------------------------------------------------
# read_flag_defines / write_flag_defines
# ---------------------------------------------------------------------------

FLAG_PARAMS = [
    ("DIRECTION",    "Odwróć",  "tooltip"),
    ("FLIP",         "Odbicie", "tooltip"),
    ("MIRROR_YX",    "Obrót",   "tooltip"),
]

class TestFlagDefines:
    def test_reads_flags(self, glsl_file):
        path = glsl_file("#define DIRECTION 1\n#define FLIP 0\n#define MIRROR_YX 1\n")
        result = read_flag_defines(path, FLAG_PARAMS)
        assert result["DIRECTION"] == 1
        assert result["FLIP"]      == 0
        assert result["MIRROR_YX"] == 1

    def test_defaults_to_zero(self, glsl_file):
        path = glsl_file("// brak flag\n")
        result = read_flag_defines(path, FLAG_PARAMS)
        assert result == {"DIRECTION": 0, "FLIP": 0, "MIRROR_YX": 0}

    def test_writes_flag(self, glsl_file):
        path = glsl_file("#define DIRECTION 0\n#define FLIP 0\n")
        write_flag_defines(path, {"FLIP": 1}, FLAG_PARAMS)
        content = open(path).read()
        assert "#define FLIP 1" in content
        assert "#define DIRECTION 0" in content

    def test_missing_file_no_crash(self, tmp_path):
        write_flag_defines(str(tmp_path / "x.glsl"), {"FLIP": 1}, FLAG_PARAMS)


# ---------------------------------------------------------------------------
# read_raw / read_all_defines
# ---------------------------------------------------------------------------

class TestReadRaw:
    def test_reads_string_values(self, glsl_file):
        path = glsl_file("#define ANGLE 3.14159\n#define SCALE 2.0\n")
        result = read_raw(path)
        assert result["ANGLE"] == "3.14159"
        assert result["SCALE"] == "2.0"

    def test_no_duplicate_keys(self, glsl_file):
        path = glsl_file("#define K 1\n#define K 2\n")
        result = read_raw(path)
        assert result["K"] == "1"   # pierwszy wpis wygrywa

    def test_missing_file_empty_dict(self, tmp_path):
        assert read_raw(str(tmp_path / "missing.glsl")) == {}

    def test_read_all_defines_same_as_read_raw(self, glsl_file):
        path = glsl_file("#define FOO bar\n#define BAZ 42\n")
        assert read_all_defines(path) == read_raw(path)


# ---------------------------------------------------------------------------
# write_define_int / write_define_float / write_define_raw
# ---------------------------------------------------------------------------

class TestWriteDefineVariants:
    def test_write_define_int_replaces(self, glsl_file):
        path = glsl_file("#define COUNT 5\n")
        write_define_int(path, "COUNT", 10)
        assert "#define COUNT 10" in open(path).read()

    def test_write_define_int_appends(self, glsl_file):
        path = glsl_file("// shader\n")
        write_define_int(path, "NEW_KEY", 7)
        assert "#define NEW_KEY 7" in open(path).read()

    def test_write_define_float_precision(self, glsl_file):
        path = glsl_file("#define SCALE 1.0\n")
        write_define_float(path, "SCALE", 1.5, step=0.1)
        assert "#define SCALE 1.5" in open(path).read()

    def test_write_define_float_two_decimals(self, glsl_file):
        path = glsl_file("#define SCALE 1.00\n")
        write_define_float(path, "SCALE", 1.23, step=0.01)
        assert "#define SCALE 1.23" in open(path).read()

    def test_write_define_raw_expression(self, glsl_file):
        path = glsl_file("#define ANGLE 3.14\n")
        write_define_raw(path, "ANGLE", "3.14159 * 2.0")
        assert "#define ANGLE 3.14159 * 2.0" in open(path).read()

    def test_write_define_int_missing_file_no_crash(self, tmp_path):
        write_define_int(str(tmp_path / "x.glsl"), "K", 1)

    def test_write_define_raw_missing_file_no_crash(self, tmp_path):
        write_define_raw(str(tmp_path / "x.glsl"), "K", "val")


# ---------------------------------------------------------------------------
# read_smooth / write_smooth
# ---------------------------------------------------------------------------

# 8-krotki: (klucz, etykieta, min, max, domyślna, jednostka, krok, tooltip)
SMOOTH_PARAMS = [
    ("setgravitystep",  "Grawitacja",    0.1, 10.0, 2.0, "",   0.1, "tip"),
    ("setsmoothfactor", "Wygładzenie",   0.0,  1.0, 0.5, "",  0.01, "tip"),
    ("setavgframes",    "Śr. ramek",       1,   30,   4, "",     1, "tip"),
]

class TestSmooth:
    def test_reads_float_params(self, glsl_file):
        path = glsl_file(
            "#request setgravitystep 3.5\n"
            "#request setsmoothfactor 0.75\n"
            "#request setavgframes 8\n"
        )
        result = read_smooth(path, SMOOTH_PARAMS)
        assert result["setgravitystep"]  == pytest.approx(3.5)
        assert result["setsmoothfactor"] == pytest.approx(0.75)
        assert result["setavgframes"]    == 8   # int

    def test_defaults_on_missing_file(self, tmp_path):
        result = read_smooth(str(tmp_path / "x.glsl"), SMOOTH_PARAMS)
        assert result["setgravitystep"]  == 2.0
        assert result["setsmoothfactor"] == 0.5
        assert result["setavgframes"]    == 4

    def test_writes_float_params(self, glsl_file):
        path = glsl_file(
            "#request setgravitystep 2.0\n"
            "#request setsmoothfactor 0.5\n"
        )
        write_smooth(path, {"setgravitystep": 5.0}, SMOOTH_PARAMS)
        content = open(path).read()
        assert "#request setgravitystep 5.0" in content
        assert "#request setsmoothfactor 0.5" in content  # niezmieniony

    def test_writes_avgframes_as_int(self, glsl_file):
        path = glsl_file("#request setavgframes 4\n")
        write_smooth(path, {"setavgframes": 12}, SMOOTH_PARAMS)
        assert "#request setavgframes 12" in open(path).read()

    def test_write_smooth_missing_file_no_crash(self, tmp_path):
        write_smooth(str(tmp_path / "x.glsl"), {"setgravitystep": 1.0}, SMOOTH_PARAMS)


# ---------------------------------------------------------------------------
# read_int_req / write_int_req
# ---------------------------------------------------------------------------

class TestIntReq:
    def test_reads_value(self, glsl_file):
        path = glsl_file("#request setfps 60\n")
        assert read_int_req(path, "setfps", 30) == {"setfps": 60}

    def test_returns_default_when_missing(self, glsl_file):
        path = glsl_file("// brak\n")
        assert read_int_req(path, "setfps", 30) == {"setfps": 30}

    def test_returns_default_on_missing_file(self, tmp_path):
        result = read_int_req(str(tmp_path / "x.glsl"), "setfps", 30)
        assert result == {"setfps": 30}

    def test_writes_value(self, glsl_file):
        path = glsl_file("#request setfps 30\n")
        write_int_req(path, "setfps", 60)
        assert "#request setfps 60" in open(path).read()

    def test_write_no_op_on_missing_file(self, tmp_path):
        write_int_req(str(tmp_path / "x.glsl"), "setfps", 60)


# ---------------------------------------------------------------------------
# read_bool_req / write_bool_req
# ---------------------------------------------------------------------------

class TestBoolReq:
    def test_reads_true(self, glsl_file):
        path = glsl_file("#request setmirror true\n")
        assert read_bool_req(path, "setmirror") == {"setmirror": True}

    def test_reads_false(self, glsl_file):
        path = glsl_file("#request setmirror false\n")
        assert read_bool_req(path, "setmirror") == {"setmirror": False}

    def test_missing_key_returns_false(self, glsl_file):
        path = glsl_file("// brak\n")
        assert read_bool_req(path, "setmirror") == {"setmirror": False}

    def test_missing_file_returns_false(self, tmp_path):
        result = read_bool_req(str(tmp_path / "x.glsl"), "setmirror")
        assert result == {"setmirror": False}

    def test_writes_true(self, glsl_file):
        path = glsl_file("#request setmirror false\n")
        write_bool_req(path, "setmirror", True)
        assert "#request setmirror true" in open(path).read()

    def test_writes_false(self, glsl_file):
        path = glsl_file("#request setmirror true\n")
        write_bool_req(path, "setmirror", False)
        assert "#request setmirror false" in open(path).read()

    def test_write_no_op_on_missing_file(self, tmp_path):
        write_bool_req(str(tmp_path / "x.glsl"), "setmirror", True)


# ---------------------------------------------------------------------------
# write_request (surowy string)
# ---------------------------------------------------------------------------

class TestWriteRequest:
    def test_writes_string_value(self, glsl_file):
        path = glsl_file("#request mod bars\n")
        write_request(path, "mod", "wave")
        assert "#request mod wave" in open(path).read()

    def test_no_op_when_key_missing(self, glsl_file):
        path = glsl_file("// brak mod\n")
        original = open(path).read()
        write_request(path, "mod", "wave")
        assert open(path).read() == original

    def test_no_op_on_missing_file(self, tmp_path):
        write_request(str(tmp_path / "x.glsl"), "mod", "wave")
