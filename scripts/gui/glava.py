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

from .core import RC_GLSL, FLAG_RED, FLAG_MANUAL, BIN_DIR

AUTOSTART_FILE  = os.path.expanduser("~/.config/autostart/glava.desktop")
_PID_DIR        = os.path.expanduser("~/.config/GlavaMP")


# =============================================================================
# Zarzadzanie plikami PID per instancja
# =============================================================================

def _pid_path(inst_id):
    """Zwraca sciezke pliku PID dla danej instancji."""
    return os.path.join(_PID_DIR, f"inst-{inst_id}.pid")


def write_pid(inst_id, pid):
    """Zapisuje PID procesu GLava do pliku inst-{id}.pid."""
    os.makedirs(_PID_DIR, exist_ok=True)
    try:
        with open(_pid_path(inst_id), "w") as f:
            f.write(str(pid))
    except Exception:
        pass


def read_pid(inst_id):
    """
    Czyta PID z pliku inst-{id}.pid.
    Zwraca int lub None jesli plik nie istnieje lub jest niepoprawny.
    """
    path = _pid_path(inst_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return int(f.read().strip())
    except Exception:
        return None


def clear_pid(inst_id):
    """Usuwa plik PID instancji."""
    try:
        os.remove(_pid_path(inst_id))
    except FileNotFoundError:
        pass
    except Exception:
        pass


def is_pid_running(pid):
    """
    Sprawdza czy proces o podanym PID istnieje i dziala.
    Uzywa os.kill(pid, 0) — nie wysyla sygnalu, tylko sprawdza istnienie.
    """
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError):
        return False


def adopt_instance(inst_id):
    """
    Probuje adoptowac istniejacy proces GLava dla danej instancji.
    Czyta PID z pliku, sprawdza czy proces zyje.
    Zwraca (pid, Popen-like) lub (None, None).

    Zamiast pelnego Popen zwracamy obiekt-wrapper ktory implementuje
    poll() i terminate() przez syscalle — wystarczy do glava_stop_instance().
    """
    pid = read_pid(inst_id)
    if not is_pid_running(pid):
        clear_pid(inst_id)
        return None, None
    return pid, _AdoptedProcess(pid, inst_id)


class _AdoptedProcess:
    """
    Lekki wrapper symulujacy subprocess.Popen dla adoptowanego procesu.
    Implementuje poll(), terminate(), kill(), wait() przez syscalle.
    """
    def __init__(self, pid, inst_id):
        self.pid     = pid
        self._inst_id = inst_id

    def poll(self):
        """None jesli proces zyje, -1 jesli martwy (jak Popen.poll())."""
        return None if is_pid_running(self.pid) else -1

    def terminate(self):
        try:
            os.kill(self.pid, 15)   # SIGTERM
        except (ProcessLookupError, OSError):
            pass

    def kill(self):
        try:
            os.kill(self.pid, 9)    # SIGKILL
        except (ProcessLookupError, OSError):
            pass

    def wait(self, timeout=None):
        """
        Czeka az proces sie zakonczy.
        Uzywa /proc/<pid>/status zamiast os.kill — poprawnie wykrywa zombie
        (procesy zakonczone ale nie zebrane przez rodzica).
        """
        import time
        deadline = time.time() + (timeout or 5)
        while time.time() < deadline:
            proc_status = f"/proc/{self.pid}/status"
            if not os.path.exists(proc_status):
                return
            try:
                with open(proc_status) as f:
                    for line in f:
                        if line.startswith("State:"):
                            if "Z" in line:  # zombie — faktycznie martwy
                                return
                            break
            except OSError:
                return  # proces zniknął w trakcie czytania
            time.sleep(0.1)

    def __repr__(self):
        return f"_AdoptedProcess(pid={self.pid}, inst_id={self._inst_id})"


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
    if instance:
        proc_env["XDG_CONFIG_HOME"] = instance.xdg_dir

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=proc_env,
        )
        # Zapisz PID jesli znamy inst_id
        if instance is not None:
            write_pid(instance.inst_id, proc.pid)
        return proc
    except Exception:
        return None


def glava_stop_instance(proc):
    """
    Zatrzymuje konkretna instancje GLava podana jako Popen lub _AdoptedProcess.
    Strategia: SIGTERM → czeka az PID fizycznie zniknie z /proc → SIGKILL.
    Gwarantuje ze proces nie zyje przed powrotem z funkcji.
    Usuwa plik PID jesli proc jest _AdoptedProcess.
    """
    if proc is None:
        return
    pid = getattr(proc, "pid", None)
    try:
        if proc.poll() is None:
            proc.terminate()
            # Czekaj az PID fizycznie zniknie — max 2s
            if pid is not None:
                deadline = time.time() + 2.0
                while time.time() < deadline:
                    try:
                        os.kill(pid, 0)
                        time.sleep(0.05)
                    except (ProcessLookupError, OSError):
                        break  # proces fizycznie zniknął
                else:
                    # Po 2s wciąż żyje — SIGKILL
                    try:
                        proc.kill()
                        time.sleep(0.05)
                    except (ProcessLookupError, OSError):
                        pass
            else:
                try:
                    proc.wait(timeout=2)
                except (subprocess.TimeoutExpired, Exception):
                    proc.kill()
    except OSError:
        pass
    # Usun plik PID
    if isinstance(proc, _AdoptedProcess):
        clear_pid(proc._inst_id)


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
    clear_pid(instance.inst_id)   # wyczyść PID niezależnie od typu proc

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


def update_autostart(extra_flags):
    """
    Podmienia linię Exec= w ~/.config/autostart/glava.desktop.
    Tworzy plik jeśli nie istnieje.
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
