import os
import sys
import pytest
import shutil
import glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

@pytest.fixture
def tmp_glava_dir(tmp_path):
    """Tymczasowy katalog z kopią plików GLSL z glava-config/."""
    src = os.path.join(os.path.dirname(__file__), '..', 'glava-config')
    dst = str(tmp_path / "glava")
    os.makedirs(dst)
    for f in glob.glob(os.path.join(src, "*.glsl")):
        shutil.copy2(f, dst)
    return dst

@pytest.fixture
def bars_glsl(tmp_glava_dir):
    return os.path.join(tmp_glava_dir, "bars.glsl")

@pytest.fixture
def smooth_glsl(tmp_glava_dir):
    return os.path.join(tmp_glava_dir, "smooth_parameters.glsl")

@pytest.fixture
def rc_glsl(tmp_glava_dir):
    return os.path.join(tmp_glava_dir, "rc.glsl")
