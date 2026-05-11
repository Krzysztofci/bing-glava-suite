import pytest
import os
import sys

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def inst0_paths(tmp_path):
    """Fake inst-0 z plikami GLSL."""
    import glob, shutil
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    glava_dir = tmp_path / "glava"
    glava_dir.mkdir()
    for f in glob.glob(os.path.join(src, "*.glsl")):
        shutil.copy2(f, str(glava_dir))
    return tmp_path

@pytest.fixture
def mock_inst0(inst0_paths, monkeypatch):
    from gui import instance
    monkeypatch.setattr(instance, "USER_HOME", str(inst0_paths))
    # Przeładuj GlavaInstance z nowym USER_HOME
    from gui.instance import GlavaInstance
    return GlavaInstance

# ── Ścieżki inst-0 ────────────────────────────────────────────────────────────

def test_inst0_glava_dir(mock_inst0, inst0_paths):
    i = mock_inst0(0)
    assert i.glava_dir == str(inst0_paths / ".config" / "glava") or \
           i.glava_dir.endswith(".config/glava")

def test_inst0_rc_glsl(mock_inst0):
    i = mock_inst0(0)
    assert i.rc_glsl.endswith("rc.glsl")

def test_inst0_module_glsl(mock_inst0):
    i = mock_inst0(0)
    assert i.module_glsl("bars").endswith("bars.glsl")
    assert i.module_glsl("circle").endswith("circle.glsl")

def test_inst1_paths(mock_inst0):
    i = mock_inst0(1)
    assert "glava-inst-1" in i.xdg_dir
    assert "glava-inst-1" in i.glava_dir
    assert "inst-1" in i.conf_dir

# ── create / destroy ──────────────────────────────────────────────────────────

def test_create_copies_glsl(tmp_path, monkeypatch):
    import glob, shutil
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))

    # Przygotuj inst-0
    glava_dir = tmp_path / ".config" / "glava"
    glava_dir.mkdir(parents=True)
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    for f in glob.glob(os.path.join(src, "*.glsl")):
        shutil.copy2(f, str(glava_dir))

    from gui.instance import GlavaInstance
    i1 = GlavaInstance(1)
    assert not i1.exists()
    i1.create()
    assert i1.exists()
    assert os.path.isfile(os.path.join(i1.glava_dir, "bars.glsl"))
    assert os.path.isfile(os.path.join(i1.glava_dir, "rc.glsl"))

def test_create_idempotent(tmp_path, monkeypatch):
    """Wywołanie create() dwa razy nie crashuje."""
    import glob, shutil
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))

    glava_dir = tmp_path / ".config" / "glava"
    glava_dir.mkdir(parents=True)
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    for f in glob.glob(os.path.join(src, "*.glsl")):
        shutil.copy2(f, str(glava_dir))

    from gui.instance import GlavaInstance
    i1 = GlavaInstance(1)
    i1.create()
    i1.create()  # drugi raz nie powinien crashować
    assert i1.exists()

def test_destroy_removes_dir(tmp_path, monkeypatch):
    import glob, shutil
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))

    glava_dir = tmp_path / ".config" / "glava"
    glava_dir.mkdir(parents=True)
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    for f in glob.glob(os.path.join(src, "*.glsl")):
        shutil.copy2(f, str(glava_dir))

    from gui.instance import GlavaInstance
    i1 = GlavaInstance(1)
    i1.create()
    assert i1.exists()
    i1.destroy()
    assert not i1.exists()

def test_destroy_inst0_raises(mock_inst0):
    """destroy() na inst-0 musi rzucić ValueError."""
    i0 = mock_inst0(0)
    with pytest.raises(ValueError):
        i0.destroy()
