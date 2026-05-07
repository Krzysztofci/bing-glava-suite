# =============================================================================
# gui/glava.py
# Sterowanie procesem GLava: restart, toggle, zapis modułu do rc.glsl.
# =============================================================================

import os
import subprocess
import re
from .core import RC_GLSL, FLAG_RED, FLAG_MANUAL, WALLPAPER_LOCK, BIN_DIR

AUTOSTART_FILE = os.path.expanduser("~/.config/autostart/glava.desktop")


def glava_is_running():
    res = subprocess.run(["pgrep", "-x", "glava"], capture_output=True)
    return res.returncode == 0


def glava_start(extra_flags=None, env=None):
    """
    Uruchamia GLava.
    extra_flags — string z flagami (np. "--desktop --verbose")
    env         — dict nadpisujący zmienne środowiskowe (np. {"LIBGL_ALWAYS_SOFTWARE": "1"})
    """
    cmd = ["glava"]
    if extra_flags:
        import shlex
        cmd += shlex.split(extra_flags)
    else:
        cmd.append("--desktop")

    proc_env = None
    if env:
        proc_env = os.environ.copy()
        proc_env.update(env)

    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=proc_env,
    )


def glava_stop():
    subprocess.run(["pkill", "-x", "glava"])


def glava_restart(module, delay_ms=500, after_fn=None, extra_flags=None, env=None):
    """
    Zatrzymuje GLava, zapisuje moduł do rc.glsl, startuje po delay_ms.
    after_fn    — opcjonalny callable wywoływany po restarcie (np. update_status).
    extra_flags — string z flagami przekazywany do glava_start()
    env         — dict nadpisujący zmienne środowiskowe (np. LIBGL_ALWAYS_SOFTWARE)
    """
    _write_rc_module(module)
    glava_stop()

    def _do_start():
        import time
        time.sleep(delay_ms / 1000.0)
        glava_start(extra_flags, env=env)
        if after_fn:
            after_fn()

    import threading
    threading.Thread(target=_do_start, daemon=True).start()


def update_autostart(extra_flags):
    """
    Podmienia linię Exec= w ~/.config/autostart/glava.desktop.
    Tworzy plik jeśli nie istnieje.
    Zwraca True przy powodzeniu, False przy błędzie.
    """
    flags = extra_flags.strip() if extra_flags else "--desktop"
    if not flags:
        flags = "--desktop"

    exec_line = f"Exec=glava {flags}\n"

    desktop_template = (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Application\n"
        "Name=GLava\n"
        "Comment=OpenGL audio visualizer\n"
        f"Exec=glava {flags}\n"
        "Icon=multimedia-audio-player\n"
        "Terminal=false\n"
        "Categories=AudioVideo;\n"
        "X-GNOME-Autostart-enabled=true\n"
        "StartupNotify=false\n"
    )

    try:
        os.makedirs(os.path.dirname(AUTOSTART_FILE), exist_ok=True)

        if os.path.exists(AUTOSTART_FILE):
            with open(AUTOSTART_FILE) as f:
                lines = f.readlines()
            new_lines = []
            found = False
            for line in lines:
                if line.startswith("Exec="):
                    new_lines.append(exec_line)
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(exec_line)
            with open(AUTOSTART_FILE, "w") as f:
                f.writelines(new_lines)
        else:
            with open(AUTOSTART_FILE, "w") as f:
                f.write(desktop_template)

        return True
    except Exception:
        return False


def glava_toggle():
    if glava_is_running():
        subprocess.run(["pkill", "-x", "glava"])
    else:
        glava_start(env={"XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}"})


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
