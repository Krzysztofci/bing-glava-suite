# =============================================================================
# gui/glava.py
# Sterowanie procesem GLava: restart, toggle, zapis modułu do rc.glsl.
# =============================================================================

import os
import subprocess
import re
from .core import RC_GLSL, FLAG_RED, FLAG_MANUAL, WALLPAPER_LOCK, BIN_DIR


def glava_is_running():
    res = subprocess.run(["pgrep", "-x", "glava"], capture_output=True)
    return res.returncode == 0


def glava_start(extra_flags=None):
    cmd = ["glava", "--desktop"]
    if extra_flags:
        import shlex
        cmd += shlex.split(extra_flags)
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def glava_stop():
    subprocess.run(["pkill", "-x", "glava"])


def glava_restart(module, delay_ms=500, after_fn=None, extra_flags=None):
    """
    Zatrzymuje GLava, zapisuje moduł do rc.glsl, startuje po delay_ms.
    after_fn — opcjonalny callable wywoływany po restarcie (np. update_status).
    """
    _write_rc_module(module)
    glava_stop()
    if after_fn:
        import threading
        def _delayed():
            import time
            time.sleep(delay_ms / 1000.0)
            glava_start(extra_flags)
            after_fn()
        threading.Thread(target=_delayed, daemon=True).start()
    else:
        import time, threading
        threading.Thread(
            target=lambda: (time.sleep(delay_ms / 1000.0), glava_start(extra_flags)),
            daemon=True
        ).start()


def glava_toggle():
    subprocess.run(["pkill", "-x", "glava"]) if glava_is_running() \
        else glava_start()


def _write_rc_module(module):
    if not os.path.exists(RC_GLSL):
        return
    with open(RC_GLSL) as f:
        content = f.read()
    new = re.sub(
        r'^#request mod .*',
        f'#request mod {module}',
        content,
        flags=re.MULTILINE
    )
    with open(RC_GLSL, "w") as f:
        f.write(new)


def restore_auto(callback=None):
    """Usuwa flagi ręczne i uruchamia auto-generowanie kolorów z tapety."""
    for flag in (FLAG_RED, FLAG_MANUAL):
        if os.path.exists(flag):
            os.remove(flag)
    script = os.path.join(BIN_DIR, "glava-colors-auto")
    subprocess.Popen(["/bin/bash", script])
    if callback:
        callback()


def _sudo_run(cmd):
    """Uruchamia komendę przez sudo z dialogiem zenity lub bezpośrednio."""
    import shutil
    if shutil.which("zenity"):
        passwd = subprocess.run(
            ["zenity", "--password", "--title=Autoryzacja"],
            capture_output=True, text=True
        ).stdout.strip()
        if passwd:
            subprocess.run(["sudo", "-S"] + cmd,
                           input=passwd + "\n",
                           capture_output=True, text=True)
    else:
        subprocess.run(["sudo"] + cmd)


def toggle_wallpaper_lock(lock_path):
    """Przełącza blokadę tapety. Zwraca True jeśli teraz zablokowana."""
    if os.path.exists(lock_path):
        os.remove(lock_path)
        return False
    else:
        open(lock_path, "a").close()
        return True
