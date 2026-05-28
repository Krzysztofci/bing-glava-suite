import pytest
import os
import glob
import shutil

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_home(tmp_path):
    """
    Tworzy fałszywy HOME z szablonem ~/.config/glava (pliki GLSL z glava-config/).
    """
    glava_dir = tmp_path / ".config" / "glava"
    glava_dir.mkdir(parents=True)
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    for f in glob.glob(os.path.join(src, "*.glsl")):
        shutil.copy2(f, str(glava_dir))
    return tmp_path


def make_inst(inst_mod, inst_id, fake_home):
    """Skrót: GlavaInstance z home=fake_home."""
    return inst_mod.GlavaInstance(inst_id, home=str(fake_home))


# ── Ścieżki ───────────────────────────────────────────────────────────────────

def test_inst0_paths(fake_home, monkeypatch):
    """inst-0 buduje ścieżki względem podanego home."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(fake_home))
    i = make_inst(inst_mod, 0, fake_home)
    assert str(fake_home) in i.xdg_dir
    assert "glava-inst-0" in i.xdg_dir
    assert i.rc_glsl.endswith("rc.glsl")

def test_inst1_paths(fake_home, monkeypatch):
    """inst-1 zawiera 'glava-inst-1' w ścieżkach."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(fake_home))
    i = make_inst(inst_mod, 1, fake_home)
    assert "glava-inst-1" in i.xdg_dir
    assert "glava-inst-1" in i.glava_dir
    assert "inst-1" in i.conf_dir

def test_inst0_module_glsl(fake_home, monkeypatch):
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(fake_home))
    i = make_inst(inst_mod, 0, fake_home)
    assert i.module_glsl("bars").endswith("bars.glsl")
    assert i.module_glsl("circle").endswith("circle.glsl")

def test_inst0_profiles_file(fake_home, monkeypatch):
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(fake_home))
    i = make_inst(inst_mod, 0, fake_home)
    assert i.profiles_file.endswith("profiles.json")
    assert str(fake_home) in i.profiles_file

# ── create() ──────────────────────────────────────────────────────────────────

def test_create_copies_glsl(fake_home, monkeypatch):
    """create() kopiuje pliki GLSL z szablonu ~/.config/glava."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(fake_home))
    i = make_inst(inst_mod, 1, fake_home)
    assert not i.exists()
    i.create()
    assert i.exists()
    assert os.path.isfile(os.path.join(i.glava_dir, "bars.glsl"))
    assert os.path.isfile(os.path.join(i.glava_dir, "rc.glsl"))

def test_create_idempotent(fake_home, monkeypatch):
    """Wywołanie create() dwa razy nie crashuje i katalog istnieje."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(fake_home))
    i = make_inst(inst_mod, 1, fake_home)
    i.create()
    i.create()
    assert i.exists()

def test_create_from_source(fake_home, monkeypatch):
    """create(source=inst0) kopiuje z instancji źródłowej."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(fake_home))
    i0 = make_inst(inst_mod, 0, fake_home)
    i0.create()
    i1 = make_inst(inst_mod, 1, fake_home)
    i1.create(source=i0)
    assert i1.exists()
    assert os.path.isfile(os.path.join(i1.glava_dir, "rc.glsl"))

def test_create_fallback_to_etc(tmp_path, monkeypatch):
    """create() gdy brak ~/.config/glava nie crashuje (fallback /etc/xdg/glava)."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))
    i = inst_mod.GlavaInstance(1, home=str(tmp_path))
    try:
        i.create()
    except Exception as e:
        pytest.fail(f"create() rzucił wyjątek przy braku szablonu: {e}")

def test_create_makes_conf_dir(fake_home, monkeypatch):
    """create() tworzy też conf_dir."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(fake_home))
    i = make_inst(inst_mod, 2, fake_home)
    i.create()
    assert os.path.isdir(i.conf_dir)

# ── destroy() ─────────────────────────────────────────────────────────────────

def test_destroy_removes_dirs(fake_home, monkeypatch):
    """destroy() usuwa xdg_dir i conf_dir instancji."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(fake_home))
    i = make_inst(inst_mod, 1, fake_home)
    i.create()
    assert i.exists()
    i.destroy()
    assert not i.exists()
    assert not os.path.isdir(i.conf_dir)

def test_destroy_nonexistent_does_not_raise(fake_home, monkeypatch):
    """destroy() na nieistniejącej instancji nie rzuca wyjątku."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(fake_home))
    i = make_inst(inst_mod, 99, fake_home)
    i.destroy()

def test_destroy_inst0_allowed(fake_home, monkeypatch):
    """inst-0 nie ma specjalnych zabezpieczeń — destroy() działa normalnie."""
    from gui import instance as inst_mod
    monkeypatch.setattr(inst_mod, "USER_HOME", str(fake_home))
    i = make_inst(inst_mod, 0, fake_home)
    i.create()
    i.destroy()
    assert not i.exists()
