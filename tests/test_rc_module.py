import pytest
import os
import shutil
import glob

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def rc_file(tmp_path):
    """Kopia rc.glsl z glava-config/ w katalogu tymczasowym."""
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config', 'rc.glsl')
    dst = str(tmp_path / "rc.glsl")
    shutil.copy2(src, dst)
    return dst

# ── _write_rc_module ──────────────────────────────────────────────────────────

def test_write_rc_module_changes_module(rc_file):
    from gui.glava import _write_rc_module
    _write_rc_module("circle", rc_path=rc_file)
    with open(rc_file) as f:
        content = f.read()
    assert "#request mod circle" in content

def test_write_rc_module_all_modules(rc_file):
    from gui.glava import _write_rc_module
    from gui.core import GLAVA_MODULES
    for mod in GLAVA_MODULES:
        _write_rc_module(mod, rc_path=rc_file)
        with open(rc_file) as f:
            content = f.read()
        assert f"#request mod {mod}" in content

def test_write_rc_module_no_duplicate(rc_file):
    """Wielokrotny zapis nie duplikuje linii #request mod."""
    from gui.glava import _write_rc_module
    _write_rc_module("bars", rc_path=rc_file)
    _write_rc_module("wave", rc_path=rc_file)
    with open(rc_file) as f:
        content = f.read()
    assert content.count("#request mod") == 1

def test_write_rc_module_missing_file(tmp_path):
    """Brak pliku rc.glsl nie crashuje."""
    from gui.glava import _write_rc_module
    _write_rc_module("bars", rc_path=str(tmp_path / "nonexistent.glsl"))

# ── read_rc_module ────────────────────────────────────────────────────────────

def test_read_rc_module_after_write(rc_file):
    from gui.glava import _write_rc_module, read_rc_module
    _write_rc_module("radial", rc_path=rc_file)
    assert read_rc_module(rc_path=rc_file) == "radial"

def test_read_rc_module_all_modules(rc_file):
    from gui.glava import _write_rc_module, read_rc_module
    from gui.core import GLAVA_MODULES
    for mod in GLAVA_MODULES:
        _write_rc_module(mod, rc_path=rc_file)
        assert read_rc_module(rc_path=rc_file) == mod

def test_read_rc_module_unknown_returns_none(rc_file):
    """Nieznany moduł w rc.glsl zwraca None."""
    from gui.glava import read_rc_module
    with open(rc_file, "w") as f:
        f.write("#request mod nonexistent_module\n")
    assert read_rc_module(rc_path=rc_file) is None

def test_read_rc_module_missing_file(tmp_path):
    from gui.glava import read_rc_module
    assert read_rc_module(rc_path=str(tmp_path / "nonexistent.glsl")) is None

def test_write_read_roundtrip(rc_file):
    from gui.glava import _write_rc_module, read_rc_module
    _write_rc_module("graph", rc_path=rc_file)
    assert read_rc_module(rc_path=rc_file) == "graph"
