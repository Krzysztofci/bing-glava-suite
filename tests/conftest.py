import os
import sys
import pytest
import shutil
import glob
import subprocess

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


# ── Diagnostyka osieroconych procesów glava ─────────────────────────────────

import threading

def _glava_pids() -> set[str]:
    """Wykrywa realny proces 'glava --desktop' przez ps (pgrep -f
    nie widzi tego procesu na tej maszynie z nieznanej przyczyny)."""
    result = subprocess.run(
        ["ps", "-eo", "pid,cmd"], capture_output=True, text=True
    )
    pids = set()
    for line in result.stdout.splitlines()[1:]:
        parts = line.strip().split(None, 1)
        if len(parts) < 2:
            continue
        pid, cmd = parts
        if "glava --desktop" in cmd:
            pids.add(pid)
    return pids


@pytest.fixture(autouse=True)
def _kill_stray_glava(request):
    """Sprawdza po KAŻDYM teście, niezależnie od tego czy spawnuje wątek —
    żeby złapać prawdziwego winowajcę, nie przypadkowego świadka."""
    threads_before = set(threading.enumerate())
    yield
    new_threads = set(threading.enumerate()) - threads_before
    for t in new_threads:
        if t.is_alive():
            t.join(timeout=1.0)

    leftover = _glava_pids()
    if leftover:
        print(f"\n⚠️  Test {request.node.nodeid} zostawił żywą glavę "
              f"(brak mocka glava_restart/restart_active_instance?) — zabijam.")
        for pid in leftover:
            subprocess.run(["kill", "-9", pid], capture_output=True)
