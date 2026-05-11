import pytest
from gui.modules import glsl_io

# ── read/write defines ────────────────────────────────────────────────────────

def test_read_defines_basic(bars_glsl):
    result = glsl_io.read_raw(bars_glsl)
    assert isinstance(result, dict)
    assert "BAR_WIDTH" in result

def test_write_defines_roundtrip(bars_glsl):
    """Zapis i odczyt wartości int przez write_defines/read_defines."""
    from gui.modules.bars import SHAPE_PARAMS
    original = glsl_io.read_defines(bars_glsl, SHAPE_PARAMS)
    new_vals = {k: v + 1 for k, v in original.items()}
    glsl_io.write_defines(bars_glsl, new_vals, SHAPE_PARAMS)
    result = glsl_io.read_defines(bars_glsl, SHAPE_PARAMS)
    for k in original:
        assert result[k] == new_vals[k], f"{k}: expected {new_vals[k]}, got {result[k]}"

def test_write_defines_clamps_to_range(bars_glsl):
    """write_defines nie powinno zapisać wartości spoza zakresu param_def."""
    from gui.modules.bars import SHAPE_PARAMS
    # Znajdź pierwszy param z ograniczonym zakresem
    p = SHAPE_PARAMS[0]
    key, vmin, vmax = p[0], p[2], p[3]
    glsl_io.write_defines(bars_glsl, {key: vmin}, SHAPE_PARAMS)
    result = glsl_io.read_defines(bars_glsl, SHAPE_PARAMS)
    assert result[key] == vmin

# ── read/write smooth ─────────────────────────────────────────────────────────

def test_write_smooth_roundtrip(smooth_glsl):
    """Zapis i odczyt wartości float przez write_smooth/read_smooth."""
    from gui.core import SMOOTH_PARAMS
    original = glsl_io.read_smooth(smooth_glsl, SMOOTH_PARAMS)
    # Zmień pierwszą wartość
    key = SMOOTH_PARAMS[0][0]
    step = SMOOTH_PARAMS[0][6]
    new_val = original[key] + step
    glsl_io.write_smooth(smooth_glsl, {key: new_val}, SMOOTH_PARAMS)
    result = glsl_io.read_smooth(smooth_glsl, SMOOTH_PARAMS)
    assert abs(result[key] - new_val) < step * 0.01

# ── write_int_req ─────────────────────────────────────────────────────────────

def test_write_int_req_roundtrip(rc_glsl):
    """Zapis i odczyt #request przez write_int_req."""
    glsl_io.write_int_req(rc_glsl, "setframerate", 30)
    with open(rc_glsl) as f:
        content = f.read()
    assert "#request setframerate 30" in content

def test_write_int_req_overwrites(rc_glsl):
    """write_int_req nadpisuje istniejącą wartość, nie duplikuje."""
    glsl_io.write_int_req(rc_glsl, "setframerate", 30)
    glsl_io.write_int_req(rc_glsl, "setframerate", 60)
    with open(rc_glsl) as f:
        content = f.read()
    assert content.count("setframerate") == content.count("#request setframerate")
    assert "#request setframerate 60" in content
    assert "#request setframerate 30" not in content

# ── write_define_int / write_define_float ─────────────────────────────────────

def test_write_define_int_roundtrip(bars_glsl):
    glsl_io.write_define_int(bars_glsl, "BAR_WIDTH", 99)
    result = glsl_io.read_raw(bars_glsl)
    assert int(result["BAR_WIDTH"]) == 99

def test_write_define_float_roundtrip(smooth_glsl):
    glsl_io.write_define_float(smooth_glsl, "TEST_FLOAT", 3.14, 0.01)
    result = glsl_io.read_raw(smooth_glsl)
    assert abs(float(result["TEST_FLOAT"]) - 3.14) < 0.001
