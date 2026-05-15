# =============================================================================
# gui/glava.py
# Sterowanie procesami GLava: start, stop, restart per instancja.
#
# Kluczowa zmiana vs repo: glava_start() zwraca Popen.
# GUI przechowuje słownik {inst_id: Popen} i zabija tylko właściwy proces.
# Globalne pkill -x glava zostało ograniczone wyłącznie do glava_stop_all().
# =============================================================================

import os
import subprocess
import re
import threading
import time

from .core import RC_GLSL, FLAG_RED, FLAG_MANUAL, WALLPAPER_LOCK, BIN_DIR

AUTOSTART_FILE = os.path.expanduser("~/.config/autostart/glava.desktop")


# =============================================================================
# Funkcje per-instancja (główne API)
# =============================================================================

def glava_start(extra_flags=None, env=None, instance=None):
    """
    Uruchamia jedną instancję GLava i zwraca obiekt Popen.

    extra_flags — string z flagami (np. "--desktop --verbose")
    env         — dict nadpisujący zmienne środowiskowe
    instance    — GlavaInstance; ustawia XDG_CONFIG_HOME na instance.xdg_dir
                  (dla inst_id=0 XDG_CONFIG_HOME nie jest nadpisywane)

    Zwraca: subprocess.Popen lub None przy błędzie.
    """
    cmd = ["glava"]
    if extra_flags:
        import shlex
        cmd += shlex.split(extra_flags)
    else:
        cmd.append("--desktop")

    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    if instance and instance.inst_id != 0:
        proc_env["XDG_CONFIG_HOME"] = instance.xdg_dir

    try:
        return subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=proc_env,
        )
    except Exception:
        return None


def glava_stop_instance(proc):
    """
    Zatrzymuje konkretną instancję GLava podaną jako Popen.
    Próbuje SIGTERM, po 2s SIGKILL.
    Bezpieczne: sprawdza czy proces jeszcze żyje przed wysłaniem sygnału.
    """
    if proc is None:
        return
    try:
        if proc.poll() is None:          # proces żyje
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
    except OSError:
        pass


def glava_is_instance_running(proc):
    """
    Zwraca True jeśli dany proces Popen wciąż działa.
    """
    if proc is None:
        return False
    return proc.poll() is None


def glava_restart_instance(instance, module,
                            delay_ms=500,
                            after_fn=None,
                            extra_flags=None,
                            env=None,
                            proc=None):
    """
    Zatrzymuje konkretną instancję (proc), zapisuje moduł do jej rc.glsl,
    startuje nową i zwraca nowy Popen przez after_fn(new_proc).

    instance    — GlavaInstance
    module      — nazwa modułu (bars, wave, circle, graph, radial)
    delay_ms    — opóźnienie między stop a start [ms]
    after_fn    — callable(new_proc) wywoływany po starcie
    extra_flags — dodatkowe flagi GLava
    env         — nadpisanie zmiennych środowiskowych
    proc        — aktualny Popen tej instancji (do zatrzymania)
    """
    _write_rc_module(module, rc_path=instance.rc_glsl)
    glava_stop_instance(proc)

    def _do_start():
        time.sleep(delay_ms / 1000.0)
        new_proc = glava_start(extra_flags, env=env, instance=instance)
        if after_fn:
            after_fn(new_proc)

    threading.Thread(target=_do_start, daemon=True).start()


# =============================================================================
# Funkcje globalne (legacy / toggle)
# =============================================================================

def glava_is_running():
    """Zwraca True jeśli jakikolwiek proces 'glava' jest uruchomiony."""
    res = subprocess.run(["pgrep", "-x", "glava"], capture_output=True)
    return res.returncode == 0


def glava_stop_all():
    """Zatrzymuje WSZYSTKIE procesy glava (pkill). Używać tylko przy wyjściu z GUI."""
    subprocess.run(["pkill", "-x", "glava"])


def glava_stop():
    """Alias dla glava_stop_all() — zachowany dla kompatybilności wstecznej."""
    glava_stop_all()


def glava_restart(module, delay_ms=500, after_fn=None, extra_flags=None,
                  env=None, instance=None):
    """
    Kompatybilność wsteczna: restart z globalnym pkill.
    Przy multiinstancji używaj glava_restart_instance().
    """
    if instance:
        _write_rc_module(module, rc_path=instance.rc_glsl)
    else:
        _write_rc_module(module)
    glava_stop_all()

    def _do_start():
        time.sleep(delay_ms / 1000.0)
        glava_start(extra_flags, env=env, instance=instance)
        if after_fn:
            after_fn()

    threading.Thread(target=_do_start, daemon=True).start()


def glava_toggle():
    """Przełącza GLavę globalnie (stop/start instancji 0)."""
    if glava_is_running():
        subprocess.run(["pkill", "-x", "glava"])
    else:
        glava_start(env={"XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}"})


# =============================================================================
# Wewnętrzne
# =============================================================================

def _write_rc_module(module, rc_path=None):
    if rc_path is None:
        rc_path = RC_GLSL
    if not os.path.exists(rc_path):
        return
    with open(rc_path) as f:
        content = f.read()
    new = re.sub(
        r'^#request mod .*',
        f'#request mod {module}',
        content,
        flags=re.MULTILINE
    )
    with open(rc_path, "w") as f:
        f.write(new)


def read_rc_module(rc_path=None):
    """
    Odczytuje aktywny moduł z linii '#request mod <name>' w rc.glsl.
    Zwraca nazwę modułu (str) lub None jeśli plik nie istnieje / brak linii.
    """
    from .core import GLAVA_MODULES
    if rc_path is None:
        rc_path = RC_GLSL
    if not os.path.exists(rc_path):
        return None
    try:
        with open(rc_path) as f:
            content = f.read()
        m = re.search(r'^#request mod (\S+)', content, re.MULTILINE)
        if m:
            mod = m.group(1)
            return mod if mod in GLAVA_MODULES else None
    except Exception:
        pass
    return None


def restore_auto(callback=None):
    """Usuwa flagi ręczne i uruchamia auto-generowanie kolorów z tapety."""
    for flag in (FLAG_RED, FLAG_MANUAL):
        if os.path.exists(flag):
            os.remove(flag)
    script = os.path.join(BIN_DIR, "glava-colors-auto")
    subprocess.Popen(["/bin/bash", script])
    if callback:
        callback()


def update_autostart(extra_flags=None):
    """
    Zapisuje ~/.config/autostart/glava.desktop uruchamiający glava-autostart.sh.
    Skrypt startuje wszystkie zarejestrowane instancje GLava z właściwym
    XDG_CONFIG_HOME dla każdej.
    extra_flags — ignorowany (zachowany dla kompatybilności wstecznej).
    """
    import shutil

    # Szukaj glava-autostart.sh obok glava-gui.py lub w BIN_DIR
    candidates = [
        os.path.join(BIN_DIR, "glava-autostart.sh"),
        os.path.join(os.path.dirname(__file__), "..", "glava-autostart.sh"),
    ]
    script_path = None
    for c in candidates:
        if os.path.exists(os.path.abspath(c)):
            script_path = os.path.abspath(c)
            break

    if script_path is None:
        # Fallback — stare zachowanie z pojedynczą instancją
        flags = (extra_flags or "--desktop").strip() or "--desktop"
        exec_line = f"Exec=glava {flags}\n"
    else:
        exec_line = f"Exec=bash {script_path}\n"

    desktop_template = (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Application\n"
        "Name=GLava (multi-instance)\n"
        "Comment=OpenGL audio visualizer - all instances\n"
        + exec_line
        + "Icon=multimedia-audio-player\n"
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
